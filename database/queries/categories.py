"""Category CRUD queries."""
from database import pool as db
from utils.helpers import slugify


async def list_categories(include_nsfw: bool = True, only_active: bool = True):
    conds = []
    if only_active:
        conds.append("is_active = TRUE")
    if not include_nsfw:
        conds.append("is_nsfw = FALSE")
    where = ("WHERE " + " AND ".join(conds)) if conds else ""
    return await db.fetch(
        f"SELECT * FROM categories {where} ORDER BY sort_order, category_id"
    )


async def get_by_slug(slug: str):
    return await db.fetchrow("SELECT * FROM categories WHERE slug=$1", slug)


async def get_by_id(cid: int):
    return await db.fetchrow("SELECT * FROM categories WHERE category_id=$1", cid)


async def create(name: str, emoji: str, is_nsfw: bool):
    slug = slugify(name)
    order = (await db.fetchval("SELECT COALESCE(MAX(sort_order),0)+1 FROM categories")) or 1
    return await db.fetchrow(
        """
        INSERT INTO categories (name, emoji, slug, sort_order, is_nsfw)
        VALUES ($1,$2,$3,$4,$5) RETURNING *
        """,
        name, emoji, slug, order, is_nsfw,
    )


async def update(cid: int, name=None, emoji=None, is_nsfw=None):
    cur = await get_by_id(cid)
    if not cur:
        return None
    name = name if name is not None else cur["name"]
    emoji = emoji if emoji is not None else cur["emoji"]
    is_nsfw = is_nsfw if is_nsfw is not None else cur["is_nsfw"]
    return await db.fetchrow(
        "UPDATE categories SET name=$1, emoji=$2, slug=$3, is_nsfw=$4 WHERE category_id=$5 RETURNING *",
        name, emoji, slugify(name), is_nsfw, cid,
    )


async def delete(cid: int):
    await db.execute("DELETE FROM titles WHERE category_id=$1", cid)
    await db.execute("DELETE FROM categories WHERE category_id=$1", cid)


async def refresh_count(cid: int):
    await db.execute(
        """UPDATE categories SET title_count =
           (SELECT COUNT(*) FROM titles WHERE category_id=$1 AND is_active=TRUE)
           WHERE category_id=$1""",
        cid,
    )
