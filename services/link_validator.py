"""Check whether title channels are still reachable."""
import logging

from telegram.error import TelegramError

from database import pool as db

log = logging.getLogger("linkval")


async def validate_all(bot):
    rows = await db.fetch(
        "SELECT title_id, title, channel_username FROM titles WHERE is_active=TRUE"
    )
    dead = []
    for r in rows:
        username = r["channel_username"]
        if not username:
            continue
        try:
            await bot.get_chat(f"@{username}")
            await db.execute(
                "UPDATE titles SET channel_alive=TRUE, last_checked_at=NOW() WHERE title_id=$1",
                r["title_id"],
            )
        except TelegramError:
            dead.append(r["title"])
            await db.execute(
                "UPDATE titles SET channel_alive=FALSE, last_checked_at=NOW() WHERE title_id=$1",
                r["title_id"],
            )
    return dead
