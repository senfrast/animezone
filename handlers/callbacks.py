"""Central callback query router (registered LAST)."""
import logging

from telegram import Update
from telegram.ext import ContextTypes

import config
from handlers import start as start_h
from handlers.admin import categories as admin_cats
from handlers.admin import edit as admin_edit
from handlers.admin import manage as admin_manage
from handlers.admin import panel as admin_panel
from handlers.user import settings as user_settings

log = logging.getLogger("callbacks")


async def router(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    if q is None:
        return
    data = q.data or ""

    # --- generic / user ---
    if data == "start":
        await q.answer()
        is_admin = config.is_admin(q.from_user.id)
        from utils import keyboards
        from database.queries import settings as settings_q

        welcome = await settings_q.get("welcome_message", "🎌 Welcome to AnimeZone!")
        await q.edit_message_text(welcome, reply_markup=keyboards.start_kb(is_admin))
        return
    if data == "help":
        await start_h.help_cmd(update, context)
        return
    if data == "usettings":
        await user_settings.show_settings(update, context)
        return
    if data == "uset:nsfw":
        await user_settings.toggle_nsfw_prompt(update, context)
        return
    if data == "uset:nsfw_yes":
        await user_settings.toggle_nsfw_confirm(update, context)
        return
    if data == "uset:notif":
        await user_settings.toggle_notifications(update, context)
        return

    # --- approval workflow (owner only, checked inside handlers) ---
    if data.startswith("approve:"):
        await admin_panel.approve_title(update, context)
        return
    if data.startswith("reject:"):
        await admin_panel.reject_title(update, context)
        return
    if data.startswith("delmod:"):
        await admin_manage.remove_mod(update, context)
        return
    if data.startswith("egen:"):
        await admin_edit.open_genres(update, context)
        return
    if data.startswith("egt:"):
        await admin_edit.toggle_genre(update, context)
        return
    if data.startswith("egdone:"):
        await admin_edit.done_genres(update, context)
        return
    if data.startswith("clrm:"):
        from handlers.admin import clones as admin_clones
        await admin_clones.remove_clone(update, context)
        return
    if data.startswith("bkv:"):
        from handlers.admin import backup_vault as admin_vault
        if not config.is_owner(q.from_user.id):
            await q.answer("⛔ Owner only", show_alert=True)
            return
        action = data.split(":", 1)[1]
        if action == "full":
            await admin_vault.full_backup(update, context)
        elif action == "restore":
            await admin_vault.restore_prompt(update, context)
        elif action == "restore_yes":
            await admin_vault.restore_run(update, context)
        elif action == "json":
            await admin_vault.backup_json(update, context)
        elif action == "covers":
            await admin_vault.archive_covers(update, context)
        elif action == "help":
            await admin_vault.help_view(update, context)
        elif action == "clear":
            await admin_vault.clear_channel(update, context)
        else:
            await q.answer()
        return

    # --- admin gate ---
    if data.startswith("admin:"):
        if not config.is_admin(q.from_user.id):
            await q.answer("⛔ Admins only", show_alert=True)
            return
        # Actions a moderator (non-owner) is allowed to reach:
        MODERATOR_OK = {"admin:home", "admin:addtitle"}
        if not config.is_owner(q.from_user.id) and data not in MODERATOR_OK:
            await q.answer("⛔ Owner only", show_alert=True)
            return
        if data == "admin:home":
            await admin_panel.admin_home(update, context)
        elif data == "admin:pending":
            await admin_panel.pending_approvals(update, context)
        elif data == "admin:mods":
            await admin_manage.mods_view(update, context)
        elif data == "admin:backup":
            await admin_manage.backup_now(update, context)
        elif data == "admin:cats":
            await admin_cats.list_cats(update, context)
        elif data.startswith("admin:titles"):
            await admin_panel.titles_page(update, context)
        elif data == "admin:featured":
            await admin_panel.featured_list(update, context)
        elif data == "admin:requests":
            await admin_panel.requests_list(update, context)
        elif data == "admin:users":
            await admin_panel.user_stats(update, context)
        elif data == "admin:dash":
            await admin_panel.dashboard(update, context)
        elif data == "admin:top":
            await admin_panel.top_titles(update, context)
        elif data == "admin:validate":
            await admin_panel.validate_links(update, context)
        elif data == "admin:export":
            await admin_panel.export_csv(update, context)
        elif data == "admin:settings":
            await admin_panel.settings_view(update, context)
        elif data == "admin:clones":
            from handlers.admin import clones as admin_clones
            await admin_clones.clones_view(update, context)
        elif data == "admin:vault":
            from handlers.admin import backup_vault as admin_vault
            await admin_vault.vault_view(update, context)
        else:
            await q.answer()
        return

    # unknown
    await q.answer()
