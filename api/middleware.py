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
    try:
        tg_user = validate_init_data(init_data)
    except Exception as e:  # noqa: BLE001
        return json_response({"error": "unauthorized", "detail": str(e)}, status=401)

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
