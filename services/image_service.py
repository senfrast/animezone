"""Resolve Telegram file_id -> temporary file URL, with in-memory caching."""
import time

import config

# file_id -> (url, expires_at)
_cache: dict[str, tuple] = {}


async def get_url(bot, file_id: str):
    if not file_id:
        return None
    now = time.time()
    cached = _cache.get(file_id)
    if cached and cached[1] > now:
        return cached[0]
    try:
        f = await bot.get_file(file_id)
        url = f.file_path
        # python-telegram-bot returns an absolute https URL in file_path for cloud bots
        if url and not url.startswith("http"):
            url = f"https://api.telegram.org/file/bot{config.BOT_TOKEN}/{url}"
        _cache[file_id] = (url, now + config.IMAGE_CACHE_TTL)
        return url
    except Exception:  # noqa: BLE001
        return None
