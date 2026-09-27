"""Title CRUD, search, listing with NSFW filtering."""
from database import pool as db
from utils.helpers import slugify

# Base active/alive filter
_ALIVE = "t.is_active = TRUE AND t.channel_alive = TRUE"


def _nsfw_clause(show_nsfw: bool) -> str:
    """Return an SQL fragment restricting NSFW when show_nsfw is False."""
    if show_nsfw:
        return ""
    return (
        " AND t.is_nsfw = FALSE AND t.category_id NOT IN "
        "(SELECT category_id FROM categories WHERE is_nsfw = TRUE)"
    )


def serialize(row, bookmark_ids=None) -> dict:
    if row is None:
        return None
    d = dict(row)
    tid = d.get("title_id")
    out = {
        "title_id": tid,
        "title": d.get("title"),
        "title_alt": d.get("title_alt"),
        "slug": d.get("slug"),
        "category_id": d.get("category_id"),
        "category_name": d.get("category_name"),
        "category_emoji": d.get("category_emoji"),
        "description": d.get("description") or "",
        "channel_link": d.get("channel_link"),
        "channel_username": d.get("channel_username"),
        "image_url": f"/api/v1/image/{tid}",
        "language": d.get("language"),
        "status": d.get("status"),
        "episode_count": d.get("episode_count"),
        "quality": d.get("quality"),
        "release_year": d.get("release_year"),
        "is_nsfw": d.get("is_nsfw"),
        "total_clicks": d.get("total_clicks"),
        "total_joins": d.get("total_joins"),
        "total_bookmarks": d.get("total_bookmarks"),
        "total_shares": d.get("total_shares"),
        "rating": float(d["rating"]) if d.get("rating") is not None else 0.0,
        "rating_count": d.get("rating_count"),
        "is_featured": d.get("is_featured"),
        "genres": d.get("genres") or [],
    }
    if bookmark_ids is not None:
        out["is_bookmarked"] = tid in bookmark_ids
    return out


_SELECT = f"""
    SELECT t.*, c.name AS category_name, c.emoji AS category_emoji,
      COALESCE((SELECT array_agg(g.name ORDER BY g.name)
                FROM title_genres tg JOIN genres g ON g.genre_id=tg.genre_id
                WHERE tg.title_id=t.title_id), ARRAY[]::text[]) AS genres
    FROM titles t JOIN categories c ON c.category_id=t.category_id
"""


async def featured(show_nsfw: bool, limit: int = 5):
    return await db.fetch(
        f"{_SELECT} WHERE {_ALIVE} AND t.is_featured=TRUE {_nsfw_clause(show_nsfw)} "
        f"ORDER BY t.featured_order, t.title_id LIMIT {int(limit)}"
    )


async def recently_added(show_nsfw: bool, limit: int = 10):
    return await db.fetch(
        f"{_SELECT} WHERE {_ALIVE} {_nsfw_clause(show_nsfw)} "
        f"ORDER BY t.added_at DESC LIMIT {int(limit)}"
    )


async def popular(show_nsfw: bool, limit: int = 10):
    return await db.fetch(
        f"{_SELECT} WHERE {_ALIVE} {_nsfw_clause(show_nsfw)} "
        f"ORDER BY t.total_clicks DESC LIMIT {int(limit)}"
    )


async def trending(show_nsfw: bool, limit: int = 10):
    return await db.fetch(
        f"""{_SELECT}
        LEFT JOIN (
            SELECT title_id, COUNT(*) AS recent FROM click_events
            WHERE created_at > NOW() - INTERVAL '24 hours' GROUP BY title_id
        ) ce ON ce.title_id = t.title_id
        WHERE {_ALIVE} {_nsfw_clause(show_nsfw)}
        ORDER BY COALESCE(ce.recent,0) DESC, t.total_clicks DESC
        LIMIT {int(limit)}"""
    )


_SORTS = {
    "popular": "t.total_clicks DESC",
    "newest": "t.added_at DESC",
    "alphabetical": "t.title ASC",
    "rating": "t.rating DESC, t.rating_count DESC",
}


