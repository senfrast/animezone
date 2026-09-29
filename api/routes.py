"""REST API endpoint handlers for the Mini App."""
import logging

from aiohttp import web

import config
from api.middleware import json_response
from database.queries import analytics as analytics_q
from database.queries import bookmarks as bookmarks_q
from database.queries import categories as categories_q
from database.queries import settings as settings_q
from database.queries import titles as titles_q
from database.queries import users as users_q
from services import image_service

log = logging.getLogger("api")


async def _show_nsfw(user_id: int) -> bool:
    row = await users_q.get_user(user_id)
    return bool(row and row["show_nsfw"])


# ---------------- init ----------------
async def init(request):
    user_id = request["user_id"]
    tg_user = request["tg_user"]
    await users_q.upsert_user(tg_user)
    row = await users_q.register_app_open(user_id)
    await analytics_q.register_app_open_today()
    show_nsfw = bool(row["show_nsfw"])

    settings = await settings_q.all_settings()
    cats = await categories_q.list_categories(include_nsfw=show_nsfw)
    bm_ids = await bookmarks_q.user_bookmark_ids(user_id)

    return json_response({
        "bot_username": request.get("bot_username", config.BOT_USERNAME),
        "user": {
            "user_id": row["user_id"],
            "first_name": row["first_name"],
            "show_nsfw": show_nsfw,
            "total_bookmarks": row["total_bookmarks"],
            "app_opens_count": row["app_opens_count"],
        },
        "config": {
            "app_name": settings.get("app_name", "AnimeZone"),
            "app_tagline": settings.get("app_tagline", "Your Anime Universe"),
            "max_bookmarks": int(settings.get("max_bookmarks_per_user", "100")),
            "maintenance_mode": settings.get("maintenance_mode", "false") == "true",
            "maintenance_message": settings.get("maintenance_message", ""),
        },
        "categories": [
            {
                "category_id": c["category_id"],
                "name": c["name"],
                "emoji": c["emoji"],
                "slug": c["slug"],
                "title_count": c["title_count"],
                "is_nsfw": c["is_nsfw"],
            }
            for c in cats
        ],
        "bookmark_ids": sorted(bm_ids),
    })


# ---------------- home ----------------
async def home(request):
    user_id = request["user_id"]
    show_nsfw = await _show_nsfw(user_id)
    bm_ids = await bookmarks_q.user_bookmark_ids(user_id)

    def ser(rows):
        return [titles_q.serialize(r, bm_ids) for r in rows]

    featured = ser(await titles_q.featured(show_nsfw, 5))
    trending = ser(await titles_q.trending(show_nsfw, 10))
    recent = ser(await titles_q.recently_added(show_nsfw, 10))
    popular = ser(await titles_q.popular(show_nsfw, 10))
    return json_response({
        "featured": featured,
        "trending": trending,
        "recently_added": recent,
        "popular": popular,
    })


