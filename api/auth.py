"""Telegram WebApp initData validation (HMAC-SHA256)."""
import hashlib
import hmac
import json
import time
import urllib.parse

import config


def validate_init_data(init_data: str, bot_token: str = None, max_age: int = 86400) -> dict:
    """Validate initData string and return the parsed Telegram user dict.

    Raises ValueError on any validation failure.
    """
    bot_token = bot_token or config.BOT_TOKEN
    if not init_data:
        raise ValueError("empty init data")

    parsed = dict(urllib.parse.parse_qsl(init_data, keep_blank_values=True))
    received_hash = parsed.pop("hash", "")
    if not received_hash:
        raise ValueError("missing hash")

    data_check_string = "\n".join(f"{k}={v}" for k, v in sorted(parsed.items()))
    secret_key = hmac.new(b"WebAppData", bot_token.encode(), hashlib.sha256).digest()
    computed_hash = hmac.new(
        secret_key, data_check_string.encode(), hashlib.sha256
    ).hexdigest()

    if not hmac.compare_digest(computed_hash, received_hash):
        raise ValueError("invalid init data hash")

    # freshness check
    auth_date = parsed.get("auth_date")
    if auth_date and auth_date.isdigit():
        if time.time() - int(auth_date) > max_age:
            raise ValueError("init data expired")

    user_raw = parsed.get("user")
    if not user_raw:
        raise ValueError("no user in init data")
    return json.loads(user_raw)


def validate_init_data_multi(init_data: str, tokens, max_age: int = 86400) -> dict:
    """Validate initData against several bot tokens (main bot + clones).

    The Mini App is shared by the main bot and every clone. Each bot signs its
    initData with its OWN token, so we accept the request if ANY known token
    verifies it. Returns the parsed user on the first match.
    """
    last_err = None
    for t in tokens:
        if not t:
            continue
        try:
            return validate_init_data(init_data, bot_token=t, max_age=max_age)
        except ValueError as e:
            last_err = e
    raise last_err or ValueError("invalid init data")
