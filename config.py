"""Central configuration loaded from environment variables."""
import os
from dotenv import load_dotenv

load_dotenv()


def _ids(name):
    raw = os.getenv(name, "")
    ids = set()
    for part in raw.replace(" ", "").split(","):
        if part.isdigit():
            ids.add(int(part))
    return ids


BOT_TOKEN = os.getenv("BOT_TOKEN", "")

# ROLES:
#   OWNER_IDS      -> full admins (approve/reject, broadcast, settings, delete, etc.)
#   MODERATOR_IDS  -> limited admins (can ONLY submit titles; go to approval queue)
# ADMIN_IDS is the union (anyone who can reach the admin panel at all).
OWNER_IDS = _ids("ADMIN_IDS")               # your existing var stays the OWNER list
ENV_MODERATOR_IDS = _ids("MODERATOR_IDS")   # optional moderators from env
DB_MODERATOR_IDS = set()                     # moderators added via the admin panel (runtime cache)
# Backwards-compatible alias
MODERATOR_IDS = ENV_MODERATOR_IDS
ADMIN_IDS = OWNER_IDS | ENV_MODERATOR_IDS

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


def is_owner(user_id: int) -> bool:
    """Full-power admin who approves content and manages the platform.
    Owners come from the ADMIN_IDS env var and are permanent (cannot be removed
    from the panel) — this guarantees you can never lock yourself out."""
    return user_id in OWNER_IDS


def is_moderator(user_id: int) -> bool:
    """Limited sub-admin: may submit titles for approval only.
    Moderators come from the env var OR the panel-managed DB cache."""
    if user_id in OWNER_IDS:
        return False
    return user_id in ENV_MODERATOR_IDS or user_id in DB_MODERATOR_IDS


def is_admin(user_id: int) -> bool:
    """Any admin (owner or moderator) — can reach the admin panel."""
    return is_owner(user_id) or is_moderator(user_id)
