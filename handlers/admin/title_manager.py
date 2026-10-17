"""Title Manager — a fully button-driven admin UI for editing live content.

Everything an owner needs to fix a title after it is published is reachable by
tapping: rename, description, status (Ongoing <-> Completed when a new season
drops or a show ends), episode/part count, category, language, quality, cover,
channel link, genres, featured, 18+, delete/restore.

The only typing involved is the new *value* itself (a name, a number, a link).
There are no slash-commands and no ids to memorise: titles are found by paging
or by searching their name.

Free-text answers use a tiny "awaiting input" slot in user_data instead of a
ConversationHandler, so any number of fields can share one message handler
without the conversations fighting each other.
"""
import html
import logging
import time

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import ContextTypes

import config
from database.queries import categories as categories_q
from database.queries import titles as titles_q
from utils import helpers
from utils.constants import LANGUAGES

log = logging.getLogger("title_manager")

PAGE = 8
AWAIT_KEY = "tm_await"

# field -> (prompt, validator/caster, success label)
TEXT_FIELDS = {
    "title": ("✏️ Send the <b>new title</b>:", "str", "Title"),
    "description": ("📝 Send the <b>new description</b>:", "str", "Description"),
    "channel_link": ("🔗 Send the <b>new channel link</b>:", "link", "Channel link"),
    "episode_count": ("🔢 Send the <b>exact number</b>:", "int", "Count"),
    "release_year": ("📅 Send the <b>release year</b> (e.g. 2024):", "int", "Year"),
    "title_alt": ("🏷️ Send an <b>alternate name</b> (used by search):", "str", "Alt name"),
}

QUALITIES = ["480p", "720p", "720p + 1080p", "1080p", "1080p + 4K", "4K"]


def esc(v) -> str:
    return html.escape(str(v or ""), quote=False)


# --------------------------------------------------------------------------
# rendering
# --------------------------------------------------------------------------
async def _render(tid: int):
    """Build the editor screen (text + keyboard) for one title."""
    r = await titles_q.get_full(tid)
    if not r:
        return None, None

    is_movie = helpers.is_movie_category(r["category_name"])
    unit = "Parts" if is_movie else "Episodes"
    completed = (r["status"] or "").lower() == "completed"
    genres = await titles_q.genres_full(tid)
    glabel = ", ".join(g["name"] for g in genres) or "—"
    deleted = r["deleted_at"] is not None

    head = "🗑️ <b>IN TRASH</b>\n\n" if deleted else ""
    text = (
        f"{head}🎬 <b>{esc(r['title'])}</b>\n"
        f"<code>#{r['title_id']}</code>\n\n"
        f"📂 <b>Category</b>   {esc(r['category_emoji'])} {esc(r['category_name'])}\n"
        f"🌐 <b>Language</b>   {esc(r['language'])}\n"
        f"📊 <b>Status</b>     {'✅ Completed' if completed else '🟢 Ongoing'}\n"
        f"📺 <b>{unit}</b>   {r['episode_count'] or 0}\n"
        f"🎞️ <b>Quality</b>    {esc(r['quality'])}\n"
        f"🎭 <b>Genres</b>     {esc(glabel)}\n"
        f"⭐ <b>Featured</b>   {'Yes' if r['is_featured'] else 'No'}\n"
        f"🔞 <b>Adult</b>      {'Yes' if r['is_nsfw'] else 'No'}\n"
        f"🔗 <b>Channel</b>    {esc(r['channel_link'])}\n\n"
        f"⭐ {float(r['rating'] or 0):.1f} ({r['rating_count'] or 0}) · "
        f"👁 {r['total_clicks'] or 0} · 🔖 {r['total_bookmarks'] or 0}"
    )
    if r["description"]:
        text += f"\n\n<i>{esc(helpers.truncate(r['description'], 160))}</i>"

    if deleted:
        kb = [
            [InlineKeyboardButton("♻️ Restore this title", callback_data=f"tm:undel:{tid}")],
            [InlineKeyboardButton("🔙 Back to list", callback_data="tm:l:0")],
        ]
        return text, InlineKeyboardMarkup(kb)

    status_btn = ("🟢 Mark Ongoing (new season)" if completed
                  else "✅ Mark Completed (series ended)")
    kb = [
        [InlineKeyboardButton("✏️ Rename", callback_data=f"tm:in:title:{tid}"),
         InlineKeyboardButton("📝 Description", callback_data=f"tm:in:description:{tid}")],
        [InlineKeyboardButton(status_btn, callback_data=f"tm:st:{tid}")],
        [InlineKeyboardButton(f"📺 {unit}: {r['episode_count'] or 0}", callback_data="tm:noop")],
        [InlineKeyboardButton("➖1", callback_data=f"tm:ep:{tid}:-1"),
         InlineKeyboardButton("➕1", callback_data=f"tm:ep:{tid}:1"),
         InlineKeyboardButton("➕5", callback_data=f"tm:ep:{tid}:5"),
         InlineKeyboardButton("🔢 Set", callback_data=f"tm:in:episode_count:{tid}")],
        [InlineKeyboardButton("🎭 Genres", callback_data=f"egen:{tid}"),
         InlineKeyboardButton("📂 Category", callback_data=f"tm:cat:{tid}")],
        [InlineKeyboardButton("🌐 Language", callback_data=f"tm:lang:{tid}"),
         InlineKeyboardButton("🎞️ Quality", callback_data=f"tm:ql:{tid}")],
        [InlineKeyboardButton("🖼️ Cover image", callback_data=f"eimg:{tid}"),
         InlineKeyboardButton("🔗 Link", callback_data=f"tm:in:channel_link:{tid}")],
        [InlineKeyboardButton(f"⭐ Featured: {'ON' if r['is_featured'] else 'OFF'}",
                              callback_data=f"tm:ft:{tid}"),
         InlineKeyboardButton(f"🔞 18+: {'ON' if r['is_nsfw'] else 'OFF'}",
                              callback_data=f"tm:ns:{tid}")],
        [InlineKeyboardButton("🗑️ Delete", callback_data=f"tm:del:{tid}"),
         InlineKeyboardButton("🔄 Refresh", callback_data=f"tm:o:{tid}")],
        [InlineKeyboardButton("🔙 Back to list", callback_data="tm:l:0"),
         InlineKeyboardButton("🏠 Panel", callback_data="admin:home")],
    ]
    return text, InlineKeyboardMarkup(kb)


