"""Scheduled message deletion.

Search results are throwaway: the card and the query that produced it are
removed a few minutes later so private chats don't fill up with old lookups.

Two layers, because Render restarts:
  * an in-process asyncio timer, so deletion is punctual to the second;
  * a row in ``pending_deletions`` swept every 30 s, so a restart (deploy,
    idle spin-down) still cleans up messages whose timer died with the process.

Whichever gets there first removes the DB row, so the other becomes a no-op.
"""
import asyncio
import logging
from datetime import datetime, timedelta, timezone

from database import pool as db

log = logging.getLogger("autodelete")

# how long a search result survives
TTL_SECONDS = 300  # 5 minutes

MAIN_BOT = 0  # bot_id used for the main bot's own messages

def set_main_bot(bot):
    """Registered at startup by main.py."""
    from services import clone_manager

    clone_manager.set_main_bot(bot)


def _resolve_bot(bot_id: int):
    """bot_id -> a telegram.Bot, or None if that clone is gone."""
    from services import clone_manager

    if not bot_id or bot_id == MAIN_BOT:
        return clone_manager.main_bot()
    return clone_manager.get_bot(bot_id)


async def _delete_now(bot, chat_id: int, message_id: int) -> bool:
    try:
        await bot.delete_message(chat_id=chat_id, message_id=message_id)
        return True
    except Exception as e:  # noqa: BLE001 — already gone / too old / no rights
        log.debug("delete %s/%s failed: %s", chat_id, message_id, e)
        return False


async def _forget(chat_id: int, message_id: int):
    try:
        await db.execute(
            "DELETE FROM pending_deletions WHERE chat_id=$1 AND message_id=$2",
            chat_id, message_id,
        )
    except Exception:  # noqa: BLE001
        pass


async def _timer(bot_id: int, chat_id: int, message_id: int, delay: int):
    try:
        await asyncio.sleep(delay)
        bot = _resolve_bot(bot_id)
        if bot is not None:
            await _delete_now(bot, chat_id, message_id)
        await _forget(chat_id, message_id)
    except asyncio.CancelledError:  # shutting down — the sweeper will finish the job
        raise
    except Exception:  # noqa: BLE001
        log.exception("autodelete timer failed")


async def schedule(bot_id: int, chat_id: int, message_ids, seconds: int = TTL_SECONDS):
    """Queue one or more messages in `chat_id` for deletion in `seconds`."""
    ids = [m for m in (message_ids if isinstance(message_ids, (list, tuple, set)) else [message_ids]) if m]
    if not ids:
        return
    due = datetime.now(timezone.utc) + timedelta(seconds=seconds)
    for mid in ids:
        try:
            await db.execute(
                """INSERT INTO pending_deletions (bot_id, chat_id, message_id, delete_at)
                   VALUES ($1,$2,$3,$4) ON CONFLICT DO NOTHING""",
                int(bot_id or 0), int(chat_id), int(mid), due,
            )
        except Exception:  # noqa: BLE001 — the in-process timer still covers it
            log.exception("could not persist pending deletion")
        asyncio.create_task(_timer(int(bot_id or 0), int(chat_id), int(mid), seconds))


async def sweep():
    """Delete everything that is due. Safety net for messages whose timer died."""
    try:
        rows = await db.fetch(
            """SELECT bot_id, chat_id, message_id FROM pending_deletions
               WHERE delete_at <= NOW() ORDER BY delete_at LIMIT 200"""
        )
    except Exception:  # noqa: BLE001
        return 0
    done = 0
    for r in rows or []:
        bot = _resolve_bot(r["bot_id"])
        if bot is not None:
            await _delete_now(bot, r["chat_id"], r["message_id"])
            done += 1
        await _forget(r["chat_id"], r["message_id"])
    if done:
        log.info("autodelete swept %d message(s)", done)
    return done
