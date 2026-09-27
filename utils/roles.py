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
