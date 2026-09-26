"""Small helper utilities: slugify, channel link parsing, formatting."""
import re
import unicodedata


def slugify(text: str) -> str:
    text = unicodedata.normalize("NFKD", text or "")
    text = text.encode("ascii", "ignore").decode("ascii")
    text = text.lower().strip()
    text = re.sub(r"[^a-z0-9]+", "-", text)
    text = re.sub(r"-{2,}", "-", text).strip("-")
    return text or "item"


def normalize_channel_link(raw: str):
    """Return (link, username_or_none). Accepts t.me/x, @x, https://t.me/+invite."""
    raw = (raw or "").strip()
    username = None
    if raw.startswith("@"):
        username = raw[1:]
        return f"https://t.me/{username}", username
    m = re.search(r"t\.me/(\+?[A-Za-z0-9_/-]+)", raw)
    if m:
        token = m.group(1)
        if not token.startswith("+"):
            username = token.split("/")[0]
        link = raw if raw.startswith("http") else f"https://{raw}"
        return link, username
    if raw.startswith("http"):
        return raw, None
    # bare username
    if re.fullmatch(r"[A-Za-z0-9_]{4,}", raw):
        return f"https://t.me/{raw}", raw
    return raw, None


def human_int(n) -> str:
    try:
        n = int(n)
    except (TypeError, ValueError):
        return "0"
    if n >= 1_000_000:
        return f"{n/1_000_000:.1f}M"
    if n >= 1_000:
        return f"{n/1_000:.1f}K"
    return str(n)


def truncate(text: str, length: int = 500) -> str:
    text = text or ""
    return text if len(text) <= length else text[: length - 1] + "…"
