"""Broadcast ConversationHandler."""
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
from services import broadcast_engine
from utils import keyboards

log = logging.getLogger("broadcast")

BC_CONTENT, BC_CONFIRM = range(2)


async def entry(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    if not config.is_owner(q.from_user.id):
        await q.answer("⛔ Owner only", show_alert=True)
        return ConversationHandler.END
    await q.message.reply_text("📢 Send the broadcast message text:")
    return BC_CONTENT


async def got_content(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["bc_text"] = update.message.text or ""
    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton("✅ Send Now", callback_data="bc:send")],
        [InlineKeyboardButton("❌ Cancel", callback_data="bc:cancel")],
    ])
    await update.message.reply_text(
        f"Preview:\n\n{context.user_data['bc_text']}\n\nSend to all users?",
        reply_markup=kb,
    )
    return BC_CONFIRM


async def confirm(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    if q.data == "bc:cancel":
        context.user_data.pop("bc_text", None)
        await q.message.reply_text("❌ Broadcast cancelled.", reply_markup=keyboards.back_admin_kb())
        return ConversationHandler.END

    text = context.user_data.get("bc_text", "")
    status_msg = await q.message.reply_text("📤 Broadcasting…")

    async def progress(i, total, sent, failed, blocked):
        try:
            await status_msg.edit_text(f"📤 {i}/{total} — sent {sent}, failed {failed}, blocked {blocked}")
        except Exception:  # noqa: BLE001
            pass

    result = await broadcast_engine.broadcast_text(context.bot, text, progress)
    context.user_data.pop("bc_text", None)
    await status_msg.edit_text(
        f"✅ Broadcast complete.\nTotal: {result['total']}\nSent: {result['sent']}\n"
        f"Failed: {result['failed']}\nBlocked: {result['blocked']}",
        reply_markup=keyboards.back_admin_kb(),
    )
    return ConversationHandler.END


async def _cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data.pop("bc_text", None)
    await update.message.reply_text("❌ Cancelled.")
    return ConversationHandler.END


def build_broadcast_conv() -> ConversationHandler:
    return ConversationHandler(
        entry_points=[CallbackQueryHandler(entry, pattern="^admin:broadcast$")],
        states={
            BC_CONTENT: [MessageHandler(filters.TEXT & ~filters.COMMAND, got_content)],
            BC_CONFIRM: [CallbackQueryHandler(confirm, pattern="^bc:(send|cancel)$")],
        },
        fallbacks=[CommandHandler("cancel", _cancel)],
        allow_reentry=True,
    )
