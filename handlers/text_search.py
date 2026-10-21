"""Plain-text title lookup, shared by the main bot and every clone.

Someone sends "atack on titen" or "jjk" and gets the same card a share link
produces — cover, details and an "Open This Title" button straight into the
Mini App. Adult queries are routed to the Adults Nation shelf instead.

Everything here takes a plain ``telegram.Bot``, so the clone dispatcher (which
has no PTB Application) can use the exact same code. Buttons are built with
``WebAppInfo``/``callback_data`` only — never a hard-coded @username — so a
card sent by a clone opens *that clone's* Mini App session, not the main bot's.
"""
import html
import logging

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update, WebAppInfo
from telegram.ext import ContextTypes

import config
from database.queries import titles as titles_q
from database.queries import users as users_q
from services import autodelete, photo_bridge, title_search

log = logging.getLogger("text_search")

THRESHOLD = 0.62   # below this we don't claim a match
STRONG = 0.80      # at or above this we answer with the card directly
ADULT_CATEGORY_SLUG = "adults-nation"

# admin flows that own the user's next message — never answer on top of them
BUSY_KEYS = ("new_title", "new_cat", "bc_text", "edit_img_tid", "tm_await")

_TTL_NOTE = "\n\n<i>🗑 This message disappears in 5 minutes.</i>"


def esc(v) -> str:
    return html.escape(str(v or ""), quote=False)


# --------------------------------------------------------------------------
# keyboards — identical for main bot and clones
# --------------------------------------------------------------------------
def _open_btn(path: str, label: str):
    return InlineKeyboardButton(label, web_app=WebAppInfo(url=f"{config.MINI_APP_URL}#{path}"))


def _title_kb(row, alternatives=None):
    rows = [[_open_btn(f"/title/{row['slug']}", "🎬 Open This Title")]]
    if row.get("channel_link"):
        rows.append([InlineKeyboardButton("📥 Join Channel", url=row["channel_link"])])
    for alt, _s in (alternatives or [])[:4]:
        rows.append([InlineKeyboardButton(f"🔎 {alt['title'][:34]}",
                                          callback_data=f"ts:{alt['title_id']}")])
    rows.append([_open_btn("/search", "🔍 Search in App")])
    return InlineKeyboardMarkup(rows)


def _adult_shelf_kb():
    return InlineKeyboardMarkup([
        [_open_btn(f"/category/{ADULT_CATEGORY_SLUG}", "🔞 Open Adults Nation")],
        [InlineKeyboardButton("⚙️ Settings", callback_data="usettings")],
    ])


def _card(row) -> str:
    from utils import helpers

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


# --------------------------------------------------------------------------
# sending — bot-agnostic
# --------------------------------------------------------------------------
async def _send(bot, bot_id, chat_id, text, kb, title_id=None, file_id=None):
    """Send the card with its cover.

    A clone can't use the main bot's file_id, so photo_bridge hands it a public
    URL the first time and caches the clone's own file_id afterwards.
    """
    photo = await photo_bridge.photo_for(bot_id, title_id, file_id) if (title_id or file_id) else None
    if photo:
        try:
            m = await bot.send_photo(chat_id=chat_id, photo=photo, caption=text,
                                     reply_markup=kb, parse_mode="HTML")
            await photo_bridge.remember(bot_id, title_id, m)
            return m
        except Exception:  # noqa: BLE001
            log.warning("cover send failed (bot %s, title %s)", bot_id, title_id, exc_info=True)
    return await bot.send_message(chat_id=chat_id, text=text, reply_markup=kb,
                                  parse_mode="HTML", disable_web_page_preview=True)


async def send_title_card(bot, bot_id, chat_id, tid, alternatives=None, schedule=True):
    """Send one title's card. Used by search hits and by the 'ts:' picker.

    `schedule=False` lets the caller batch this message with the user's query
    into a single auto-delete call.
    """
    row = await titles_q.get_full(tid)
    if not row:
        m = await bot.send_message(chat_id=chat_id, text="😕 That title is no longer available.")
    else:
        row = dict(row)
        m = await _send(bot, bot_id, chat_id, _card(row) + _TTL_NOTE,
                        _title_kb(row, alternatives),
                        title_id=row.get("title_id") or tid,
                        file_id=row.get("image_file_id"))
    if schedule:
        await autodelete.schedule(bot_id, chat_id, m.message_id)
    return m


