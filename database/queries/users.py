"""User CRUD queries."""
from database import pool as db


async def upsert_user(tg_user: dict, source: str = "organic", referred_by=None):
    """Insert or update a user from a Telegram user dict; returns the row."""
    return await db.fetchrow(
        """
        INSERT INTO users (user_id, username, first_name, last_name, language_code, source, referred_by)
        VALUES ($1,$2,$3,$4,$5,$6,$7)
        ON CONFLICT (user_id) DO UPDATE SET
            username = EXCLUDED.username,
            first_name = EXCLUDED.first_name,
            last_name = EXCLUDED.last_name,
            language_code = COALESCE(EXCLUDED.language_code, users.language_code),
            last_active = NOW()
        RETURNING *
        """,
        tg_user.get("id"),
        tg_user.get("username"),
        tg_user.get("first_name"),
        tg_user.get("last_name"),
        tg_user.get("language_code", "en"),
        source,
        referred_by,
    )


async def get_user(user_id: int):
    return await db.fetchrow("SELECT * FROM users WHERE user_id=$1", user_id)


async def register_app_open(user_id: int):
    return await db.fetchrow(
        """
        UPDATE users
        SET app_opens_count = app_opens_count + 1,
            last_app_open = NOW(),
            last_active = NOW()
        WHERE user_id=$1
        RETURNING *
        """,
        user_id,
    )


async def set_nsfw(user_id: int, value: bool):
    await db.execute("UPDATE users SET show_nsfw=$1 WHERE user_id=$2", value, user_id)


async def set_notifications(user_id: int, value: bool):
    await db.execute(
        "UPDATE users SET notifications_enabled=$1 WHERE user_id=$2", value, user_id
    )


async def count_users() -> int:
    return await db.fetchval("SELECT COUNT(*) FROM users") or 0


async def all_user_ids():
    rows = await db.fetch(
        "SELECT user_id FROM users WHERE is_banned=FALSE ORDER BY user_id"
    )
    return [r["user_id"] for r in rows]


async def is_banned(user_id: int) -> bool:
    v = await db.fetchval("SELECT is_banned FROM users WHERE user_id=$1", user_id)
    return bool(v)
