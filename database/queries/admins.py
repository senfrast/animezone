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


# ---------------- per-moderator permissions ----------------
PERMS = ("auto_approve", "can_nsfw", "can_edit", "can_delete")


async def get_moderator(user_id: int):
    return await db.fetchrow("SELECT * FROM bot_admins WHERE user_id=$1", user_id)


async def set_perm(user_id: int, perm: str, value: bool):
    if perm not in PERMS:
        raise ValueError(f"unknown permission: {perm}")
    await db.execute(
        f"UPDATE bot_admins SET {perm} = $1 WHERE user_id = $2", value, user_id
    )


async def toggle_perm(user_id: int, perm: str) -> bool:
    if perm not in PERMS:
        raise ValueError(f"unknown permission: {perm}")
    return await db.fetchval(
        f"UPDATE bot_admins SET {perm} = NOT COALESCE({perm}, FALSE) "
        f"WHERE user_id = $1 RETURNING {perm}",
        user_id,
    )


async def perms_for(user_id: int) -> dict:
    """Permission map for one moderator. Owners implicitly get everything."""
    row = await db.fetchrow(
        "SELECT auto_approve, can_nsfw, can_edit, can_delete FROM bot_admins WHERE user_id=$1",
        user_id,
    )
    if not row:
        return {p: False for p in PERMS}
    return {p: bool(row[p]) for p in PERMS}