async def by_category(category_id: int, show_nsfw: bool, page: int, per_page: int,
                      sort="popular", language="all", genre="all", status="all"):
    conds = [_ALIVE, "t.category_id = $1"]
    args = [category_id]
    nsfw = _nsfw_clause(show_nsfw)
    if language and language != "all":
        args.append(language)
        conds.append(f"t.language = ${len(args)}")
    if status and status != "all":
        args.append(status)
        conds.append(f"t.status = ${len(args)}")
    genre_join = ""
    if genre and genre != "all":
        args.append(genre)
        genre_join = (" JOIN title_genres tgf ON tgf.title_id=t.title_id "
                      " JOIN genres gf ON gf.genre_id=tgf.genre_id ")
        conds.append(f"gf.slug = ${len(args)}")
    where = " AND ".join(conds) + nsfw
    order = _SORTS.get(sort, _SORTS["popular"])

    total = await db.fetchval(
        f"SELECT COUNT(DISTINCT t.title_id) FROM titles t "
        f"JOIN categories c ON c.category_id=t.category_id {genre_join} WHERE {where}",
        *args,
    ) or 0

    offset = (max(page, 1) - 1) * per_page
    rows = await db.fetch(
        f"{_SELECT} {genre_join} WHERE {where} ORDER BY {order} "
        f"LIMIT {int(per_page)} OFFSET {int(offset)}",
        *args,
    )
    return rows, total


async def category_filters(category_id: int, show_nsfw: bool):
    nsfw = _nsfw_clause(show_nsfw)
    langs = await db.fetch(
        f"SELECT DISTINCT t.language FROM titles t WHERE {_ALIVE} AND t.category_id=$1 {nsfw} "
        f"AND t.language IS NOT NULL ORDER BY 1",
        category_id,
    )
    genres = await db.fetch(
        f"""SELECT g.name, g.slug, COUNT(*) AS count
            FROM titles t
            JOIN title_genres tg ON tg.title_id=t.title_id
            JOIN genres g ON g.genre_id=tg.genre_id
            WHERE {_ALIVE} AND t.category_id=$1 {nsfw}
            GROUP BY g.name, g.slug ORDER BY count DESC""",
        category_id,
    )
    return (
        [r["language"] for r in langs],
        [dict(r) for r in genres],
    )


async def get_by_slug(slug: str):
    return await db.fetchrow(f"{_SELECT} WHERE t.slug=$1", slug)


async def get_by_id(tid: int):
    return await db.fetchrow(f"{_SELECT} WHERE t.title_id=$1", tid)


async def get_image_file_id(tid: int):
    return await db.fetchval("SELECT image_file_id FROM titles WHERE title_id=$1", tid)


async def genres_full(tid: int):
    return await db.fetch(
        """SELECT g.name, g.emoji, g.slug FROM title_genres tg
           JOIN genres g ON g.genre_id=tg.genre_id WHERE tg.title_id=$1 ORDER BY g.name""",
        tid,
    )


async def tags(tid: int):
    rows = await db.fetch("SELECT tag FROM title_tags WHERE title_id=$1", tid)
    return [r["tag"] for r in rows]


async def related(tid: int, category_id: int, show_nsfw: bool, limit: int = 10):
    return await db.fetch(
        f"""{_SELECT}
        WHERE {_ALIVE} AND t.category_id=$2 AND t.title_id <> $1 {_nsfw_clause(show_nsfw)}
        AND t.title_id IN (
            SELECT tg2.title_id FROM title_genres tg2 WHERE tg2.genre_id IN (
                SELECT genre_id FROM title_genres WHERE title_id=$1))
        ORDER BY t.total_clicks DESC LIMIT {int(limit)}""",
        tid, category_id,
    )


async def search(query: str, show_nsfw: bool, limit: int = 20):
    return await db.fetch(
        f"""{_SELECT}
        WHERE {_ALIVE} {_nsfw_clause(show_nsfw)}
        AND (similarity(t.title, $1) > 0.2
             OR t.title ILIKE '%'||$1||'%'
             OR t.title_alt ILIKE '%'||$1||'%')
        ORDER BY similarity(t.title, $1) DESC, t.total_clicks DESC
        LIMIT {int(limit)}""",
        query,
    )


# ---------------- mutations ----------------
async def create(data: dict, approved: bool = True):
    """Create a title. If approved=False the title is saved as PENDING:
    is_active=FALSE + is_approved=FALSE, so it stays hidden from the app
    until an owner approves it."""
    slug = slugify(data["title"])
    # ensure unique slug
    n = 1
    base = slug
    while await db.fetchval("SELECT 1 FROM titles WHERE slug=$1", slug):
        n += 1
        slug = f"{base}-{n}"
    row = await db.fetchrow(
        """
        INSERT INTO titles (title, title_alt, slug, category_id, description,
            channel_link, channel_username, image_file_id, language, status,
            episode_count, is_nsfw, added_by, is_active, is_approved)
        VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12,$13,$14,$15)
        RETURNING *
        """,
        data["title"], data.get("title_alt"), slug, data["category_id"],
        data.get("description", ""), data["channel_link"], data.get("channel_username"),
        data.get("image_file_id"), data.get("language", "Hindi"),
        data.get("status", "Ongoing"), int(data.get("episode_count", 0)),
        bool(data.get("is_nsfw", False)), data.get("added_by"),
        approved, approved,
    )
    for gid in data.get("genre_ids", []):
        await db.execute(
            "INSERT INTO title_genres (title_id, genre_id) VALUES ($1,$2) ON CONFLICT DO NOTHING",
            row["title_id"], gid,
        )
    return row


