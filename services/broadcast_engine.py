"""Rate-limited broadcast sender."""
import asyncio
import logging

from telegram.error import Forbidden, RetryAfter, TelegramError

from database.queries import users as users_q

log = logging.getLogger("broadcast")

RATE_PER_SEC = 25


async def broadcast_to(bot, user_ids, text: str, progress_cb=None):
    """Send `text` to an explicit list of user ids using the given bot.

    Used by clone bots, which can only reach their own subscribers.
    """
    total = len(user_ids)
    sent = failed = blocked = 0
    for i, uid in enumerate(user_ids, 1):
        try:
            await bot.send_message(chat_id=uid, text=text)
            sent += 1
        except Forbidden:
            blocked += 1
        except RetryAfter as e:
            await asyncio.sleep(e.retry_after + 1)
            try:
                await bot.send_message(chat_id=uid, text=text)
                sent += 1
            except TelegramError:
                failed += 1
        except TelegramError:
            failed += 1

        if i % RATE_PER_SEC == 0:
            await asyncio.sleep(1)
            if progress_cb:
                await progress_cb(i, total, sent, failed, blocked)
    return {"total": total, "sent": sent, "failed": failed, "blocked": blocked}


async def broadcast_text(bot, text: str, progress_cb=None):
    user_ids = await users_q.all_user_ids()
    total = len(user_ids)
    sent = failed = blocked = 0
    for i, uid in enumerate(user_ids, 1):
        try:
            await bot.send_message(chat_id=uid, text=text)
            sent += 1
        except Forbidden:
            blocked += 1
        except RetryAfter as e:
            await asyncio.sleep(e.retry_after + 1)
            try:
                await bot.send_message(chat_id=uid, text=text)
                sent += 1
            except TelegramError:
                failed += 1
        except TelegramError:
            failed += 1

        if i % RATE_PER_SEC == 0:
            await asyncio.sleep(1)
            if progress_cb:
                await progress_cb(i, total, sent, failed, blocked)
    return {"total": total, "sent": sent, "failed": failed, "blocked": blocked}
