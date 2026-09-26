"""Input validation helpers."""
import re


def valid_title(text: str) -> bool:
    return bool(text) and 1 <= len(text.strip()) <= 255


def valid_description(text: str) -> bool:
    return len(text or "") <= 500


def valid_channel(text: str) -> bool:
    text = (text or "").strip()
    if text.startswith("@") and len(text) > 4:
        return True
    return bool(re.search(r"t\.me/", text)) or text.startswith("http")


def valid_int(text: str):
    text = (text or "").strip()
    if text.lstrip("-").isdigit():
        return int(text)
    return None
