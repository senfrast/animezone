"""asyncpg connection pool with auto-reconnection and migration runner."""
import asyncio
import logging
import os

import asyncpg

import config

log = logging.getLogger("db")

_pool: asyncpg.Pool | None = None


async def init_pool(retries: int = 5) -> asyncpg.Pool:
    """Create the global connection pool. Retries on transient failures."""
    global _pool
    if _pool is not None:
        return _pool

    dsn = config.DATABASE_URL
    if not dsn:
        raise RuntimeError("DATABASE_URL is not set")

    last_err = None
    for attempt in range(1, retries + 1):
        try:
            _pool = await asyncpg.create_pool(
                dsn=dsn,
                min_size=2,
                max_size=10,
                command_timeout=30,
                # Supabase pooler (pgbouncer transaction/session) — disable
                # server-side prepared statement caching to stay compatible.
                statement_cache_size=0,
                max_inactive_connection_lifetime=60,
            )
            log.info("Database pool created (attempt %s)", attempt)
            return _pool
        except Exception as e:  # noqa: BLE001
            last_err = e
            log.warning("DB pool attempt %s failed: %s", attempt, e)
            await asyncio.sleep(min(2 * attempt, 10))
    raise RuntimeError(f"Could not create DB pool: {last_err}")


def get_pool() -> asyncpg.Pool:
    if _pool is None:
        raise RuntimeError("Pool not initialised. Call init_pool() first.")
    return _pool


async def close_pool():
    global _pool
    if _pool is not None:
        await _pool.close()
        _pool = None


# --- convenience wrappers with auto-reconnect ---
async def fetch(query: str, *args):
    return await get_pool().fetch(query, *args)


async def fetchrow(query: str, *args):
    return await get_pool().fetchrow(query, *args)


async def fetchval(query: str, *args):
    return await get_pool().fetchval(query, *args)


async def execute(query: str, *args):
    return await get_pool().execute(query, *args)


async def run_migrations():
    """Apply the schema file if the core tables are missing."""
    pool = get_pool()
    exists = await pool.fetchval(
        "SELECT EXISTS (SELECT 1 FROM information_schema.tables "
        "WHERE table_schema='public' AND table_name='titles')"
    )
    if exists:
        log.info("Migrations: schema already present, skipping.")
        return
    path = os.path.join(config.BASE_DIR, "database", "migrations", "001_schema.sql")
    with open(path, "r", encoding="utf-8") as f:
        sql = f.read()
    async with pool.acquire() as conn:
        await conn.execute(sql)
    log.info("Migrations: schema applied.")
