"""In-memory registry of clone bots.

Design goals (memory-efficient, no extra infrastructure):
  * ONE lightweight ``telegram.Bot`` per clone token (tens of KB each) — NOT a
    full Application/Updater. No polling loops => zero idle CPU.
  * All clones share the same aiohttp server, the same DB pool and the same
    Mini App. Adding a clone only sets a webhook; it never spawns a process.
"""
import logging

from telegram import Bot, Update

import config
from database.queries import clones as clones_q

log = logging.getLogger("clones")

# bot_id -> telegram.Bot  (live API clients)
_bots: dict[int, Bot] = {}
# bot_id -> dict row cache (name/username/is_maintenance)
_clones: dict[int, dict] = {}


def _webhook_url(bot_id: int) -> str:
    return f"{config.WEBHOOK_URL}/webhook/clone/{bot_id}"


async def _make_bot(token: str) -> Bot:
    bot = Bot(token)
    await bot.initialize()
    return bot


async def _register(row: dict, set_webhook: bool = True):
    bot = await _make_bot(row["token"])
    _bots[row["bot_id"]] = bot
    _clones[row["bot_id"]] = dict(row)
    if set_webhook:
        try:
            await bot.set_webhook(
                url=_webhook_url(row["bot_id"]),
                allowed_updates=Update.ALL_TYPES,
                drop_pending_updates=True,
            )
        except Exception:  # noqa: BLE001
            log.exception("set_webhook failed for clone %s", row["bot_id"])
    return bot


async def load_all():
    """Called once on startup: wire up every saved clone."""
    rows = await clones_q.list_active()
    for r in rows:
        try:
            await _register(dict(r))
            log.info("Clone online: @%s (%s)", r["username"], r["bot_id"])
        except Exception:  # noqa: BLE001
            log.exception("Failed to load clone %s", r["bot_id"])
    if rows:
        log.info("Loaded %d clone bot(s).", len(rows))


async def add(token: str, added_by: int):
    """Validate a BotFather token, persist it and bring it online immediately.

    Returns the getMe result (has .id, .username, .first_name). Raises on a bad
    token so the caller can show the error.
    """
    tmp = await _make_bot(token)
    me = await tmp.get_me()
    if me.id in _bots:
        # already registered — refresh token/webhook
        try:
            await tmp.shutdown()
        except Exception:  # noqa: BLE001
            pass
        await clones_q.create(me.id, token, me.username, me.first_name, added_by)
        row = await clones_q.get(me.id)
        await _register(dict(row))
        return me
    await clones_q.create(me.id, token, me.username, me.first_name, added_by)
    row = await clones_q.get(me.id)
    _bots[me.id] = tmp
    _clones[me.id] = dict(row)
    try:
        await tmp.set_webhook(
            url=_webhook_url(me.id),
            allowed_updates=Update.ALL_TYPES,
            drop_pending_updates=True,
        )
    except Exception:  # noqa: BLE001
        log.exception("set_webhook failed for new clone %s", me.id)
    return me


async def remove(bot_id: int):
    bot = _bots.get(bot_id)
    if bot is not None:
        try:
            await bot.delete_webhook(drop_pending_updates=True)
        except Exception:  # noqa: BLE001
            pass
        try:
            await bot.shutdown()
        except Exception:  # noqa: BLE001
            pass
    _bots.pop(bot_id, None)
    _clones.pop(bot_id, None)
    await clones_q.delete(bot_id)


async def set_maintenance(bot_id: int, on: bool):
    await clones_q.set_maintenance(bot_id, on)
    if bot_id in _clones:
        _clones[bot_id]["is_maintenance"] = on


def get_bot(bot_id: int):
    return _bots.get(bot_id)


def get_clone(bot_id: int):
    return _clones.get(bot_id)


def is_maintenance(bot_id: int) -> bool:
    c = _clones.get(bot_id)
    return bool(c and c.get("is_maintenance"))


def all_tokens() -> list[str]:
    """Tokens of every loaded clone (used to validate Mini App initData)."""
    return [c["token"] for c in _clones.values() if c.get("token")]


def token_username_pairs() -> list[tuple]:
    """(token, username) for each loaded clone — lets the API identify which
    bot opened the Mini App so share links use the correct @username."""
    return [(c["token"], c.get("username")) for c in _clones.values() if c.get("token")]