# ---------------- approval workflow ----------------
async def list_pending():
    return await db.fetch(
        f"{_SELECT} WHERE t.is_approved = FALSE ORDER BY t.added_at ASC"
    )


async def count_pending():
    return await db.fetchval(
        "SELECT COUNT(*) FROM titles WHERE is_approved = FALSE"
    ) or 0


async def approve(tid: int):
    row = await db.fetchrow(
        "UPDATE titles SET is_approved=TRUE, is_active=TRUE, updated_at=NOW() "
        "WHERE title_id=$1 RETURNING *",
        tid,
    )
    return row


async def get_pending_by_id(tid: int):
    return await db.fetchrow(f"{_SELECT} WHERE t.title_id=$1 AND t.is_approved=FALSE", tid)


async def set_active(tid: int, value: bool):
    await db.execute("UPDATE titles SET is_active=$1 WHERE title_id=$2", value, tid)


async def delete(tid: int):
    await db.execute("DELETE FROM titles WHERE title_id=$1", tid)


async def list_all(limit=50, offset=0):
    return await db.fetch(
        f"{_SELECT} ORDER BY t.added_at DESC LIMIT {int(limit)} OFFSET {int(offset)}"
    )


async def count_all():
    return await db.fetchval("SELECT COUNT(*) FROM titles") or 0


async def set_featured(tid: int, value: bool, order: int = 0):
    await db.execute(
        "UPDATE titles SET is_featured=$1, featured_order=$2 WHERE title_id=$3",
        value, order, tid,
    )


async def list_featured():
    return await db.fetch(
        f"{_SELECT} WHERE t.is_featured=TRUE ORDER BY t.featured_order, t.title_id"
    )


# ---------------- events / ratings ----------------
async def track_event(user_id: int, title_id: int, event_type: str):
    await db.execute(
        "INSERT INTO click_events (user_id, title_id, event_type) VALUES ($1,$2,$3)",
        user_id, title_id, event_type,
    )
    col = {"view": "total_clicks", "join": "total_joins", "share": "total_shares"}.get(
        event_type, "total_clicks"
    )
    await db.execute(f"UPDATE titles SET {col}={col}+1 WHERE title_id=$1", title_id)
    ucol = {"view": "total_clicks", "join": "total_joins", "share": "total_shares"}.get(
        event_type, "total_clicks"
    )
    await db.execute(f"UPDATE users SET {ucol}={ucol}+1 WHERE user_id=$1", user_id)
    # daily stats upsert
    tcol = {"view": "clicks", "join": "joins", "share": "shares"}.get(event_type, "clicks")
    await db.execute(
        f"""INSERT INTO title_daily_stats (date, title_id, {tcol})
            VALUES (CURRENT_DATE, $1, 1)
            ON CONFLICT (date, title_id) DO UPDATE SET {tcol} = title_daily_stats.{tcol}+1""",
        title_id,
    )
    dcol = {"view": "total_clicks", "join": "total_joins", "share": "total_shares"}.get(
        event_type, "total_clicks"
    )
    await db.execute(
        f"""INSERT INTO daily_analytics (date, {dcol}) VALUES (CURRENT_DATE, 1)
            ON CONFLICT (date) DO UPDATE SET {dcol} = daily_analytics.{dcol}+1""",
    )


async def rate(user_id: int, title_id: int, value: int):
    await db.execute(
        """INSERT INTO ratings (user_id, title_id, rating) VALUES ($1,$2,$3)
           ON CONFLICT (user_id, title_id) DO UPDATE SET rating=EXCLUDED.rating""",
        user_id, title_id, value,
    )
    row = await db.fetchrow(
        """UPDATE titles SET
             rating = COALESCE((SELECT AVG(rating)::DECIMAL(2,1) FROM ratings WHERE title_id=$1),0),
             rating_count = (SELECT COUNT(*) FROM ratings WHERE title_id=$1)
           WHERE title_id=$1 RETURNING rating, rating_count""",
        title_id,
    )
    return row


async def user_rating(user_id: int, title_id: int):
    return await db.fetchval(
        "SELECT rating FROM ratings WHERE user_id=$1 AND title_id=$2", user_id, title_id
    )