async def _show(q, tid: int, note: str = ""):
    text, kb = await _render(tid)
    if text is None:
        await q.edit_message_text("❌ Title not found.",
                                  reply_markup=InlineKeyboardMarkup(
                                      [[InlineKeyboardButton("🔙 Back", callback_data="tm:l:0")]]))
        return
    if note:
        text = f"{note}\n\n{text}"
    try:
        await q.edit_message_text(text, reply_markup=kb, parse_mode="HTML",
                                  disable_web_page_preview=True)
    except Exception:  # noqa: BLE001 — identical content ⇒ Telegram errors, harmless
        pass


# --------------------------------------------------------------------------
# list / search
# --------------------------------------------------------------------------
def _row_label(r) -> str:
    flag = "⭐" if r["is_featured"] else ""
    flag += "🔞" if r["is_nsfw"] else ""
    mark = "✅" if (r["status"] or "").lower() == "completed" else "🟢"
    name = r["title"] if len(r["title"]) <= 32 else r["title"][:31] + "…"
    return f"{mark}{flag} {name}"


async def show_list(update: Update, context: ContextTypes.DEFAULT_TYPE, data: str = None):
    q = update.callback_query
    await q.answer()
    parts = (data or q.data).split(":")
    offset = int(parts[2]) if len(parts) > 2 and parts[2].isdigit() else 0
    cid = int(parts[3]) if len(parts) > 3 and parts[3].isdigit() else None

    rows = await titles_q.admin_list(limit=PAGE, offset=offset, category_id=cid)
    total = await titles_q.admin_count(category_id=cid)
    cats = await categories_q.list_categories()
    cname = next((c["name"] for c in cats if c["category_id"] == cid), None)

    head = f"🎬 <b>MANAGE TITLES</b> — {total}"
    if cname:
        head += f" in {esc(cname)}"
    body = (f"{head}\n<i>Page {offset // PAGE + 1} of {max(1, -(-total // PAGE))}</i>\n\n"
            "Tap a title to edit everything about it.")

    kb = [[InlineKeyboardButton(_row_label(r), callback_data=f"tm:o:{r['title_id']}")]
          for r in rows]
    nav = []
    suffix = f":{cid}" if cid else ""
    if offset > 0:
        nav.append(InlineKeyboardButton("⬅️ Prev", callback_data=f"tm:l:{max(offset-PAGE,0)}{suffix}"))
    if offset + PAGE < total:
        nav.append(InlineKeyboardButton("Next ➡️", callback_data=f"tm:l:{offset+PAGE}{suffix}"))
    if nav:
        kb.append(nav)
    kb.append([InlineKeyboardButton("🔍 Search by name", callback_data="tm:find"),
               InlineKeyboardButton("📂 Filter", callback_data="tm:filter")])
    kb.append([InlineKeyboardButton("🗑️ Trash", callback_data="tm:trash"),
               InlineKeyboardButton("🏠 Panel", callback_data="admin:home")])
    await q.edit_message_text(body, reply_markup=InlineKeyboardMarkup(kb), parse_mode="HTML")


