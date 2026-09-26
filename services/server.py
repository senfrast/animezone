"""aiohttp server: health + webhook + API + static Mini App files."""
import logging
import os

from aiohttp import web
from telegram import Update

import config
from api import routes
from api.middleware import api_middleware, json_response
from database.queries import analytics as analytics_q

log = logging.getLogger("server")


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


async def serve_index(request):
    return web.FileResponse(os.path.join(config.STATIC_DIR, "index.html"))


def build_app(application) -> web.Application:
    app = web.Application(middlewares=[api_middleware])
    app["bot"] = application.bot
    app["application"] = application

    # 1. health (exact)
    app.router.add_get("/health", health)
    # 2. webhook (exact)
    app.router.add_post(config.WEBHOOK_PATH, make_webhook_handler(application))
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
