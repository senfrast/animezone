"""Full catalog backup + restore.

The backup is a single self-contained JSON file containing every title (with its
channel links, metadata, genres, tags and image file_id), all categories, genres,
platform settings and panel moderators. It is enough to fully rebuild the catalog
in a brand-new database.

NOTE on images: images are stored as Telegram *file_id*s, which are tied to the
bot that uploaded them. If the SAME bot token is used, restored images work
immediately. If the bot was deleted and a NEW token is issued, the metadata and
links all restore fine but images must be re-uploaded (Telegram file_ids are
bot-specific). Everything else survives.
"""
import datetime
import io
import json
import logging
import asyncio

from database import pool as db

log = logging.getLogger("backup")

BACKUP_VERSION = 1


async def build_backup() -> dict:
    cats = await db.fetch("SELECT name, emoji, slug, description, sort_order, is_nsfw, is_active FROM categories ORDER BY sort_order")
    genres = await db.fetch("SELECT name, emoji, slug FROM genres ORDER BY name")
    settings = await db.fetch("SELECT key, value FROM platform_settings")
    mods = await db.fetch("SELECT user_id, first_name, username FROM bot_admins WHERE role='moderator'")
    titles = await db.fetch(
        """
        SELECT t.*, c.slug AS category_slug,
          COALESCE((SELECT array_agg(g.slug) FROM title_genres tg
                    JOIN genres g ON g.genre_id=tg.genre_id WHERE tg.title_id=t.title_id),
                   ARRAY[]::text[]) AS genre_slugs,
          COALESCE((SELECT array_agg(tag) FROM title_tags WHERE title_id=t.title_id),
                   ARRAY[]::text[]) AS tag_list
        FROM titles t JOIN categories c ON c.category_id=t.category_id
        ORDER BY t.title_id
        """
    )
    title_list = []
    for t in titles:
        title_list.append({
            "title": t["title"], "title_alt": t["title_alt"], "slug": t["slug"],
            "category_slug": t["category_slug"], "description": t["description"],
            "channel_link": t["channel_link"], "channel_username": t["channel_username"],
            "image_file_id": t["image_file_id"],
            "language": t["language"], "status": t["status"],
            "episode_count": t["episode_count"], "quality": t["quality"],
            "release_year": t["release_year"], "is_nsfw": t["is_nsfw"],
            "is_featured": t["is_featured"], "featured_order": t["featured_order"],
            "is_active": t["is_active"], "is_approved": t.get("is_approved", True),
            "rating": float(t["rating"]) if t["rating"] is not None else 0.0,
            "genres": list(t["genre_slugs"]), "tags": list(t["tag_list"]),
        })
    return {
        "version": BACKUP_VERSION,
        "exported_at": datetime.datetime.utcnow().isoformat() + "Z",
        "counts": {"titles": len(title_list), "categories": len(cats), "genres": len(genres)},
        "categories": [dict(c) for c in cats],
        "genres": [dict(g) for g in genres],
        "titles": title_list,
        "settings": {r["key"]: r["value"] for r in settings},
        "moderators": [dict(m) for m in mods],
    }


async def backup_bytes():
    data = await build_backup()
    raw = json.dumps(data, ensure_ascii=False, indent=2, default=str).encode("utf-8")
    ts = datetime.datetime.now().strftime("%Y%m%d_%H%M")
    return io.BytesIO(raw), f"animezone_backup_{ts}.json", data["counts"]


