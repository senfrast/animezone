"""Backup Vault: use a private Telegram channel as backup storage.

The owner adds the bot as an admin of a private channel, then registers it here
(by forwarding any message from it, or /setbackup <id>). The bot then posts the
full DB JSON there (daily + on demand) and can archive all cover images so the
actual image bytes are stored safely — restorable even under a new bot token.
"""
import logging

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import ContextTypes

import config
from database.queries import settings as settings_q
from services import backup_service
from utils import keyboards

log = logging.getLogger("admin.vault")

SETTING_KEY = "backup_channel_id"


async def _channel_id():
    val = await settings_q.get(SETTING_KEY)
    if val:
        return str(val)
    return config.BACKUP_CHANNEL_ID or None


def _vault_kb(has_channel: bool):
    rows = []
    if has_channel:
        rows.append([InlineKeyboardButton("📤 Backup DB to Channel now", callback_data="bkv:json")])
        rows.append([InlineKeyboardButton("🖼️ Archive all covers to Channel", callback_data="bkv:covers")])
        rows.append([InlineKeyboardButton("🔌 Disconnect channel", callback_data="bkv:clear")])
    rows.append([InlineKeyboardButton("ℹ️ How to connect a channel", callback_data="bkv:help")])
    rows.append([InlineKeyboardButton("🔙 Back to Panel", callback_data="admin:home")])
    return InlineKeyboardMarkup(rows)


async def vault_view(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    if not config.is_owner(q.from_user.id):
        await q.answer("⛔ Owner only", show_alert=True)
        return
    ch = await _channel_id()
    if ch:
        status = f"✅ Connected channel: <code>{ch}</code>\nDaily auto-backup is posted here at 03:30 IST."
    else:
        status = "⚠️ No backup channel connected yet."
    await q.edit_message_text(
        "🗄️ <b>BACKUP VAULT</b>\n\n"
        f"{status}\n\n"
        "A private channel becomes a permanent, free backup store: the full database "
        "(titles, categories, genres, settings) is posted as a JSON file, and you can "
        "archive every cover image too.",
        reply_markup=_vault_kb(bool(ch)),
        parse_mode="HTML",
    )


async def help_view(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    await q.edit_message_text(
        "ℹ️ <b>Connect a backup channel</b>\n\n"
        "1️⃣ Create a <b>private channel</b> in Telegram.\n"
        "2️⃣ Add this bot as an <b>Administrator</b> (allow it to post messages).\n"
        "3️⃣ Do EITHER of these:\n"
        "   • <b>Forward</b> any message from that channel to me, or\n"
        "   • send <code>/setbackup -100XXXXXXXXXX</code> with the channel's id.\n\n"
        "That's it — I'll start posting backups there.",
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back", callback_data="admin:vault")]]),
        parse_mode="HTML",
    )


async def backup_json(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer("Posting backup…")
    if not config.is_owner(q.from_user.id):
        return
    ch = await _channel_id()
    if not ch:
        await q.answer("No channel connected", show_alert=True)
        return
    try:
        counts = await backup_service.send_json_to_channel(context.bot, ch)
        await q.edit_message_text(
            f"✅ Database backup posted to the channel.\n"
            f"{counts['titles']} titles · {counts['categories']} categories · {counts['genres']} genres.",
            reply_markup=keyboards.back_admin_kb("admin:vault"),
        )
    except Exception as e:  # noqa: BLE001
        log.exception("channel json backup failed")
        await q.edit_message_text(
            f"❌ Couldn't post to the channel: {e}\n\n"
            "Make sure the bot is an admin of the channel and can post messages.",
            reply_markup=keyboards.back_admin_kb("admin:vault"),
        )


async def archive_covers(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer("Archiving covers…")
    if not config.is_owner(q.from_user.id):
        return
    ch = await _channel_id()
    if not ch:
        await q.answer("No channel connected", show_alert=True)
        return
    status = await q.edit_message_text("🖼️ Archiving covers to the channel… this can take a minute.")

    async def progress(i, total, sent, failed):
        try:
            await status.edit_text(f"🖼️ {i}/{total} — archived {sent}, failed {failed}")
        except Exception:  # noqa: BLE001
            pass

    try:
        res = await backup_service.archive_covers_to_channel(context.bot, ch, progress)
        await status.edit_text(
            f"✅ Cover archive complete.\nArchived: {res['sent']}/{res['total']} (failed {res['failed']}).",
            reply_markup=keyboards.back_admin_kb("admin:vault"),
        )
    except Exception as e:  # noqa: BLE001
        log.exception("cover archive failed")
        await status.edit_text(
            f"❌ Archiving failed: {e}", reply_markup=keyboards.back_admin_kb("admin:vault")
        )


async def clear_channel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    if not config.is_owner(q.from_user.id):
        return
    await settings_q.set(SETTING_KEY, "")
    await vault_view(update, context)


# ---- setting the channel: /setbackup <id>  OR  forward from the channel ----
async def set_backup_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not config.is_owner(update.effective_user.id):
        return
    text = update.message.text or ""
    parts = text.split(maxsplit=1)
    if len(parts) < 2 or not parts[1].strip().lstrip("-").isdigit():
        await update.message.reply_text(
            "Usage: <code>/setbackup -100XXXXXXXXXX</code>\n"
            "Or just forward any message from your backup channel to me.",
            parse_mode="HTML",
        )
        return
    cid = parts[1].strip()
    await _apply_channel(update, context, cid)


async def on_forwarded(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """If the owner forwards a message from a channel, register it as the vault."""
    if not config.is_owner(update.effective_user.id):
        return
    msg = update.message
    chat = None
    fo = getattr(msg, "forward_origin", None)
    if fo is not None and getattr(fo, "chat", None) is not None:
        chat = fo.chat
    elif getattr(msg, "forward_from_chat", None) is not None:
        chat = msg.forward_from_chat
    if chat is None or getattr(chat, "type", None) != "channel":
        return  # not a channel forward — ignore
    await _apply_channel(update, context, str(chat.id), name=getattr(chat, "title", None))


async def _apply_channel(update, context, cid: str, name: str = None):
    # verify the bot can post there
    try:
        test = await context.bot.send_message(cid, "✅ AnimeZone backup channel connected. Backups will appear here.")
    except Exception as e:  # noqa: BLE001
        await update.message.reply_text(
            f"❌ I can't post to that channel: {e}\n\n"
            "Add me as an <b>admin</b> of the channel (with permission to post), then try again.",
            parse_mode="HTML",
        )
        return
    await settings_q.set(SETTING_KEY, cid)
    label = f" (<b>{name}</b>)" if name else ""
    await update.message.reply_text(
        f"✅ Backup channel set to <code>{cid}</code>{label}.\n\n"
        "I'll post the daily backup here at 03:30 IST. Use <b>Admin → 🗄️ Backup Vault</b> "
        "to back up now or archive covers.",
        parse_mode="HTML",
    )
