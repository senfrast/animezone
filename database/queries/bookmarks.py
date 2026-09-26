"""Bookmark CRUD queries."""
from database import pool as db
from database.queries import titles as titles_q


async def user_bookmark_ids(user_id: int):
    rows = await db.fetch("SELECT title_id FROM bookmarks WHERE user_id=$1", user_id)
    return {r["title_id"] for r in rows}


async def toggle(user_id: int, title_id: int, max_bookmarks: int):
    existing = await db.fetchval(
        "SELECT 1 FROM bookmarks WHERE user_id=$1 AND title_id=$2", user_id, title_id
    )
    if existing:
        await db.execute(
            "DELETE FROM bookmarks WHERE user_id=$1 AND title_id=$2", user_id, title_id
        )
        await db.execute(
            "UPDATE users SET total_bookmarks=GREATEST(total_bookmarks-1,0) WHERE user_id=$1",
            user_id,
        )
        await db.execute(
            "UPDATE titles SET total_bookmarks=GREATEST(total_bookmarks-1,0) WHERE title_id=$1",
            title_id,
        )
        bookmarked = False
    else:
        count = await db.fetchval(
            "SELECT COUNT(*) FROM bookmarks WHERE user_id=$1", user_id
        ) or 0
        if count >= max_bookmarks:
            return {"error": "limit", "total": count}
        await db.execute(
            "INSERT INTO bookmarks (user_id, title_id) VALUES ($1,$2) ON CONFLICT DO NOTHING",
            user_id, title_id,
        )
        await db.execute(
            "UPDATE users SET total_bookmarks=total_bookmarks+1 WHERE user_id=$1", user_id
        )
        await db.execute(
            "UPDATE titles SET total_bookmarks=total_bookmarks+1 WHERE title_id=$1", title_id
        )
        bookmarked = True
    total = await db.fetchval(
        "SELECT COUNT(*) FROM bookmarks WHERE user_id=$1", user_id
    ) or 0
    return {"bookmarked": bookmarked, "total": total}


async def list_for_user(user_id: int, show_nsfw: bool):
    nsfw = "" if show_nsfw else (
        " AND t.is_nsfw=FALSE AND t.category_id NOT IN "
        "(SELECT category_id FROM categories WHERE is_nsfw=TRUE)"
    )
    return await db.fetch(
        f"""
        SELECT t.*, c.name AS category_name, c.emoji AS category_emoji,
          COALESCE((SELECT array_agg(g.name ORDER BY g.name)
                    FROM title_genres tg JOIN genres g ON g.genre_id=tg.genre_id
                    WHERE tg.title_id=t.title_id), ARRAY[]::text[]) AS genres
        FROM bookmarks b
        JOIN titles t ON t.title_id=b.title_id
        JOIN categories c ON c.category_id=t.category_id
        WHERE b.user_id=$1 AND t.is_active=TRUE AND t.channel_alive=TRUE {nsfw}
        ORDER BY b.created_at DESC
        """,
        user_id,
    )