async def answer(bot, bot_id, chat_id, uid, query, query_message_id=None):
    """Run a text search and reply. Works for the main bot and any clone.

    `bot_id` is 0 for the main bot, otherwise the clone's id — it tells the
    auto-deleter which bot must remove the message later.
    """
    query = (query or "").strip()
    if len(query) < 2 or query.startswith("/"):
        return

    try:
        u = await users_q.get_user(uid)
        show_nsfw = bool(u and u["show_nsfw"])
    except Exception:  # noqa: BLE001
        show_nsfw = False

    results, adult = await title_search.find(titles_q, query, show_nsfw, limit=6)
    best = results[0] if results else None
    sent = None

    # ---------- adult intent, no specific adult title matched ----------
    if adult and (not best or best[1] < THRESHOLD or not best[0]["is_nsfw"]):
        if not show_nsfw:
            sent = await bot.send_message(
                chat_id=chat_id,
                text="🔞 <b>Adult content is turned off</b>\n\n"
                     "Turn on 18+ in Settings to browse <b>Adults Nation</b>." + _TTL_NOTE,
                reply_markup=InlineKeyboardMarkup(
                    [[InlineKeyboardButton("⚙️ Open Settings", callback_data="usettings")]]),
                parse_mode="HTML")
        else:
            sent = await bot.send_message(
                chat_id=chat_id,
                text="🔞 <b>Adults Nation</b>\n\nHere's the 18+ shelf — "
                     "browse everything inside 👇" + _TTL_NOTE,
                reply_markup=_adult_shelf_kb(), parse_mode="HTML")

    # ---------- nothing close enough ----------
    elif not best or best[1] < THRESHOLD:
        near = [r for r in results if r[1] >= 0.45][:4]
        kb = [[InlineKeyboardButton(f"🔎 {r['title'][:34]}", callback_data=f"ts:{r['title_id']}")]
              for r, _s in near]
        kb.append([_open_btn("/search", "🔍 Search in App")])
        sent = await bot.send_message(
            chat_id=chat_id,
            text=(f"😕 Couldn't find <b>{esc(query)}</b>.\n\n"
                  + ("Did you mean one of these?" if near
                     else "Try a different spelling, or browse the app.") + _TTL_NOTE),
            reply_markup=InlineKeyboardMarkup(kb), parse_mode="HTML")

    # ---------- a clear winner ----------
    elif best[1] >= STRONG:
        alts = [r for r in results[1:] if r[1] >= THRESHOLD]
        sent = await send_title_card(bot, bot_id, chat_id, best[0]["title_id"], alts,
                                     schedule=False)

    # ---------- plausible but not certain: let them choose ----------
    else:
        alts = [r for r in results[1:] if r[1] >= THRESHOLD]
        kb = [[InlineKeyboardButton(f"🎬 {best[0]['title'][:34]}",
                                    callback_data=f"ts:{best[0]['title_id']}")]]
        for r, _s in alts[:4]:
            kb.append([InlineKeyboardButton(f"🔎 {r['title'][:34]}",
                                            callback_data=f"ts:{r['title_id']}")])
        kb.append([_open_btn("/search", "🔍 Search in App")])
        sent = await bot.send_message(
            chat_id=chat_id,
            text=f"🔎 Closest matches for <b>{esc(query)}</b> — pick one:" + _TTL_NOTE,
            reply_markup=InlineKeyboardMarkup(kb), parse_mode="HTML")

    # the reply and the query that caused it both go away after 5 minutes
    ids = [m for m in (sent.message_id if sent else None, query_message_id) if m]
    await autodelete.schedule(bot_id, chat_id, ids)
    return sent


# --------------------------------------------------------------------------
# main-bot entry points (PTB)
# --------------------------------------------------------------------------
async def handle(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.message
    if not msg or not msg.text:
        return
    for key in BUSY_KEYS:
        if key in context.user_data:
            return
    await answer(context.bot, autodelete.MAIN_BOT, msg.chat_id,
                 update.effective_user.id, msg.text, msg.message_id)


async def on_pick(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    tid = int(q.data.split(":")[1])
    await send_title_card(context.bot, autodelete.MAIN_BOT, q.message.chat_id, tid)
