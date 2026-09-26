"""Add Title ConversationHandler."""
import logging

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import (
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
    ConversationHandler,
    MessageHandler,
    filters,
)

import config
from database import pool as db
from database.queries import categories as categories_q
from database.queries import titles as titles_q
from utils import keyboards
from utils.constants import LANGUAGES
from utils.helpers import normalize_channel_link, truncate

log = logging.getLogger("addtitle")

(NAME, IMAGE, DESC_CHOICE, DESC, CHANNEL, CATEGORY, GENRES, LANGUAGE,
 STATUS, EPISODES, NSFW, CONFIRM) = range(12)


def _admin(uid):
    return config.is_admin(uid)


async def entry(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    if q:
        await q.answer()
        if not _admin(q.from_user.id):
            return ConversationHandler.END
        context.user_data["new_title"] = {}
        # pre-fill from a content request?
        await q.message.reply_text("📝 Send the title name.\nExample: Naruto Shippuden (Hindi)")
    else:
        context.user_data["new_title"] = {}
        await update.message.reply_text("📝 Send the title name.")
    return NAME


async def got_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    name = (update.message.text or "").strip()
    if not (1 <= len(name) <= 255):
        await update.message.reply_text("⚠️ Please send a valid title (1–255 chars).")
        return NAME
    context.user_data["new_title"]["title"] = name
    await update.message.reply_text("🖼️ Send the image (photo) for this title.\nThis image is used everywhere.")
    return IMAGE


async def got_image(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message.photo:
        await update.message.reply_text("⚠️ Please send a photo.")
        return IMAGE
    context.user_data["new_title"]["image_file_id"] = update.message.photo[-1].file_id
    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton("📝 Add Description", callback_data="addt:desc")],
        [InlineKeyboardButton("⏩ Skip", callback_data="addt:skipdesc")],
    ])
    await update.message.reply_text("📝 Want to add a description?", reply_markup=kb)
    return DESC_CHOICE


async def desc_choice(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    if q.data == "addt:skipdesc":
        context.user_data["new_title"]["description"] = ""
        await q.message.reply_text("🔗 Send the Telegram channel link.\nFormats: t.me/channel, @channel, or t.me/+invite")
        return CHANNEL
    await q.message.reply_text("Send description (max 500 chars):")
    return DESC


async def got_desc(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["new_title"]["description"] = truncate(update.message.text or "", 500)
    await update.message.reply_text("🔗 Send the Telegram channel link.\nFormats: t.me/channel, @channel, or t.me/+invite")
    return CHANNEL


async def got_channel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    raw = (update.message.text or "").strip()
    link, username = normalize_channel_link(raw)
    if not link:
        await update.message.reply_text("⚠️ Invalid link, try again.")
        return CHANNEL
    context.user_data["new_title"]["channel_link"] = link
    context.user_data["new_title"]["channel_username"] = username
    cats = await categories_q.list_categories()
    rows = [[InlineKeyboardButton(f"{c['emoji']} {c['name']}", callback_data=f"addt:cat:{c['category_id']}")] for c in cats]
    await update.message.reply_text("📂 Select category:", reply_markup=InlineKeyboardMarkup(rows))
    return CATEGORY


async def got_category(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    cid = int(q.data.split(":")[2])
    context.user_data["new_title"]["category_id"] = cid
    context.user_data["new_title"]["genre_ids"] = set()
    await _show_genres(q, context)
    return GENRES


async def _show_genres(q, context):
    genres = await db.fetch("SELECT genre_id, name, emoji FROM genres ORDER BY name")
    selected = context.user_data["new_title"]["genre_ids"]
    rows, row = [], []
    for g in genres:
        mark = "✅" if g["genre_id"] in selected else ""
        row.append(InlineKeyboardButton(f"{mark}{g['emoji']} {g['name']}", callback_data=f"addt:g:{g['genre_id']}"))
        if len(row) == 2:
            rows.append(row)
            row = []
    if row:
        rows.append(row)
    rows.append([InlineKeyboardButton("✅ Done", callback_data="addt:gdone")])
    text = "🎭 Select genres (tap to toggle, then Done). Min 1."
    try:
        await q.edit_message_text(text, reply_markup=InlineKeyboardMarkup(rows))
    except Exception:  # noqa: BLE001
        await q.message.reply_text(text, reply_markup=InlineKeyboardMarkup(rows))


async def toggle_genre(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    if q.data == "addt:gdone":
        if not context.user_data["new_title"]["genre_ids"]:
            await q.answer("Select at least 1 genre", show_alert=True)
            return GENRES
        rows = [[InlineKeyboardButton(l, callback_data=f"addt:lang:{l}")] for l in LANGUAGES]
        await q.edit_message_text("🌐 Select language:", reply_markup=InlineKeyboardMarkup(rows))
        return LANGUAGE
    gid = int(q.data.split(":")[2])
    sel = context.user_data["new_title"]["genre_ids"]
    if gid in sel:
        sel.remove(gid)
    else:
        sel.add(gid)
    await _show_genres(q, context)
    return GENRES


async def got_language(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    context.user_data["new_title"]["language"] = q.data.split(":")[2]
    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton("🟢 Ongoing", callback_data="addt:st:Ongoing")],
        [InlineKeyboardButton("✅ Completed", callback_data="addt:st:Completed")],
    ])
    await q.edit_message_text("📊 Status:", reply_markup=kb)
    return STATUS


async def got_status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    context.user_data["new_title"]["status"] = q.data.split(":")[2]
    await q.edit_message_text("📺 Episode count? (send a number, 0 if unknown)")
    return EPISODES


async def got_episodes(update: Update, context: ContextTypes.DEFAULT_TYPE):
    txt = (update.message.text or "").strip()
    if not txt.isdigit():
        await update.message.reply_text("⚠️ Send a number (0 if unknown).")
        return EPISODES
    context.user_data["new_title"]["episode_count"] = int(txt)
    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton("❌ No — Safe for All", callback_data="addt:nsfw:0")],
        [InlineKeyboardButton("✅ Yes — 18+ Only", callback_data="addt:nsfw:1")],
    ])
    await update.message.reply_text("🔞 Is this 18+ content?", reply_markup=kb)
    return NSFW


