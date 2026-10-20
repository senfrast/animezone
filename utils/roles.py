"""Keeps config.DB_MODERATOR_IDS in sync with the bot_admins table."""
import logging

import config
from database.queries import admins as admins_q

log = logging.getLogger("roles")


async def refresh():
    try:
        ids = await admins_q.all_moderator_ids()
        config.DB_MODERATOR_IDS.clear()
        config.DB_MODERATOR_IDS.update(ids)
        log.info("Moderator cache refreshed: %s panel moderators", len(ids))
    except Exception:  # noqa: BLE001
        log.exception("Failed to refresh moderator cache")


# ---------------- per-moderator permission checks ----------------
# Owners always have every permission. Moderators get only what the owner
# switched on in Admin Panel -> Moderators -> (tap a moderator).
async def can(user_id: int, perm: str) -> bool:
    if config.is_owner(user_id):
        return True
    if not config.is_moderator(user_id):
        return False
    try:
        perms = await admins_q.perms_for(user_id)
    except Exception:  # noqa: BLE001
        return False
    return bool(perms.get(perm))


async def publishes_instantly(user_id: int) -> bool:
    """True when this user's uploads skip the approval queue."""
    return await can(user_id, "auto_approve")


async def may_upload_nsfw(user_id: int) -> bool:
    return await can(user_id, "can_nsfw")
