"""Plain-text title lookup in the bot chat.

Someone sends "atack on titen" or "jjk" and gets the same card they would get
from a share link — cover, details and an "Open This Title" button that opens
the Mini App directly on that title.

Adult queries are routed to the Adults Nation shelf instead of being matched
against the normal catalogue.
"""
import html
import logging

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update, WebAppInfo
from telegram.ext import ContextTypes

import config
from database.queries import titles as titles_q
from database.queries import users as users_q
from services import title_search
from utils import helpers

log = logging.getLogger("text_search")

# below this we don't claim a match
THRESHOLD = 0.62
# a result this good is shown on its own; otherwise we offer a choice
STRONG = 0.80
ADULT_CATEGORY_SLUG = "adults-nation"


def esc(v) -> str:
    return html.escape(str(v or ""), quote=False)


def _title_kb(row, alternatives=None, is_admin=False):
    url = f"{config.MINI_APP_URL}#/title/{row['slug']}"
    rows = [[InlineKeyboardButton("🎬 Open This Title", web_app=WebAppInfo(url=url))]]
    if row.get("channel_link"):
        rows.append([InlineKeyboardButton("📥 Join Channel", url=row["channel_link"])])
    for alt, _s in (alternatives or [])[:4]:
        rows.append([InlineKeyboardButton(f"🔎 {alt['title'][:34]}",
                                          callback_data=f"ts:{alt['title_id']}")])
    rows.append([InlineKeyboardButton("🔍 Search in App",
                                      web_app=WebAppInfo(url=f"{config.MINI_APP_URL}#/search"))])
    return InlineKeyboardMarkup(rows)


def _card(row) -> str:
    unit = helpers.unit_label(row.get("category_name"), row.get("episode_count"))
    bits = [f"{row.get('category_emoji') or '📂'} {esc(row.get('category_name'))}"]
    if row.get("status"):
        bits.append("✅ Completed" if str(row["status"]).lower() == "completed" else "🟢 Ongoing")
    if unit:
        bits.append(unit)
    text = f"🎬 <b>{esc(row['title'])}</b>\n{' · '.join(bits)}"
    if row.get("is_nsfw"):
        text += "\n🔞 <i>Adult — 18+ only</i>"
    text += "\n\nTap below to open it 👇"
    return text


async def _send_card(message, tid: int, alternatives=None):
    row = await titles_q.get_full(tid)
    if not row:
        await message.reply_text("😕 That title is no longer available.")
        return
    row = dict(row)
    kb = _title_kb(row, alternatives)
    if row.get("image_file_id"):
        try:
            await message.reply_photo(photo=row["image_file_id"], caption=_card(row),
                                      reply_markup=kb, parse_mode="HTML")
            return
        except Exception:  # noqa: BLE001 — fall back to text if the file_id died
            log.warning("cover send failed for %s", tid)
    await message.reply_text(_card(row), reply_markup=kb, parse_mode="HTML",
                             disable_web_page_preview=True)


def _adult_shelf_kb():
    url = f"{config.MINI_APP_URL}#/category/{ADULT_CATEGORY_SLUG}"
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🔞 Open Adults Nation", web_app=WebAppInfo(url=url))],
        [InlineKeyboardButton("⚙️ Settings", callback_data="usettings")],
    ])


async def handle(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Entry point for any plain text message that nothing else claimed."""
    msg = update.message
    if not msg or not msg.text:
        return
    query = msg.text.strip()
    if len(query) < 2 or query.startswith("/"):
        return
    # never hijack an in-progress admin flow
    for key in ("new_title", "new_cat", "bc_text", "edit_img_tid", "tm_await"):
        if key in context.user_data:
            return

    uid = update.effective_user.id
    try:
        u = await users_q.get_user(uid)
        show_nsfw = bool(u and u["show_nsfw"])
    except Exception:  # noqa: BLE001
        show_nsfw = False

    results, adult = await title_search.find(titles_q, query, show_nsfw, limit=6)
    best = results[0] if results else None

    # ---------- adult intent ----------
    if adult and (not best or best[1] < THRESHOLD or not best[0]["is_nsfw"]):
        if not show_nsfw:
            await msg.reply_text(
                "🔞 <b>Adult content is turned off</b>\n\n"
                "Turn on 18+ in Settings to browse <b>Adults Nation</b>.",
                reply_markup=InlineKeyboardMarkup(
                    [[InlineKeyboardButton("⚙️ Open Settings", callback_data="usettings")]]),
                parse_mode="HTML")
            return
        await msg.reply_text(
            "🔞 <b>Adults Nation</b>\n\nHere's the 18+ shelf — browse everything inside 👇",
            reply_markup=_adult_shelf_kb(), parse_mode="HTML")
        return

    # ---------- nothing close enough ----------
    if not best or best[1] < THRESHOLD:
        near = [r for r in results if r[1] >= 0.45][:4]
        kb = [[InlineKeyboardButton(f"🔎 {r['title'][:34]}", callback_data=f"ts:{r['title_id']}")]
              for r, _s in near]
        kb.append([InlineKeyboardButton(
            "🔍 Search in App",
            web_app=WebAppInfo(url=f"{config.MINI_APP_URL}#/search"))])
        text = (f"😕 Couldn't find <b>{esc(query)}</b>.\n\n"
                + ("Did you mean one of these?" if near
                   else "Try a different spelling, or browse the app."))
        await msg.reply_text(text, reply_markup=InlineKeyboardMarkup(kb), parse_mode="HTML")
        return

    # ---------- a clear winner ----------
    alts = [r for r in results[1:] if r[1] >= THRESHOLD]
    if best[1] >= STRONG:
        await _send_card(msg, best[0]["title_id"], alts)
        return

    # ---------- plausible but not certain: offer the options ----------
    kb = [[InlineKeyboardButton(f"🎬 {best[0]['title'][:34]}",
                                callback_data=f"ts:{best[0]['title_id']}")]]
    for r, _s in alts[:4]:
        kb.append([InlineKeyboardButton(f"🔎 {r['title'][:34]}", callback_data=f"ts:{r['title_id']}")])
    kb.append([InlineKeyboardButton(
        "🔍 Search in App", web_app=WebAppInfo(url=f"{config.MINI_APP_URL}#/search"))])
    await msg.reply_text(
        f"🔎 Closest matches for <b>{esc(query)}</b> — pick one:",
        reply_markup=InlineKeyboardMarkup(kb), parse_mode="HTML")


async def on_pick(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """User tapped one of the suggested titles."""
    q = update.callback_query
    await q.answer()
    tid = int(q.data.split(":")[1])
    await _send_card(q.message, tid)
