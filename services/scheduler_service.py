"""APScheduler job definitions."""
import logging

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger

import config
from database import pool as db
from services import link_validator

log = logging.getLogger("scheduler")


def build_scheduler(bot) -> AsyncIOScheduler:
    sched = AsyncIOScheduler(timezone="Asia/Kolkata")

    async def job_validate_links():
        try:
            dead = await link_validator.validate_all(bot)
            if dead and config.ADMIN_IDS:
                msg = "🔗 Dead channels found:\n" + "\n".join(f"• {d}" for d in dead[:30])
                for aid in config.ADMIN_IDS:
                    try:
                        await bot.send_message(aid, msg)
                    except Exception:  # noqa: BLE001
                        pass
        except Exception:  # noqa: BLE001
            log.exception("link validation failed")

    async def job_cleanup():
        try:
            await db.execute(
                "DELETE FROM click_events WHERE created_at < NOW() - INTERVAL '90 days'"
            )
        except Exception:  # noqa: BLE001
            log.exception("cleanup failed")

    async def job_refresh_counts():
        try:
            await db.execute(
                """UPDATE categories c SET title_count =
                   (SELECT COUNT(*) FROM titles t WHERE t.category_id=c.category_id AND t.is_active=TRUE)"""
            )
        except Exception:  # noqa: BLE001
            log.exception("count refresh failed")

    sched.add_job(job_validate_links, IntervalTrigger(hours=6), id="validate_links")
    sched.add_job(job_refresh_counts, IntervalTrigger(hours=1), id="refresh_counts")
    sched.add_job(job_cleanup, CronTrigger(day_of_week="sun", hour=3), id="cleanup")
    return sched
