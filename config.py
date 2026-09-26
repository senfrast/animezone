"""Central configuration loaded from environment variables."""
import os
from dotenv import load_dotenv

load_dotenv()


def _admin_ids():
    raw = os.getenv("ADMIN_IDS", "")
    ids = set()
    for part in raw.replace(" ", "").split(","):
        if part.isdigit():
            ids.add(int(part))
    return ids


BOT_TOKEN = os.getenv("BOT_TOKEN", "")
ADMIN_IDS = _admin_ids()
BOT_USERNAME = os.getenv("BOT_USERNAME", "AnimeZoneBot")

DATABASE_URL = os.getenv("DATABASE_URL", "")

PORT = int(os.getenv("PORT", "10000"))
WEBHOOK_URL = os.getenv("WEBHOOK_URL", "").rstrip("/")
MINI_APP_URL = os.getenv("MINI_APP_URL", WEBHOOK_URL).rstrip("/")
USE_WEBHOOK = os.getenv("USE_WEBHOOK", "true").lower() == "true"

WEBHOOK_PATH = "/webhook"
API_PREFIX = "/api/v1"

# Rate limiting
RATE_LIMIT_MAX = 60          # requests
RATE_LIMIT_WINDOW = 60       # seconds

# Image URL cache TTL (seconds)
IMAGE_CACHE_TTL = 30 * 60

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
STATIC_DIR = os.path.join(BASE_DIR, "static")


def is_admin(user_id: int) -> bool:
    return user_id in ADMIN_IDS
