"""User settings: 18+ toggle + notifications (callback based)."""
import logging

from telegram import Update
from telegram.ext import ContextTypes

from database.queries import settings as settings_q
from database.queries import users as users_q
from utils import keyboards

log = logging.getLogger("usettings")


async def show_settings(update: Update, context: ContextTypes.DEFAULT_TYPE, edit=True):
    q = update.callback_query
    user = update.effective_user
    row = await users_q.get_user(user.id)
    if row is None:
        row = await users_q.upsert_user(
            {"id": user.id, "username": user.username, "first_name": user.first_name}
        )
    text = (
        "⚙️ <b>SETTINGS</b>\n\n"
        "━━━ CONTENT ━━━━━━━━━━━━\n"
        f"🔞 18+ Content: {'🟢 ON' if row['show_nsfw'] else '🔴 OFF'}\n\n"
        f"🔔 Notifications: {'🟢 ON' if row['notifications_enabled'] else '🔴 OFF'}"
    )
    kb = keyboards.user_settings_kb(row["show_nsfw"], row["notifications_enabled"])
    if q and edit:
        await q.answer()
        await q.edit_message_text(text, reply_markup=kb, parse_mode="HTML")
    elif q:
        await q.answer()
        await q.message.reply_text(text, reply_markup=kb, parse_mode="HTML")
    else:
        await update.message.reply_text(text, reply_markup=kb, parse_mode="HTML")


async def settings_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await show_settings(update, context, edit=False)


async def toggle_nsfw_prompt(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    row = await users_q.get_user(update.effective_user.id)
    if row and row["show_nsfw"]:
        # currently ON -> turn OFF immediately
        await users_q.set_nsfw(update.effective_user.id, False)
        await show_settings(update, context)
        return
    warning = await settings_q.get(
        "nsfw_warning_text",
        "⚠️ AGE VERIFICATION\n\nThis will show 18+ content.\n\nBy enabling, you confirm you are 18+.",
    )
    await q.edit_message_text(warning, reply_markup=keyboards.nsfw_confirm_kb())


async def toggle_nsfw_confirm(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer("18+ content enabled")
    await users_q.set_nsfw(update.effective_user.id, True)
    await show_settings(update, context)


async def toggle_notifications(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    row = await users_q.get_user(update.effective_user.id)
    await users_q.set_notifications(update.effective_user.id, not row["notifications_enabled"])
    await show_settings(update, context)
