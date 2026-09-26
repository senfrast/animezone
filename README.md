# 🎌 AnimeZone — Telegram Mini App Content Discovery Platform

A Netflix-style content catalog that lives **inside Telegram**. Browse anime, movies
and web series — each linked to a Telegram channel — from a fast, dark-themed Mini App.
Bot + REST API + Mini App frontend all run from a **single** Python process.

## Architecture

One `aiohttp` server handles everything (same origin, no CORS):

```
POST /webhook          → Telegram bot updates
GET  /health           → UptimeRobot health check
GET/POST /api/v1/*     → REST API for the Mini App
GET  /                 → Mini App (static/index.html)
GET  /css /js /assets  → Static frontend files
```

- **Backend:** Python 3.11+, `python-telegram-bot` 21.3, `aiohttp`, `asyncpg`, `APScheduler`
- **Database:** Supabase PostgreSQL
- **Frontend:** Vanilla HTML/CSS/JS (no frameworks) — instant load
- **Images:** stored as Telegram `file_id`, served via 302 redirect to Telegram's CDN (zero storage cost)
- **Auth:** every API call validates Telegram `initData` (HMAC-SHA256)
- **18+ filtering:** enforced at the **database query level**

## Environment variables

See `.env.example`:

| Key | Description |
|-----|-------------|
| `BOT_TOKEN` | Telegram bot token |
| `ADMIN_IDS` | Comma-separated admin Telegram user IDs |
| `BOT_USERNAME` | Bot username (without @) |
| `DATABASE_URL` | Supabase Postgres connection string |
| `WEBHOOK_URL` | Public base URL (Render service URL) |
| `MINI_APP_URL` | Usually same as `WEBHOOK_URL` |
| `PORT` | Port to bind (Render sets this) |
| `USE_WEBHOOK` | `true` in production |

## Run locally

```bash
pip install -r requirements.txt
cp .env.example .env   # fill values
python main.py
```

## Deploy (Render)

`render.yaml` is included. Create a Web Service from this repo, set the env vars,
and Render will run `python main.py`. Point BotFather's menu button and
`/setmenubutton` Web App URL to your Render URL.

## Admin

- `/admin` — full panel (stats, categories, add title, featured, broadcast, analytics, export, link validation)
- Add-title is a step-by-step conversation (name → image → description → channel → category → genres → language → status → episodes → 18+ → confirm)
- `/settings` — user 18+ & notification toggles

Built to be beautiful, fast, and bulletproof. 🎌
