"""aiohttp middleware: auth, rate limiting, error handling for /api/v1/*."""
import json
import logging
import time

from aiohttp import web

import config
from api.auth import validate_init_data
from database.queries import users as users_q

log = logging.getLogger("api")

# user_id -> list[timestamps]
_rate: dict[int, list] = {}


def json_response(data, status=200):
    return web.json_response(data, status=status, dumps=lambda o: json.dumps(o, default=str))


def _rate_limited(user_id: int) -> bool:
    now = time.time()
    window = config.RATE_LIMIT_WINDOW
    bucket = [t for t in _rate.get(user_id, []) if now - t < window]
    if len(bucket) >= config.RATE_LIMIT_MAX:
        _rate[user_id] = bucket
        return True
    bucket.append(now)
    _rate[user_id] = bucket
    return False


@web.middleware
async def api_middleware(request: web.Request, handler):
    path = request.path
    # Only guard the API namespace (except image, which is public-ish but still validated lightly)
    if not path.startswith(config.API_PREFIX):
        return await handler(request)

    # image endpoint: allow without strict auth so <img> tags work inside webview
    if path.startswith(config.API_PREFIX + "/image/"):
        try:
            return await handler(request)
        except web.HTTPException:
            raise
        except Exception as e:  # noqa: BLE001
            log.exception("image error")
            return web.HTTPFound("/assets/placeholder.svg")

    init_data = request.headers.get("X-Telegram-Init-Data", "")
    # Accept initData signed by the main bot OR any clone bot (shared Mini App),
    # and remember WHICH bot opened it so share links use the right username.
    from services import clone_manager

    candidates = [(config.BOT_TOKEN, config.BOT_USERNAME), *clone_manager.token_username_pairs()]
    tg_user = None
    bot_username = config.BOT_USERNAME
    last_err = "invalid init data"
    for tok, uname in candidates:
        if not tok:
            continue
        try:
            tg_user = validate_init_data(init_data, bot_token=tok)
            bot_username = uname or config.BOT_USERNAME
            break
        except Exception as e:  # noqa: BLE001
            last_err = str(e)
            continue
    if tg_user is None:
        return json_response({"error": "unauthorized", "detail": last_err}, status=401)
    request["bot_username"] = bot_username

    user_id = tg_user.get("id")
    if not user_id:
        return json_response({"error": "unauthorized"}, status=401)

    if _rate_limited(user_id):
        return json_response({"error": "rate_limited"}, status=429)

    # ensure user row + ban check
    try:
        row = await users_q.get_user(user_id)
        if row is None:
            row = await users_q.upsert_user(tg_user)
        if row and row["is_banned"]:
            return json_response({"error": "banned"}, status=403)
    except Exception:  # noqa: BLE001
        log.exception("user lookup failed")

    request["tg_user"] = tg_user
    request["user_id"] = user_id

    try:
        return await handler(request)
    except web.HTTPException:
        raise
    except Exception as e:  # noqa: BLE001
        log.exception("API handler error on %s", path)
        return json_response({"error": "server_error", "detail": str(e)}, status=500)
