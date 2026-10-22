"""Let clone bots send the same cover images as the main bot.

Telegram scopes ``file_id`` to the bot that received the file, so a clone
literally cannot send a photo using the main bot's file_id — the API answers
"wrong file_id or the file is temporarily unavailable".

So the first time a clone needs a cover we hand Telegram a public URL on our
own server; Telegram downloads it and hands us back a file_id that belongs to
*that* clone, which we cache in ``title_bot_images``. Every later send for that
clone is then a plain, instant file_id send — no download, no bandwidth.
"""
import io
import logging

import config
from database import pool as db

log = logging.getLogger("photo_bridge")

MAIN_BOT = 0
# bot_id -> {title_id: file_id}
_mem: dict[int, dict[int, str]] = {}


def public_url(title_id: int) -> str:
    base = (config.WEBHOOK_URL or "").rstrip("/")
    return f"{base}{config.API_PREFIX}/image/{title_id}"


async def photo_for(bot_id: int, title_id: int, main_file_id: str | None):
    """What to pass as `photo=` for this bot.

    Main bot -> its own file_id. Clone -> its cached file_id, else a public URL
    Telegram can fetch.
    """
    if not bot_id or bot_id == MAIN_BOT:
        return main_file_id
    cached = _mem.get(bot_id, {}).get(title_id)
    if cached:
        return cached
    try:
        row = await db.fetchrow(
            "SELECT file_id FROM title_bot_images WHERE title_id=$1 AND bot_id=$2",
            title_id, bot_id,
        )
        if row and row["file_id"]:
            _mem.setdefault(bot_id, {})[title_id] = row["file_id"]
            return row["file_id"]
    except Exception:  # noqa: BLE001
        log.exception("photo cache lookup failed")
    # Not cached yet. Prefer uploading the bytes ourselves: making Telegram
    # fetch our URL costs an extra round trip and used to blow the send
    # timeout, which produced a duplicate text card.
    if main_file_id:
        try:
            from services import clone_manager, image_service

            mb = clone_manager.main_bot()
            if mb is not None:
                data = await image_service.get_bytes(mb, main_file_id)
                if data and data[0]:
                    return io.BytesIO(data[0])
        except Exception:  # noqa: BLE001
            log.exception("could not load cover bytes for title %s", title_id)
    return public_url(title_id) if title_id else main_file_id


async def remember(bot_id: int, title_id: int, message):
    """After a clone sends a cover by URL, keep the file_id it got back."""
    if not bot_id or bot_id == MAIN_BOT or not title_id or message is None:
        return
    photos = getattr(message, "photo", None)
    if not photos:
        return
    file_id = photos[-1].file_id
    if _mem.get(bot_id, {}).get(title_id) == file_id:
        return
    _mem.setdefault(bot_id, {})[title_id] = file_id
    try:
        await db.execute(
            """INSERT INTO title_bot_images (title_id, bot_id, file_id) VALUES ($1,$2,$3)
               ON CONFLICT (title_id, bot_id) DO UPDATE SET file_id = EXCLUDED.file_id""",
            title_id, bot_id, file_id,
        )
    except Exception:  # noqa: BLE001
        log.exception("could not cache clone file_id")


async def forget(title_id: int):
    """Called when a title's artwork changes, so clones re-fetch it."""
    for d in _mem.values():
        d.pop(title_id, None)
    try:
        await db.execute("DELETE FROM title_bot_images WHERE title_id=$1", title_id)
    except Exception:  # noqa: BLE001
        pass
