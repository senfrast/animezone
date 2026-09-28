"""aiohttp server: health + webhook + API + static Mini App files."""
import asyncio
import logging
import os

from aiohttp import web
from telegram import Update

import config
from api import routes
from api.middleware import api_middleware, json_response
from database.queries import analytics as analytics_q

log = logging.getLogger("server")

# Keep strong refs to background dispatch tasks so they aren't GC'd mid-flight.
_bg_tasks: set = set()


async def health(request):
    try:
        stats = await analytics_q.quick_stats()
        return json_response({"status": "ok", "titles": stats["titles"], "users": stats["users"]})
    except Exception:  # noqa: BLE001
        return json_response({"status": "ok", "titles": 0, "users": 0})


def make_webhook_handler(application):
    async def webhook(request):
        try:
            data = await request.json()
        except Exception:  # noqa: BLE001
            return web.Response(status=400, text="bad request")
        update = Update.de_json(data, application.bot)
        await application.update_queue.put(update)
        return web.Response(text="ok")

    return webhook


async def clone_webhook(request):
    """Webhook endpoint shared by ALL clone bots: /webhook/clone/{bot_id}."""
    from services import clone_dispatcher, clone_manager

    try:
        bot_id = int(request.match_info["bot_id"])
    except (KeyError, ValueError):
        return web.Response(status=400, text="bad bot id")
    bot = clone_manager.get_bot(bot_id)
    if bot is None:
        return web.Response(status=404, text="unknown bot")
    try:
        data = await request.json()
    except Exception:  # noqa: BLE001
        return web.Response(status=400, text="bad request")
    update = Update.de_json(data, bot)
    # Process in the background so we return 200 to Telegram immediately
    # (broadcasts can take a while).
    task = asyncio.create_task(clone_dispatcher.dispatch(bot, bot_id, update))
    _bg_tasks.add(task)
    task.add_done_callback(_bg_tasks.discard)
    return web.Response(text="ok")


async def serve_index(request):
    return web.FileResponse(os.path.join(config.STATIC_DIR, "index.html"))


def build_app(application) -> web.Application:
    app = web.Application(middlewares=[api_middleware])
    app["bot"] = application.bot
    app["application"] = application

    # 1. health (exact)
    app.router.add_get("/health", health)
    # 2. webhook (exact) — main bot
    app.router.add_post(config.WEBHOOK_PATH, make_webhook_handler(application))
    # 2b. webhook for clone bots (parameterized) — shares this same server
    app.router.add_post("/webhook/clone/{bot_id}", clone_webhook)
    # 3 + 4. API routes (incl. parameterized image)
    routes.setup_routes(app)
    # 5. index
    app.router.add_get("/", serve_index)
    # 6. static dirs (LAST)
    app.router.add_static("/css", os.path.join(config.STATIC_DIR, "css"), name="css")
    app.router.add_static("/js", os.path.join(config.STATIC_DIR, "js"), name="js")
    app.router.add_static("/assets", os.path.join(config.STATIC_DIR, "assets"), name="assets")
    return app


async def start_server(application):
    app = build_app(application)
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, "0.0.0.0", config.PORT)
    await site.start()
    log.info("aiohttp server listening on 0.0.0.0:%s", config.PORT)
    return runner