async def restore_from(data: dict) -> dict:
    """Restore a backup. Existing rows are preserved; only missing items are added
    (matched by slug), so restoring is safe and idempotent."""
    added = {"categories": 0, "titles": 0, "genres": 0, "moderators": 0, "settings": 0}

    # genres (seeded normally, but add any missing)
    for g in data.get("genres", []):
        r = await db.execute(
            "INSERT INTO genres (name, emoji, slug) VALUES ($1,$2,$3) ON CONFLICT (name) DO NOTHING",
            g["name"], g.get("emoji", "🎭"), g["slug"],
        )
        if r.endswith("1"):
            added["genres"] += 1

    # categories
    for c in data.get("categories", []):
        r = await db.execute(
            """INSERT INTO categories (name, emoji, slug, description, sort_order, is_nsfw, is_active)
               VALUES ($1,$2,$3,$4,$5,$6,$7) ON CONFLICT (name) DO NOTHING""",
            c["name"], c.get("emoji", "📂"), c["slug"], c.get("description"),
            c.get("sort_order", 0), c.get("is_nsfw", False), c.get("is_active", True),
        )
        if r.endswith("1"):
            added["categories"] += 1

    # maps
    cat_map = {r["slug"]: r["category_id"] for r in await db.fetch("SELECT category_id, slug FROM categories")}
    genre_map = {r["slug"]: r["genre_id"] for r in await db.fetch("SELECT genre_id, slug FROM genres")}

    # titles
    for t in data.get("titles", []):
        if await db.fetchval("SELECT 1 FROM titles WHERE slug=$1", t["slug"]):
            continue
        cid = cat_map.get(t.get("category_slug"))
        if not cid:
            continue
        row = await db.fetchrow(
            """INSERT INTO titles (title, title_alt, slug, category_id, description,
                channel_link, channel_username, image_file_id, language, status,
                episode_count, quality, release_year, is_nsfw, is_featured, featured_order,
                is_active, is_approved)
               VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12,$13,$14,$15,$16,$17,$18)
               RETURNING title_id""",
            t["title"], t.get("title_alt"), t["slug"], cid, t.get("description", ""),
            t["channel_link"], t.get("channel_username"), t.get("image_file_id"),
            t.get("language", "Hindi"), t.get("status", "Ongoing"),
            t.get("episode_count", 0), t.get("quality", "720p + 1080p"),
            t.get("release_year"), t.get("is_nsfw", False),
            t.get("is_featured", False), t.get("featured_order", 0),
            t.get("is_active", True), t.get("is_approved", True),
        )
        for gslug in t.get("genres", []):
            gid = genre_map.get(gslug)
            if gid:
                await db.execute(
                    "INSERT INTO title_genres (title_id, genre_id) VALUES ($1,$2) ON CONFLICT DO NOTHING",
                    row["title_id"], gid,
                )
        for tag in t.get("tags", []):
            await db.execute(
                "INSERT INTO title_tags (title_id, tag) VALUES ($1,$2)", row["title_id"], tag
            )
        added["titles"] += 1

    # settings
    for k, v in (data.get("settings") or {}).items():
        await db.execute(
            """INSERT INTO platform_settings (key, value) VALUES ($1,$2)
               ON CONFLICT (key) DO UPDATE SET value=EXCLUDED.value""",
            k, v,
        )
        added["settings"] += 1

    # moderators
    for m in data.get("moderators", []):
        await db.execute(
            """INSERT INTO bot_admins (user_id, role, first_name, username)
               VALUES ($1,'moderator',$2,$3) ON CONFLICT (user_id) DO NOTHING""",
            m["user_id"], m.get("first_name"), m.get("username"),
        )
        added["moderators"] += 1

    # refresh category counts
    await db.execute(
        """UPDATE categories c SET title_count =
           (SELECT COUNT(*) FROM titles t WHERE t.category_id=c.category_id AND t.is_active=TRUE)"""
    )
    return added


# ---------------- Telegram channel "backup vault" ----------------
async def send_json_to_channel(bot, chat_id) -> dict:
    """Post the full DB JSON backup as a document to a private channel."""
    buf, fname, counts = await backup_bytes()
    caption = (
        f"🗄️ AnimeZone database backup\n"
        f"{counts['titles']} titles · {counts['categories']} categories · {counts['genres']} genres\n"
        f"{datetime.datetime.now().strftime('%Y-%m-%d %H:%M')} IST\n"
        f"Restore via Admin → ♻️ Restore Backup (forward this file to the bot)."
    )
    await bot.send_document(chat_id=chat_id, document=buf, filename=fname, caption=caption)
    return counts


async def archive_covers_to_channel(bot, chat_id, progress=None) -> dict:
    """Post every cover image to the channel so the actual image bytes are
    stored safely (survives a bot-token change, unlike a bare file_id)."""
    rows = await db.fetch(
        "SELECT title_id, title, slug, image_file_id FROM titles "
        "WHERE image_file_id IS NOT NULL AND deleted_at IS NULL ORDER BY title_id"
    )
    total = len(rows)
    sent = failed = 0
    await bot.send_message(
        chat_id,
        f"🖼️ Cover archive — {total} images — {datetime.datetime.now().strftime('%Y-%m-%d %H:%M')} IST",
    )
    for i, r in enumerate(rows, 1):
        try:
            await bot.send_photo(
                chat_id=chat_id, photo=r["image_file_id"],
                caption=f"#{r['title_id']} {r['title']}\nslug: {r['slug']}",
            )
            sent += 1
        except Exception:  # noqa: BLE001
            failed += 1
        if i % 15 == 0:
            await asyncio.sleep(1.0)
            if progress:
                await progress(i, total, sent, failed)
    return {"total": total, "sent": sent, "failed": failed}