async def got_nsfw(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    context.user_data["new_title"]["is_nsfw"] = q.data.split(":")[2] == "1"
    d = context.user_data["new_title"]
    cat = await categories_q.get_by_id(d["category_id"])
    genre_names = await db.fetch(
        "SELECT name FROM genres WHERE genre_id = ANY($1::int[])", list(d["genre_ids"])
    )
    preview = (
        "🔎 <b>PREVIEW</b>\n\n"
        f"<b>{d['title']}</b>\n"
        f"📂 {cat['emoji']} {cat['name']}\n"
        f"🎭 {', '.join(g['name'] for g in genre_names)}\n"
        f"🌐 {d['language']} │ 📊 {d['status']} │ 📺 {d['episode_count']} eps\n"
        f"🔞 {'Yes' if d['is_nsfw'] else 'No'}\n"
        f"🔗 {d['channel_link']}\n\n"
        f"{d.get('description') or '(no description)'}"
    )
    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton("✅ Publish", callback_data="addt:publish")],
        [InlineKeyboardButton("❌ Cancel", callback_data="addt:cancel")],
    ])
    await q.message.reply_photo(photo=d["image_file_id"], caption=preview, reply_markup=kb, parse_mode="HTML")
    return CONFIRM


async def confirm(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    if q.data == "addt:cancel":
        context.user_data.pop("new_title", None)
        await q.message.reply_text("❌ Cancelled.", reply_markup=keyboards.back_admin_kb())
        return ConversationHandler.END
    d = context.user_data["new_title"]
    d["genre_ids"] = list(d.get("genre_ids", []))
    d["added_by"] = q.from_user.id
    row = await titles_q.create(d)
    await categories_q.refresh_count(d["category_id"])
    context.user_data.pop("new_title", None)
    await q.message.reply_text(
        f"✅ <b>{row['title']}</b> is now live! (#{row['title_id']})",
        reply_markup=keyboards.back_admin_kb(),
        parse_mode="HTML",
    )
    return ConversationHandler.END


def build_add_title_conv() -> ConversationHandler:
    return ConversationHandler(
        entry_points=[
            CallbackQueryHandler(entry, pattern="^admin:addtitle$"),
            CommandHandler("addtitle", entry),
        ],
        states={
            NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, got_name)],
            IMAGE: [MessageHandler(filters.PHOTO, got_image)],
            DESC_CHOICE: [CallbackQueryHandler(desc_choice, pattern="^addt:(desc|skipdesc)$")],
            DESC: [MessageHandler(filters.TEXT & ~filters.COMMAND, got_desc)],
            CHANNEL: [MessageHandler(filters.TEXT & ~filters.COMMAND, got_channel)],
            CATEGORY: [CallbackQueryHandler(got_category, pattern="^addt:cat:")],
            GENRES: [CallbackQueryHandler(toggle_genre, pattern="^addt:(g:|gdone)")],
            LANGUAGE: [CallbackQueryHandler(got_language, pattern="^addt:lang:")],
            STATUS: [CallbackQueryHandler(got_status, pattern="^addt:st:")],
            EPISODES: [MessageHandler(filters.TEXT & ~filters.COMMAND, got_episodes)],
            NSFW: [CallbackQueryHandler(got_nsfw, pattern="^addt:nsfw:")],
            CONFIRM: [CallbackQueryHandler(confirm, pattern="^addt:(publish|cancel)$")],
        },
        fallbacks=[CommandHandler("cancel", _cancel)],
        per_message=False,
        allow_reentry=True,
    )


async def _cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data.pop("new_title", None)
    await update.message.reply_text("❌ Cancelled.")
    return ConversationHandler.END
