"""Resolve Telegram file_id -> file URL / bytes, with in-memory caching."""
import time
from collections import OrderedDict

import aiohttp

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


# ---------------------------------------------------------------------------
# byte cache — small, bounded; covers are a few dozen KB each
# ---------------------------------------------------------------------------
_bytes_cache: "OrderedDict[str, tuple]" = OrderedDict()
_BYTES_MAX = 120


async def get_bytes(bot, file_id: str):
    """Download a Telegram file once and keep it in memory.

    Returns (body, content_type) or None.
    """
    if not file_id:
        return None
    hit = _bytes_cache.get(file_id)
    if hit is not None:
        _bytes_cache.move_to_end(file_id)
        return hit
    url = await get_url(bot, file_id)
    if not url:
        return None
    try:
        timeout = aiohttp.ClientTimeout(total=20)
        async with aiohttp.ClientSession(timeout=timeout) as sess:
            async with sess.get(url) as resp:
                if resp.status != 200:
                    return None
                body = await resp.read()
        ctype = "image/jpeg"
        low = url.lower()
        if low.endswith(".png"):
            ctype = "image/png"
        elif low.endswith(".webp"):
            ctype = "image/webp"
        result = (body, ctype)
        _bytes_cache[file_id] = result
        while len(_bytes_cache) > _BYTES_MAX:
            _bytes_cache.popitem(last=False)
        return result
    except Exception:  # noqa: BLE001
        return None