async def filter_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    cats = await categories_q.list_categories()
    kb = [[InlineKeyboardButton(f"{c['emoji']} {c['name']}", callback_data=f"tm:l:0:{c['category_id']}")]
          for c in cats]
    kb.append([InlineKeyboardButton("📋 All categories", callback_data="tm:l:0")])
    await q.edit_message_text("📂 <b>Filter by category</b>",
                              reply_markup=InlineKeyboardMarkup(kb), parse_mode="HTML")


async def trash_view(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    rows = await titles_q.list_trash()
    if not rows:
        kb = [[InlineKeyboardButton("🔙 Back to list", callback_data="tm:l:0")]]
        await q.edit_message_text("🗑️ <b>TRASH</b>\n\nEmpty — nothing deleted. ✅",
                                  reply_markup=InlineKeyboardMarkup(kb), parse_mode="HTML")
        return
    kb = [[InlineKeyboardButton(f"♻️ {r['title'][:34]}", callback_data=f"tm:undel:{r['title_id']}")]
          for r in rows[:20]]
    kb.append([InlineKeyboardButton("🔙 Back to list", callback_data="tm:l:0")])
    await q.edit_message_text(
        f"🗑️ <b>TRASH</b> ({len(rows)})\n\nTap to restore a title.",
        reply_markup=InlineKeyboardMarkup(kb), parse_mode="HTML")


async def search_prompt(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    context.user_data[AWAIT_KEY] = {"field": "__search", "tid": 0, "ts": time.time()}
    await q.edit_message_text(
        "🔍 <b>Search titles</b>\n\nSend part of the name — I'll list the matches.",
        reply_markup=InlineKeyboardMarkup(
            [[InlineKeyboardButton("❌ Cancel", callback_data="tm:l:0")]]),
        parse_mode="HTML")


async def _send_search_results(message, query: str):
    rows = await titles_q.admin_search(query)
    if not rows:
        await message.reply_text(
            f"🔍 No title matches “{esc(query)}”.",
            reply_markup=InlineKeyboardMarkup(
                [[InlineKeyboardButton("🔙 Back to list", callback_data="tm:l:0")]]),
            parse_mode="HTML")
        return
    kb = []
    for r in rows:
        label = _row_label(r)
        if r["deleted_at"] is not None:
            label = "🗑️ " + label
        kb.append([InlineKeyboardButton(label, callback_data=f"tm:o:{r['title_id']}")])
    kb.append([InlineKeyboardButton("🔙 Back to list", callback_data="tm:l:0")])
    await message.reply_text(
        f"🔍 <b>{len(rows)} match(es)</b> for “{esc(query)}”",
        reply_markup=InlineKeyboardMarkup(kb), parse_mode="HTML")


# --------------------------------------------------------------------------
# instant toggles
# --------------------------------------------------------------------------
async def toggle_status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    tid = int(q.data.split(":")[2])
    new = await titles_q.toggle_status(tid)
    await q.answer(f"Status → {new}")
    await _show(q, tid, f"📊 Status changed to <b>{esc(new)}</b>")


async def bump_eps(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    _, _, tid, delta = q.data.split(":")
    n = await titles_q.bump_episodes(int(tid), int(delta))
    await q.answer(f"Now {n}")
    await _show(q, int(tid))


async def toggle_featured(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    tid = int(q.data.split(":")[2])
    row = await titles_q.get_by_id(tid)
    new = not row["is_featured"]
    await titles_q.set_featured(tid, new)
    await q.answer("⭐ Featured" if new else "Removed from featured")
    await _show(q, tid)


async def toggle_nsfw(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    tid = int(q.data.split(":")[2])
    row = await titles_q.get_by_id(tid)
    new = not row["is_nsfw"]
    await titles_q.update_field(tid, "is_nsfw", new)
    await q.answer("Marked 18+" if new else "Marked safe")
    await _show(q, tid)


# --------------------------------------------------------------------------
# pickers
# --------------------------------------------------------------------------
async def category_picker(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    tid = int(q.data.split(":")[2])
    cats = await categories_q.list_categories()
    kb = [[InlineKeyboardButton(f"{c['emoji']} {c['name']}",
                                callback_data=f"tm:cset:{tid}:{c['category_id']}")]
          for c in cats]
    kb.append([InlineKeyboardButton("🔙 Back", callback_data=f"tm:o:{tid}")])
    await q.edit_message_text("📂 <b>Pick a category</b>",
                              reply_markup=InlineKeyboardMarkup(kb), parse_mode="HTML")


async def language_picker(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    tid = int(q.data.split(":")[2])
    kb, row = [], []
    for i, lang in enumerate(LANGUAGES):
        row.append(InlineKeyboardButton(lang, callback_data=f"tm:lset:{tid}:{i}"))
        if len(row) == 2:
            kb.append(row)
            row = []
    if row:
        kb.append(row)
    kb.append([InlineKeyboardButton("🔙 Back", callback_data=f"tm:o:{tid}")])
    await q.edit_message_text("🌐 <b>Pick a language</b>",
                              reply_markup=InlineKeyboardMarkup(kb), parse_mode="HTML")


async def quality_picker(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    tid = int(q.data.split(":")[2])
    kb = [[InlineKeyboardButton(v, callback_data=f"tm:qset:{tid}:{i}")]
          for i, v in enumerate(QUALITIES)]
    kb.append([InlineKeyboardButton("🔙 Back", callback_data=f"tm:o:{tid}")])
    await q.edit_message_text("🎞️ <b>Pick a quality</b>",
                              reply_markup=InlineKeyboardMarkup(kb), parse_mode="HTML")


async def set_from_picker(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handles tm:cset / tm:lset / tm:qset."""
    q = update.callback_query
    kind, tid, idx = q.data.split(":")[1], int(q.data.split(":")[2]), int(q.data.split(":")[3])
    if kind == "cset":
        await titles_q.update_field(tid, "category_id", idx)
        label = "Category updated"
    elif kind == "lset":
        await titles_q.update_field(tid, "language", LANGUAGES[idx])
        label = f"Language → {LANGUAGES[idx]}"
    else:
        await titles_q.update_field(tid, "quality", QUALITIES[idx])
        label = f"Quality → {QUALITIES[idx]}"
    await q.answer(label)
    await _show(q, tid, f"✅ {esc(label)}")


# --------------------------------------------------------------------------
# delete / restore
# --------------------------------------------------------------------------
async def delete_confirm(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    tid = int(q.data.split(":")[2])
    row = await titles_q.get_by_id(tid)
    await q.edit_message_text(
        f"🗑️ Delete <b>{esc(row['title'])}</b>?\n\n"
        "It moves to Trash and disappears from the app. You can restore it later.",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("✅ Yes, delete", callback_data=f"tm:dely:{tid}")],
            [InlineKeyboardButton("❌ Cancel", callback_data=f"tm:o:{tid}")],
        ]), parse_mode="HTML")


async def delete_do(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    tid = int(q.data.split(":")[2])
    await titles_q.delete(tid)
    await q.answer("Moved to Trash")
    await q.edit_message_text(
        "🗑️ Moved to Trash.",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("♻️ Undo", callback_data=f"tm:undel:{tid}")],
            [InlineKeyboardButton("🔙 Back to list", callback_data="tm:l:0")],
        ]))


async def restore_do(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    tid = int(q.data.split(":")[2])
    await titles_q.restore(tid)
    await q.answer("Restored ✅")
    await _show(q, tid, "♻️ <b>Restored.</b>")


# --------------------------------------------------------------------------
# free-text input
# --------------------------------------------------------------------------
async def ask_input(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    _, _, field, tid = q.data.split(":")
    tid = int(tid)
    prompt, _kind, _label = TEXT_FIELDS[field]
    context.user_data[AWAIT_KEY] = {"field": field, "tid": tid, "ts": time.time()}
    row = await titles_q.get_by_id(tid)
    current = row[field] if field in row.keys() else ""
    await q.edit_message_text(
        f"{prompt}\n\n<b>Current:</b> <code>{esc(helpers.truncate(str(current or '—'), 200))}</code>",
        reply_markup=InlineKeyboardMarkup(
            [[InlineKeyboardButton("❌ Cancel", callback_data=f"tm:o:{tid}")]]),
        parse_mode="HTML")


async def on_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Catches the reply to any editor prompt. Returns True if it consumed it."""
    pending = context.user_data.get(AWAIT_KEY)
    if not pending or not update.message or not update.message.text:
        return False
    # a prompt the admin walked away from must not silently eat a later message
    if time.time() - pending.get("ts", 0) > 600:
        context.user_data.pop(AWAIT_KEY, None)
        return False
    if not config.is_owner(update.effective_user.id):
        context.user_data.pop(AWAIT_KEY, None)
        return False

    value = update.message.text.strip()
    field, tid = pending["field"], pending["tid"]
    context.user_data.pop(AWAIT_KEY, None)

    if field == "__search":
        await _send_search_results(update.message, value)
        return True

    prompt, kind, label = TEXT_FIELDS[field]
    if kind == "int":
        if not value.isdigit():
            pending["ts"] = time.time()
            context.user_data[AWAIT_KEY] = pending  # keep waiting
            await update.message.reply_text("⚠️ Please send a number.")
            return True
        value = int(value)
    elif kind == "link":
        value, _uname = helpers.normalize_channel_link(value)
    elif field == "title" and len(value) > 255:
        value = value[:255]

    await titles_q.update_field(tid, field, value)
    text, kb = await _render(tid)
    await update.message.reply_text(
        f"✅ <b>{label} updated.</b>\n\n{text}", reply_markup=kb,
        parse_mode="HTML", disable_web_page_preview=True)
    return True


# --------------------------------------------------------------------------
# router
# --------------------------------------------------------------------------
async def route(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    if not config.is_owner(q.from_user.id):
        await q.answer("⛔ Owner only", show_alert=True)
        return
    data = q.data
    action = data.split(":")[1]

    if action == "noop":
        await q.answer()
    elif action == "l":
        await show_list(update, context)
    elif action == "o":
        await q.answer()
        await _show(q, int(data.split(":")[2]))
    elif action == "st":
        await toggle_status(update, context)
    elif action == "ep":
        await bump_eps(update, context)
    elif action == "ft":
        await toggle_featured(update, context)
    elif action == "ns":
        await toggle_nsfw(update, context)
    elif action == "cat":
        await category_picker(update, context)
    elif action == "lang":
        await language_picker(update, context)
    elif action == "ql":
        await quality_picker(update, context)
    elif action in ("cset", "lset", "qset"):
        await set_from_picker(update, context)
    elif action == "in":
        await ask_input(update, context)
    elif action == "del":
        await delete_confirm(update, context)
    elif action == "dely":
        await delete_do(update, context)
    elif action == "undel":
        await restore_do(update, context)
    elif action == "find":
        await search_prompt(update, context)
    elif action == "filter":
        await filter_menu(update, context)
    elif action == "trash":
        await trash_view(update, context)
    else:
        await q.answer()
