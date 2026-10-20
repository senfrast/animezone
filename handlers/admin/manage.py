"""Owner tools: manage moderators (from the panel) + backup / restore."""
import json
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
from database.queries import admins as admins_q
from services import backup_service
from utils import keyboards, roles

log = logging.getLogger("manage")

MOD_INPUT = 0
RESTORE_FILE = 0


# ---------------- moderators ----------------
async def mods_view(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    if not config.is_owner(q.from_user.id):
        await q.answer("⛔ Owner only", show_alert=True)
        return
    db_mods = await admins_q.list_moderators()
    lines = ["👮 <b>MODERATORS</b>\n",
             "Tap a moderator to control exactly what they're allowed to do.\n"]
    rows = []
    if config.ENV_MODERATOR_IDS:
        lines.append("<b>From server config (permanent):</b>")
        for uid in config.ENV_MODERATOR_IDS:
            lines.append(f"• <code>{uid}</code>")
        lines.append("")
    lines.append("<b>Added from panel:</b>")
    if db_mods:
        for m in db_mods:
            label = m["first_name"] or ""
            if m["username"]:
                label += f" (@{m['username']})"
            label = label.strip() or f"User {m['user_id']}"
            badges = ""
            if m.get("auto_approve"):
                badges += "⚡"
            if m.get("can_nsfw"):
                badges += "🔞"
            if m.get("can_edit"):
                badges += "✏️"
            if m.get("can_delete"):
                badges += "🗑️"
            lines.append(f"• {label} — <code>{m['user_id']}</code> {badges}")
            rows.append([InlineKeyboardButton(
                f"⚙️ {label} {badges}", callback_data=f"mperm:{m['user_id']}")])
    else:
        lines.append("• (none yet)")
    lines.append("\n<i>⚡ auto-publish · 🔞 may add 18+ · ✏️ may edit · 🗑️ may delete</i>")
    rows.append([InlineKeyboardButton("➕ Add Moderator", callback_data="admin:addmod")])
    rows.append([InlineKeyboardButton("🔙 Back to Panel", callback_data="admin:home")])
    await q.edit_message_text("\n".join(lines), reply_markup=InlineKeyboardMarkup(rows), parse_mode="HTML")


_PERM_LABELS = {
    "auto_approve": ("⚡ Auto-publish uploads",
                     "Their titles go live instantly — no approval queue."),
    "can_nsfw": ("🔞 May add 18+ content",
                 "Can mark a title as adult and post into Adults Nation."),
    "can_edit": ("✏️ May edit titles",
                 "Can open the Title Manager and change existing titles."),
    "can_delete": ("🗑️ May delete titles",
                   "Can move titles to Trash."),
}


async def mod_perms(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Permission screen for one moderator."""
    q = update.callback_query
    await q.answer()
    if not config.is_owner(q.from_user.id):
        await q.answer("⛔ Owner only", show_alert=True)
        return
    uid = int(q.data.split(":")[1])
    m = await admins_q.get_moderator(uid)
    if not m:
        await q.edit_message_text("Moderator not found.",
                                  reply_markup=keyboards.back_admin_kb("admin:mods"))
        return
    label = (m["first_name"] or "").strip()
    if m["username"]:
        label += f" (@{m['username']})"
    label = label or f"User {uid}"

    body = [f"⚙️ <b>PERMISSIONS</b>\n{label} — <code>{uid}</code>\n"]
    rows = []
    for perm, (title, desc) in _PERM_LABELS.items():
        on = bool(m[perm])
        body.append(f"{'✅' if on else '❌'} <b>{title}</b>\n   <i>{desc}</i>")
        rows.append([InlineKeyboardButton(
            f"{'✅' if on else '❌'} {title}", callback_data=f"mpset:{uid}:{perm}")])
    body.append("\nTap any line to switch it on or off.")
    rows.append([InlineKeyboardButton("🗑️ Remove this moderator", callback_data=f"delmod:{uid}")])
    rows.append([InlineKeyboardButton("🔙 Back to Moderators", callback_data="admin:mods")])
    await q.edit_message_text("\n".join(body),
                              reply_markup=InlineKeyboardMarkup(rows), parse_mode="HTML")


async def mod_perm_toggle(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    if not config.is_owner(q.from_user.id):
        await q.answer("⛔ Owner only", show_alert=True)
        return
    _, uid, perm = q.data.split(":")
    new = await admins_q.toggle_perm(int(uid), perm)
    await q.answer(f"{_PERM_LABELS[perm][0]} → {'ON' if new else 'OFF'}")
    # re-render the screen with the fresh value
    await mod_perms(_ReData(update, f"mperm:{uid}"), context)


class _ReData:
    """Wraps an Update so a handler can be re-run with different callback data
    (CallbackQuery.data is immutable in PTB)."""

    def __init__(self, update, data):
        self._u = update
        self.callback_query = _ReQ(update.callback_query, data)
        self.effective_user = update.effective_user

    def __getattr__(self, item):
        return getattr(self._u, item)


class _ReQ:
    def __init__(self, q, data):
        self._q = q
        self.data = data
        self.from_user = q.from_user

    async def answer(self, *a, **k):
        return None

    def __getattr__(self, item):
        return getattr(self._q, item)


async def remove_mod(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    if not config.is_owner(q.from_user.id):
        await q.answer("⛔ Owner only", show_alert=True)
        return
    uid = int(q.data.split(":")[1])
    await admins_q.remove_moderator(uid)
    await roles.refresh()
    await q.answer("Removed")
    await mods_view(update, context)


# --- add moderator conversation ---
async def add_mod_entry(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    if not config.is_owner(q.from_user.id):
        return ConversationHandler.END
    await q.message.reply_text(
        "👮 <b>Add a moderator</b>\n\n"
        "Send me the person's <b>numeric Telegram ID</b>,\n"
        "or simply <b>forward any message from them</b> here.\n\n"
        "(They can get their ID from @userinfobot.)\n\n"
        "Send /cancel to abort.",
        parse_mode="HTML",
    )
    return MOD_INPUT


async def add_mod_input(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.message
    uid = first_name = username = None

    # forwarded message?
    fo = getattr(msg, "forward_origin", None)
    if fo is not None and getattr(fo, "sender_user", None):
        u = fo.sender_user
        uid, first_name, username = u.id, u.first_name, u.username
    elif getattr(msg, "forward_from", None):
        u = msg.forward_from
        uid, first_name, username = u.id, u.first_name, u.username
    elif msg.text and msg.text.strip().isdigit():
        uid = int(msg.text.strip())

    if not uid:
        await msg.reply_text(
            "⚠️ I couldn't read a user. Send a numeric ID, or forward a message from them.\n"
            "(If their forwarded messages are hidden by privacy, use the numeric ID.)"
        )
        return MOD_INPUT

    if config.is_owner(uid):
        await msg.reply_text("That user is already an owner. 👑")
        return ConversationHandler.END

    await admins_q.add_moderator(uid, first_name, username, added_by=msg.from_user.id)
    await roles.refresh()
    await msg.reply_text(
        f"✅ Added moderator: {first_name or ''} <code>{uid}</code>\n"
        "They can now open /admin and submit titles for your approval.",
        reply_markup=keyboards.back_admin_kb(),
        parse_mode="HTML",
    )
    # let them know
    try:
        await context.bot.send_message(
            uid,
            "🎉 You've been added as a moderator on AnimeZone!\n\n"
            "Send /admin to add titles. Everything you submit will be reviewed "
            "by the owner before going live.",
        )
    except Exception:  # noqa: BLE001
        pass
    return ConversationHandler.END


async def _cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("❌ Cancelled.")
    return ConversationHandler.END


def build_add_mod_conv() -> ConversationHandler:
    return ConversationHandler(
        entry_points=[CallbackQueryHandler(add_mod_entry, pattern="^admin:addmod$")],
        states={MOD_INPUT: [MessageHandler((filters.TEXT | filters.FORWARDED) & ~filters.COMMAND, add_mod_input)]},
        fallbacks=[CommandHandler("cancel", _cancel)],
        allow_reentry=True,
    )


# ---------------- backup ----------------
async def backup_now(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer("Generating backup…")
    if not config.is_owner(q.from_user.id):
        await q.answer("⛔ Owner only", show_alert=True)
        return
    buf, fname, counts = await backup_service.backup_bytes()
    await context.bot.send_document(
        chat_id=q.from_user.id, document=buf, filename=fname,
        caption=(f"💾 <b>Full backup</b>\n{counts['titles']} titles · "
                 f"{counts['categories']} categories · {counts['genres']} genres\n\n"
                 "Keep this file safe. You can restore everything from it via "
                 "<b>Admin → ♻️ Restore Backup</b>."),
        parse_mode="HTML",
    )
    await q.edit_message_text("💾 Backup sent above. ⬆️", reply_markup=keyboards.back_admin_kb())


# --- restore conversation ---
async def restore_entry(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    if not config.is_owner(q.from_user.id):
        return ConversationHandler.END
    await q.message.reply_text(
        "♻️ <b>Restore from backup</b>\n\n"
        "Send me a backup <b>.json</b> file (the one this bot generated).\n"
        "Existing titles are kept — only missing ones are re-added, so this is safe.\n\n"
        "Send /cancel to abort.",
        parse_mode="HTML",
    )
    return RESTORE_FILE


async def restore_file(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.message
    doc = msg.document
    if not doc:
        await msg.reply_text("⚠️ Please send the backup .json file.")
        return RESTORE_FILE
    try:
        f = await context.bot.get_file(doc.file_id)
        raw = await f.download_as_bytearray()
        data = json.loads(raw.decode("utf-8"))
    except Exception as e:  # noqa: BLE001
        await msg.reply_text(f"❌ Could not read the file: {e}")
        return RESTORE_FILE
    if not isinstance(data, dict) or "titles" not in data:
        await msg.reply_text("❌ That doesn't look like an AnimeZone backup.")
        return RESTORE_FILE
    await msg.reply_text("♻️ Restoring…")
    added = await backup_service.restore_from(data)
    await roles.refresh()
    await msg.reply_text(
        "✅ <b>Restore complete</b>\n"
        f"Added: {added['titles']} titles, {added['categories']} categories, "
        f"{added['genres']} genres, {added['moderators']} moderators.\n\n"
        "⚠️ If this was restored under a NEW bot token, images may need re-uploading "
        "(Telegram image IDs are bot-specific). Everything else is back.",
        reply_markup=keyboards.back_admin_kb(),
        parse_mode="HTML",
    )
    return ConversationHandler.END


def build_restore_conv() -> ConversationHandler:
    return ConversationHandler(
        entry_points=[CallbackQueryHandler(restore_entry, pattern="^admin:restore$")],
        states={RESTORE_FILE: [MessageHandler(filters.Document.ALL & ~filters.COMMAND, restore_file)]},
        fallbacks=[CommandHandler("cancel", _cancel)],
        allow_reentry=True,
    )
