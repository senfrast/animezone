"""Category management + Add Category ConversationHandler."""
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
from database.queries import categories as categories_q
from utils import keyboards

log = logging.getLogger("admincats")

CAT_NAME, CAT_EMOJI, CAT_NSFW = range(3)


async def list_cats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    cats = await categories_q.list_categories(only_active=False)
    lines = ["📂 <b>CATEGORIES</b>\n"]
    for c in cats:
        nsfw = "🔞" if c["is_nsfw"] else ""
        lines.append(f"{c['emoji']} <b>{c['name']}</b> {nsfw} — {c['title_count']} titles  (delete: /delcat_{c['category_id']})")
    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton("➕ Add Category", callback_data="admin:addcat")],
        [InlineKeyboardButton("🔙 Back to Panel", callback_data="admin:home")],
    ])
    await q.edit_message_text("\n".join(lines), reply_markup=kb, parse_mode="HTML")


async def cat_entry(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    if not config.is_owner(q.from_user.id):
        await q.answer("⛔ Owner only", show_alert=True)
        return ConversationHandler.END
    context.user_data["new_cat"] = {}
    await q.message.reply_text("📂 Send the category name:")
    return CAT_NAME


async def cat_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["new_cat"]["name"] = (update.message.text or "").strip()
    await update.message.reply_text("Send an emoji for it (e.g. 🎬):")
    return CAT_EMOJI


async def cat_emoji(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["new_cat"]["emoji"] = (update.message.text or "📂").strip()[:10]
    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton("❌ No — Safe", callback_data="addcat:nsfw:0")],
        [InlineKeyboardButton("✅ Yes — 18+", callback_data="addcat:nsfw:1")],
    ])
    await update.message.reply_text("🔞 Is this an 18+ category?", reply_markup=kb)
    return CAT_NSFW


async def cat_nsfw(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    d = context.user_data["new_cat"]
    is_nsfw = q.data.split(":")[2] == "1"
    row = await categories_q.create(d["name"], d["emoji"], is_nsfw)
    context.user_data.pop("new_cat", None)
    await q.message.reply_text(
        f"✅ Category {row['emoji']} {row['name']} created.",
        reply_markup=keyboards.back_admin_kb("admin:cats"),
    )
    return ConversationHandler.END


async def delcat_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not config.is_owner(update.effective_user.id):
        return
    cid = (update.message.text or "").replace("/delcat_", "").strip()
    if cid.isdigit():
        await categories_q.delete(int(cid))
        await update.message.reply_text(f"🗑️ Category #{cid} deleted (with its titles).")


async def _cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data.pop("new_cat", None)
    await update.message.reply_text("❌ Cancelled.")
    return ConversationHandler.END


def build_add_category_conv() -> ConversationHandler:
    return ConversationHandler(
        entry_points=[CallbackQueryHandler(cat_entry, pattern="^admin:addcat$")],
        states={
            CAT_NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, cat_name)],
            CAT_EMOJI: [MessageHandler(filters.TEXT & ~filters.COMMAND, cat_emoji)],
            CAT_NSFW: [CallbackQueryHandler(cat_nsfw, pattern="^addcat:nsfw:")],
        },
        fallbacks=[CommandHandler("cancel", _cancel)],
        allow_reentry=True,
    )
