# 🚀 AnimeZone — Live Deployment Summary

Everything was created **fresh** and is **live** right now.

## 🔗 THE LINK YOU ASKED FOR

**Mini App URL (paste this into your bot settings / BotFather):**

```
https://animezone-h1qw.onrender.com
```

> The plain `animezone.onrender.com` subdomain was already taken, so Render assigned
> `animezone-h1qw.onrender.com`. This is your permanent app URL.

I already configured your bot automatically, so you may not even need to paste it:
- ✅ **Menu button** set to open the Mini App (`🎬 Open AnimeZone`)
- ✅ **Commands** set: `/start`, `/settings`, `/help`, `/admin`
- ✅ **Webhook** set to `https://animezone-h1qw.onrender.com/webhook`

If you still want to set it in **BotFather** manually:
`/mybots` → `YC_Anime_Zone_bot` → **Bot Settings → Menu Button → Configure menu button**
→ paste `https://animezone-h1qw.onrender.com`

## 🧩 What was provisioned (all fresh)

| Service | Detail |
|--------|--------|
| **Supabase project** | `animezone` (ref `affdyfwqkifkurpmafmr`, Singapore region) — schema applied: 14 tables, 3 categories, 17 genres, 9 settings |
| **GitHub repo** | https://github.com/senfrast/animezone (public) |
| **Render web service** | `animezone` (`srv-darvd40jo6nc739jl9t0`, Singapore, free plan) — **LIVE** |
| **Bot** | `@YC_Anime_Zone_bot` — webhook active |

## ✅ Verified working in production
- `GET /health` → `{"status":"ok"}`
- Mini App HTML + CSS + JS + assets served
- `GET /api/v1/init` with valid Telegram initData → 200; without it → **401** (auth works)
- Fuzzy search, bookmarks, ratings, click tracking, image redirect — all tested OK

## 📋 Next steps for YOU

1. **Open the bot** `@YC_Anime_Zone_bot` in Telegram → tap **Open AnimeZone** (or send `/start`).
2. Send `/admin` → **➕ Add New Title** → add 10–20 titles. Mark a few as featured with `/feature_<id>`.
3. **UptimeRobot (recommended):** Render's free tier sleeps after ~15 min idle (≈50s cold start).
   Add an HTTP monitor for `https://animezone-h1qw.onrender.com/health` every 5 minutes to keep it awake.
4. **🔐 ROTATE YOUR SECRETS.** You shared your GitHub PAT, Supabase token, Render token,
   and bot token in chat — regenerate all of them now. The Render env vars will keep the
   app running; just update `BOT_TOKEN` in Render if you rotate it (then it re-sets the webhook on restart).

## 🛠️ How updates work
`git push` to `main` → Render auto-deploys. The database schema auto-applies on first boot
(and is idempotent). Env vars are managed in the Render dashboard.
