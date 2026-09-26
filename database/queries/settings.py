"""Platform settings queries with light in-process caching."""
import time
from database import pool as db

_cache: dict | None = None
_cache_at = 0.0
_TTL = 60


async def all_settings(force=False) -> dict:
    global _cache, _cache_at
    if not force and _cache is not None and (time.time() - _cache_at) < _TTL:
        return _cache
    rows = await db.fetch("SELECT key, value FROM platform_settings")
    _cache = {r["key"]: r["value"] for r in rows}
    _cache_at = time.time()
    return _cache


async def get(key: str, default=None):
    s = await all_settings()
    return s.get(key, default)


async def get_int(key: str, default: int) -> int:
    v = await get(key)
    try:
        return int(v)
    except (TypeError, ValueError):
        return default


async def get_bool(key: str, default=False) -> bool:
    v = await get(key)
    if v is None:
        return default
    return str(v).lower() in ("true", "1", "yes", "on")


async def set(key: str, value: str):
    await db.execute(
        """INSERT INTO platform_settings (key, value, updated_at)
           VALUES ($1,$2,NOW())
           ON CONFLICT (key) DO UPDATE SET value=EXCLUDED.value, updated_at=NOW()""",
        key, str(value),
    )
    await all_settings(force=True)
