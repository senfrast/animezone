"""Panel-managed moderators (stored in DB, not env vars)."""
from database import pool as db


async def list_moderators():
    return await db.fetch(
        "SELECT * FROM bot_admins WHERE role='moderator' ORDER BY added_at DESC"
    )


async def all_moderator_ids():
    rows = await db.fetch("SELECT user_id FROM bot_admins WHERE role='moderator'")
    return [r["user_id"] for r in rows]


async def add_moderator(user_id: int, first_name=None, username=None, added_by=None):
    return await db.fetchrow(
        """
        INSERT INTO bot_admins (user_id, role, first_name, username, added_by)
        VALUES ($1,'moderator',$2,$3,$4)
        ON CONFLICT (user_id) DO UPDATE SET
            role='moderator', first_name=EXCLUDED.first_name, username=EXCLUDED.username
        RETURNING *
        """,
        user_id, first_name, username, added_by,
    )


async def remove_moderator(user_id: int):
    await db.execute("DELETE FROM bot_admins WHERE user_id=$1", user_id)


async def exists(user_id: int) -> bool:
    return bool(await db.fetchval("SELECT 1 FROM bot_admins WHERE user_id=$1", user_id))
