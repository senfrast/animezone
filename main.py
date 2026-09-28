"""AnimeZone entry point: bot + API + static server + scheduler on ONE process."""
import asyncio
import logging
import sys

from telegram import Update
from telegram.ext import (
    ApplicationBuilder,
    CallbackQueryHandler,
    CommandHandler,
)

import config
from database import pool as db
from handlers import start as start_h
from handlers.admin import broadcast as admin_broadcast
from handlers.admin import categories as admin_cats
from handlers.admin import clones as admin_clones
from handlers.admin import edit as admin_edit
from handlers.admin import manage as admin_manage
from handlers.admin import panel as admin_panel
from handlers.admin import titles as admin_titles
from handlers.callbacks import router as callback_router
from handlers.user import settings as user_settings
from services import scheduler_service, server
from utils import roles

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    stream=sys.stdout,
)
log = logging.getLogger("main")


def register_handlers(application):
    # 1-4 ConversationHandlers first
    application.add_handler(admin_titles.build_add_title_conv())
    application.add_handler(admin_cats.build_add_category_conv())
    application.add_handler(admin_broadcast.build_broadcast_conv())
    application.add_handler(admin_manage.build_add_mod_conv())
    application.add_handler(admin_manage.build_restore_conv())
    application.add_handler(admin_edit.build_edit_image_conv())
    application.add_handler(admin_clones.build_add_clone_conv())
    # 5-9 commands
    application.add_handler(CommandHandler("start", start_h.start))
    application.add_handler(CommandHandler("admin", admin_panel.admin_command))
    application.add_handler(CommandHandler("help", start_h.help_cmd))
    application.add_handler(CommandHandler("settings", user_settings.settings_command))
    application.add_handler(CommandHandler("cancel", start_h.cancel))
    application.add_handler(CommandHandler("set", admin_panel.set_command))
    # dynamic slash-commands (feature/delete/etc.)
    application.add_handler(CommandHandler("feature", admin_panel.feature_command))
    application.add_handler(CommandHandler("unfeature", admin_panel.unfeature_command))
    application.add_handler(CommandHandler("delete", admin_panel.del_title_command))
    application.add_handler(CommandHandler("restore", admin_panel.restore_title_command))
    application.add_handler(CommandHandler("trash", admin_panel.trash_command))
    application.add_handler(CommandHandler("delcat", admin_cats.delcat_command))
    application.add_handler(CommandHandler("req_done", admin_panel.req_done_command))
    # these commands include the id suffix (e.g. /feature_12) -> use regex handler
    from telegram.ext import MessageHandler, filters

    application.add_handler(MessageHandler(filters.Regex(r"^/feature_\d+"), admin_panel.feature_command))
    application.add_handler(MessageHandler(filters.Regex(r"^/unfeature_\d+"), admin_panel.unfeature_command))
    application.add_handler(MessageHandler(filters.Regex(r"^/delete_\d+"), admin_panel.del_title_command))
    application.add_handler(MessageHandler(filters.Regex(r"^/restore_\d+"), admin_panel.restore_title_command))
    application.add_handler(MessageHandler(filters.Regex(r"^/edit_\d+"), admin_edit.edit_menu_command))
    application.add_handler(MessageHandler(filters.Regex(r"^/delcat_\d+"), admin_cats.delcat_command))
    application.add_handler(MessageHandler(filters.Regex(r"^/req_done_\d+"), admin_panel.req_done_command))
    # 10 callback router LAST
    application.add_handler(CallbackQueryHandler(callback_router))


async def run():
    log.info("Starting AnimeZone…")
    await db.init_pool()
    await db.run_migrations()
    await roles.refresh()  # load panel-managed moderators into the cache

    application = (
        ApplicationBuilder()
        .token(config.BOT_TOKEN)
        .updater(None)  # we feed updates via webhook queue ourselves
        .build()
    )
    register_handlers(application)

    await application.initialize()
    await application.start()

    # scheduler
    sched = scheduler_service.build_scheduler(application.bot)

    # aiohttp server (webhook + api + static)
    runner = await server.start_server(application)

    # set webhook
    if config.USE_WEBHOOK and config.WEBHOOK_URL:
        url = f"{config.WEBHOOK_URL}{config.WEBHOOK_PATH}"
        await application.bot.set_webhook(
            url=url, allowed_updates=Update.ALL_TYPES, drop_pending_updates=True
        )
        log.info("Webhook set: %s", url)

    # bring any saved clone bots online (sets their webhooks; no polling loops)
    try:
        from services import clone_manager

        await clone_manager.load_all()
    except Exception:  # noqa: BLE001
        log.exception("clone load failed")

    sched.start()
    log.info("🟢 AnimeZone started")

    # notify admins
    try:
        from database.queries import analytics as analytics_q

        stats = await analytics_q.quick_stats()
        for aid in config.ADMIN_IDS:
            try:
                await application.bot.send_message(
                    aid, f"🟢 Bot online. Titles: {stats['titles']}, Users: {stats['users']}"
                )
            except Exception:  # noqa: BLE001
                pass
    except Exception:  # noqa: BLE001
        log.exception("admin notify failed")

    # run forever
    stop = asyncio.Event()
    try:
        await stop.wait()
    finally:
        sched.shutdown(wait=False)
        await application.stop()
        await application.shutdown()
        await runner.cleanup()
        await db.close_pool()


if __name__ == "__main__":
    try:
        asyncio.run(run())
    except (KeyboardInterrupt, SystemExit):
        log.info("Shutting down.")
