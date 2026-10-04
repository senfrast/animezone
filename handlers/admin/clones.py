"""Main-bot admin UI to create / list / remove clone bots."""
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
from database.queries import clones as clones_q
from services import clone_manager
from utils import keyboards

log = logging.getLogger("admin.clones")

ADD_TOKEN = range(1)


async def clones_view(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    if not config.is_owner(q.from_user.id):
        await q.answer("⛔ Owner only", show_alert=True)
        return
    rows = await clones_q.list_active()
    lines = ["🤖 <b>CLONE BOTS</b>\n"]
    if rows:
        lines.append(
            "Each clone shares this bot's content, server and Mini App, and gives "
            "you its own admin panel (stats · broadcast · dashboard · maintenance).\n"
        )
        for r in rows:
            subs = await clones_q.sub_count(r["bot_id"])
            maint = " · 🔧 MAINT" if r["is_maintenance"] else ""
            uname = f"@{r['username']}" if r["username"] else str(r["bot_id"])
            lines.append(f"• <b>{uname}</b> — {subs} users{maint}")
    else:
        lines.append(
            "No clones yet.\n\nCreate a new bot in @BotFather, copy its token, then "
            "tap <b>Add Clone Bot</b> and paste it here."
        )
    kb_rows = [[InlineKeyboardButton("➕ Add Clone Bot", callback_data="clone:add")]]
    for r in rows:
        uname = f"@{r['username']}" if r["username"] else str(r["bot_id"])
        kb_rows.append([InlineKeyboardButton(f"🗑️ Remove {uname}", callback_data=f"clrm:{r['bot_id']}")])
    kb_rows.append([InlineKeyboardButton("🔙 Back to Panel", callback_data="admin:home")])
    await q.edit_message_text(
        "\n".join(lines), reply_markup=InlineKeyboardMarkup(kb_rows), parse_mode="HTML"
    )


async def remove_clone(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    if not config.is_owner(q.from_user.id):
        await q.answer("⛔ Owner only", show_alert=True)
        return
    bot_id = int(q.data.split(":")[1])
    clone = clone_manager.get_clone(bot_id) or await clones_q.get(bot_id)
    uname = f"@{clone['username']}" if clone and clone.get("username") else str(bot_id)
    await clone_manager.remove(bot_id)
    await q.answer(f"Removed {uname}", show_alert=True)
    # refresh the list
    await clones_view(update, context)


# ---------------- add-clone conversation ----------------
async def add_entry(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    if not config.is_owner(q.from_user.id):
        await q.answer("⛔ Owner only", show_alert=True)
        return ConversationHandler.END
    await q.message.reply_text(
        "🤖 <b>Add a Clone Bot</b>\n\n"
        "1. Open @BotFather → <code>/newbot</code> → follow the steps.\n"
        "2. Copy the token it gives you (looks like <code>123456:ABC-...</code>).\n"
        "3. Paste that token here.\n\n"
        "Send /cancel to abort.",
        parse_mode="HTML",
    )
    return ADD_TOKEN


async def got_token(update: Update, context: ContextTypes.DEFAULT_TYPE):
    token = (update.message.text or "").strip()
    if ":" not in token or len(token) < 20:
        await update.message.reply_text("⚠️ That doesn't look like a bot token. Try again or /cancel.")
        return ADD_TOKEN
    status = await update.message.reply_text("⏳ Validating token and wiring up the clone…")
    try:
        me = await clone_manager.add(token, update.effective_user.id)
    except Exception as e:  # noqa: BLE001
        log.exception("add clone failed")
        await status.edit_text(f"❌ Couldn't add that bot: {e}\n\nCheck the token and try again with /cancel then Add Clone Bot.")
        return ConversationHandler.END
    await status.edit_text(
        f"✅ Clone <b>@{me.username}</b> is live!\n\n"
        f"It now opens the same AnimeZone Mini App. Press Start on it to see your admin panel.\n\n"
        f"⚠️ In @BotFather, set this bot's Mini App / menu-button URL to:\n"
        f"<code>{config.MINI_APP_URL}</code>",
        parse_mode="HTML",
    )
    return ConversationHandler.END


async def _cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("❌ Cancelled.", reply_markup=keyboards.back_admin_kb())
    return ConversationHandler.END


def build_add_clone_conv() -> ConversationHandler:
    return ConversationHandler(
        entry_points=[CallbackQueryHandler(add_entry, pattern="^clone:add$")],
        states={
            ADD_TOKEN: [MessageHandler(filters.TEXT & ~filters.COMMAND, got_token)],
        },
        fallbacks=[CommandHandler("cancel", _cancel)],
        allow_reentry=True,
    )