# ---------------- category ----------------
async def category(request):
    user_id = request["user_id"]
    slug = request.match_info["slug"]
    show_nsfw = await _show_nsfw(user_id)

    cat = await categories_q.get_by_slug(slug)
    if not cat or not cat["is_active"]:
        return json_response({"error": "not_found"}, status=404)
    if cat["is_nsfw"] and not show_nsfw:
        return json_response({"error": "forbidden"}, status=403)

    q = request.rel_url.query
    page = max(int(q.get("page", "1") or 1), 1)
    per_page = await settings_q.get_int("items_per_page", 20)
    rows, total = await titles_q.by_category(
        cat["category_id"], show_nsfw, page, per_page,
        sort=q.get("sort", "popular"),
        language=q.get("language", "all"),
        genre=q.get("genre", "all"),
        status=q.get("status", "all"),
    )
    bm_ids = await bookmarks_q.user_bookmark_ids(user_id)
    langs, genres = await titles_q.category_filters(cat["category_id"], show_nsfw)
    total_pages = max((total + per_page - 1) // per_page, 1)
    return json_response({
        "category": {"category_id": cat["category_id"], "name": cat["name"], "emoji": cat["emoji"]},
        "titles": [titles_q.serialize(r, bm_ids) for r in rows],
        "total": total,
        "page": page,
        "total_pages": total_pages,
        "filters": {
            "languages": langs,
            "genres": genres,
            "statuses": ["Ongoing", "Completed"],
        },
    })


# ---------------- title detail ----------------
async def title_detail(request):
    user_id = request["user_id"]
    slug = request.match_info["slug"]
    show_nsfw = await _show_nsfw(user_id)

    row = await titles_q.get_by_slug(slug)
    if not row:
        return json_response({"error": "not_found"}, status=404)
    if row["is_nsfw"] and not show_nsfw:
        return json_response({"error": "forbidden"}, status=403)

    bm_ids = await bookmarks_q.user_bookmark_ids(user_id)
    genres = await titles_q.genres_full(row["title_id"])
    tags = await titles_q.tags(row["title_id"])
    related = await titles_q.related(row["title_id"], row["category_id"], show_nsfw, 10)
    ur = await titles_q.user_rating(user_id, row["title_id"])

    return json_response({
        "title": titles_q.serialize(row, bm_ids),
        "genres": [{"name": g["name"], "emoji": g["emoji"]} for g in genres],
        "tags": tags,
        "related": [titles_q.serialize(r, bm_ids) for r in related],
        "is_bookmarked": row["title_id"] in bm_ids,
        "user_rating": ur,
    })


# ---------------- search ----------------
async def search(request):
    user_id = request["user_id"]
    show_nsfw = await _show_nsfw(user_id)
    query = (request.rel_url.query.get("q", "") or "").strip()
    if len(query) < 1:
        return json_response({"results": [], "query": query, "total": 0})
    rows = await titles_q.search(query, show_nsfw, 20)
    bm_ids = await bookmarks_q.user_bookmark_ids(user_id)
    results = [titles_q.serialize(r, bm_ids) for r in rows]
    return json_response({"results": results, "query": query, "total": len(results)})


# ---------------- bookmarks ----------------
async def bookmarks_list(request):
    user_id = request["user_id"]
    show_nsfw = await _show_nsfw(user_id)
    rows = await bookmarks_q.list_for_user(user_id, show_nsfw)
    bm_ids = await bookmarks_q.user_bookmark_ids(user_id)
    return json_response({"titles": [titles_q.serialize(r, bm_ids) for r in rows]})


async def bookmark_toggle(request):
    user_id = request["user_id"]
    body = await request.json()
    title_id = int(body.get("title_id"))
    max_bm = await settings_q.get_int("max_bookmarks_per_user", 100)
    result = await bookmarks_q.toggle(user_id, title_id, max_bm)
    if result.get("error") == "limit":
        return json_response({"error": "limit", "total": result["total"]}, status=400)
    return json_response(result)


# ---------------- click / rate / request / nsfw ----------------
async def click(request):
    user_id = request["user_id"]
    body = await request.json()
    title_id = int(body.get("title_id"))
    event_type = body.get("event_type", "view")
    if event_type not in ("view", "join", "share"):
        event_type = "view"
    await titles_q.track_event(user_id, title_id, event_type)
    return json_response({"ok": True})


async def rate(request):
    user_id = request["user_id"]
    body = await request.json()
    title_id = int(body.get("title_id"))
    value = int(body.get("rating"))
    if not 1 <= value <= 5:
        return json_response({"error": "invalid_rating"}, status=400)
    row = await titles_q.rate(user_id, title_id, value)
    return json_response({
        "ok": True,
        "new_rating": float(row["rating"]),
        "rating_count": row["rating_count"],
    })


async def content_request(request):
    user_id = request["user_id"]
    body = await request.json()
    title = (body.get("title", "") or "").strip()
    if not title:
        return json_response({"error": "empty"}, status=400)
    row = await analytics_q.add_content_request(user_id, title[:255], body.get("category", ""))
    return json_response({"ok": True, "request_id": row["request_id"]})


async def toggle_nsfw(request):
    user_id = request["user_id"]
    body = await request.json()
    value = bool(body.get("show_nsfw"))
    await users_q.set_nsfw(user_id, value)
    return json_response({"ok": True, "show_nsfw": value})


async def trending_searches(request):
    # Popular titles used as suggested searches
    show_nsfw = await _show_nsfw(request["user_id"])
    rows = await titles_q.popular(show_nsfw, 10)
    return json_response({"terms": [r["title"] for r in rows]})


# ---------------- image ----------------
async def image(request):
    tid = int(request.match_info["title_id"])
    bot = request.app["bot"]
    file_id = await titles_q.get_image_file_id(tid)
    if not file_id:
        raise web.HTTPFound("/assets/placeholder.svg")
    url = await image_service.get_url(bot, file_id)
    if not url:
        raise web.HTTPFound("/assets/placeholder.svg")
    raise web.HTTPFound(url)


def setup_routes(app: web.Application):
    p = config.API_PREFIX
    app.router.add_get(f"{p}/init", init)
    app.router.add_get(f"{p}/home", home)
    app.router.add_get(f"{p}/category/{{slug}}", category)
    app.router.add_get(f"{p}/title/{{slug}}", title_detail)
    app.router.add_get(f"{p}/search", search)
    app.router.add_get(f"{p}/bookmarks", bookmarks_list)
    app.router.add_post(f"{p}/bookmark", bookmark_toggle)
    app.router.add_post(f"{p}/click", click)
    app.router.add_post(f"{p}/rate", rate)
    app.router.add_post(f"{p}/request", content_request)
    app.router.add_post(f"{p}/toggle-nsfw", toggle_nsfw)
    app.router.add_get(f"{p}/trending-searches", trending_searches)
    app.router.add_get(f"{p}/image/{{title_id}}", image)
