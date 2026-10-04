"""Clone-bot registry + per-clone subscriber tracking.

A "clone" is another Telegram bot (its own BotFather token) that runs on the
SAME server/webhook/database as the main bot. Each clone opens the same Mini App
and gives the owner a small admin panel (stats / broadcast / dashboard /
maintenance). Subscribers are tracked per clone because Telegram only lets a bot
message users who pressed Start on THAT specific bot.
"""
from database import pool as db


# ----------------------------- clones -----------------------------
async def create(bot_id: int, token: str, username: str, name: str, added_by: int):
    await db.execute(
        """
        INSERT INTO bot_clones (bot_id, token, username, name, added_by, is_active)
        VALUES ($1,$2,$3,$4,$5,TRUE)
        ON CONFLICT (bot_id) DO UPDATE
          SET token=EXCLUDED.token, username=EXCLUDED.username,
              name=EXCLUDED.name, is_active=TRUE
        """,
        bot_id, token, username, name, added_by,
    )


async def get(bot_id: int):
    return await db.fetchrow("SELECT * FROM bot_clones WHERE bot_id=$1", bot_id)


async def list_all():
    return await db.fetch("SELECT * FROM bot_clones ORDER BY created_at")


async def list_active():
    return await db.fetch("SELECT * FROM bot_clones WHERE is_active=TRUE ORDER BY created_at")


async def delete(bot_id: int):
    """Soft-remove a clone.

    Removing a clone used to hard-DELETE its bot_subscribers rows, which
    destroyed the whole audience the moment an owner removed a bot — and
    re-adding the same token came back empty. Telegram still remembers who
    pressed Start (the bot_id never changes), so we only deactivate here and
    keep the subscriber rows. Re-adding the same bot flips is_active back to
    TRUE (see create()) and the audience + stats return intact.
    """
    await db.execute("UPDATE bot_clones SET is_active=FALSE WHERE bot_id=$1", bot_id)


async def purge(bot_id: int):
    """Permanently erase a clone and its subscribers (irreversible)."""
    await db.execute("DELETE FROM bot_subscribers WHERE bot_id=$1", bot_id)
    await db.execute("DELETE FROM bot_clones WHERE bot_id=$1", bot_id)


async def list_inactive():
    return await db.fetch(
        "SELECT * FROM bot_clones WHERE is_active=FALSE ORDER BY created_at"
    )


async def set_maintenance(bot_id: int, on: bool):
    await db.execute(
        "UPDATE bot_clones SET is_maintenance=$1 WHERE bot_id=$2", on, bot_id
    )


async def count():
    return await db.fetchval("SELECT COUNT(*) FROM bot_clones WHERE is_active=TRUE") or 0


# --------------------------- subscribers --------------------------
async def upsert_subscriber(bot_id: int, user):
    await db.execute(
        """
        INSERT INTO bot_subscribers (bot_id, user_id, first_name, username)
        VALUES ($1,$2,$3,$4)
        ON CONFLICT (bot_id, user_id) DO UPDATE
          SET last_seen=NOW(),
              first_name=EXCLUDED.first_name,
              username=EXCLUDED.username
        """,
        bot_id, user.id, getattr(user, "first_name", None), getattr(user, "username", None),
    )


async def subscriber_ids(bot_id: int):
    rows = await db.fetch(
        "SELECT user_id FROM bot_subscribers WHERE bot_id=$1", bot_id
    )
    return [r["user_id"] for r in rows]


async def sub_count(bot_id: int):
    return await db.fetchval(
        "SELECT COUNT(*) FROM bot_subscribers WHERE bot_id=$1", bot_id
    ) or 0


async def sub_new_today(bot_id: int):
    return await db.fetchval(
        "SELECT COUNT(*) FROM bot_subscribers WHERE bot_id=$1 "
        "AND first_seen::date = CURRENT_DATE",
        bot_id,
    ) or 0


async def sub_active_since(bot_id: int, days: int):
    return await db.fetchval(
        "SELECT COUNT(*) FROM bot_subscribers WHERE bot_id=$1 "
        "AND last_seen > NOW() - ($2 || ' days')::interval",
        bot_id, str(days),
    ) or 0
