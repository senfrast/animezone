"""InlineKeyboardMarkup builders."""
from telegram import (
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    WebAppInfo,
)

import config


def start_kb(is_admin: bool):
    rows = [[InlineKeyboardButton("🎬 Open AnimeZone", web_app=WebAppInfo(url=config.MINI_APP_URL))]]
    rows.append([
        InlineKeyboardButton("⚙️ Settings", callback_data="usettings"),
        InlineKeyboardButton("❓ Help", callback_data="help"),
    ])
    if is_admin:
        rows.append([InlineKeyboardButton("👑 Admin Panel", callback_data="admin:home")])
    return InlineKeyboardMarkup(rows)


def start_kb_title(slug: str, is_admin: bool):
    url = f"{config.MINI_APP_URL}#/title/{slug}"
    rows = [[InlineKeyboardButton("🎬 Open This Title", web_app=WebAppInfo(url=url))]]
    rows.append([
        InlineKeyboardButton("⚙️ Settings", callback_data="usettings"),
        InlineKeyboardButton("❓ Help", callback_data="help"),
    ])
    if is_admin:
        rows.append([InlineKeyboardButton("👑 Admin Panel", callback_data="admin:home")])
    return InlineKeyboardMarkup(rows)


def user_settings_kb(show_nsfw: bool, notifications: bool):
    nsfw = "🟢 ON" if show_nsfw else "🔴 OFF"
    notif = "🟢 ON" if notifications else "🔴 OFF"
    return InlineKeyboardMarkup([
        [InlineKeyboardButton(f"🔞 18+ Content: {nsfw}", callback_data="uset:nsfw")],
        [InlineKeyboardButton(f"🔔 Notifications: {notif}", callback_data="uset:notif")],
        [InlineKeyboardButton("🔙 Back", callback_data="start")],
    ])


def nsfw_confirm_kb():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("✅ I am 18+ — Enable", callback_data="uset:nsfw_yes")],
        [InlineKeyboardButton("❌ Cancel", callback_data="usettings")],
    ])


def admin_home_kb(is_owner: bool = True, pending: int = 0):
    if not is_owner:
        # Limited sub-admin (moderator): may only submit titles for approval.
        return InlineKeyboardMarkup([
            [InlineKeyboardButton("➕ Add New Title", callback_data="admin:addtitle")],
        ])
    pend_label = f"🕒 Pending Approvals ({pending})" if pending else "🕒 Pending Approvals"
    return InlineKeyboardMarkup([
        [InlineKeyboardButton(pend_label, callback_data="admin:pending")],
        [InlineKeyboardButton("📂 Manage Categories", callback_data="admin:cats")],
        [InlineKeyboardButton("➕ Add New Title", callback_data="admin:addtitle")],
        [InlineKeyboardButton("📋 View All Titles", callback_data="admin:titles:0")],
        [InlineKeyboardButton("⭐ Manage Featured", callback_data="admin:featured")],
        [InlineKeyboardButton("📝 Content Requests", callback_data="admin:requests")],
        [InlineKeyboardButton("👥 User Stats", callback_data="admin:users"),
         InlineKeyboardButton("📢 Broadcast", callback_data="admin:broadcast")],
        [InlineKeyboardButton("📊 Dashboard", callback_data="admin:dash"),
         InlineKeyboardButton("🔥 Top Titles", callback_data="admin:top")],
        [InlineKeyboardButton("👮 Moderators", callback_data="admin:mods"),
         InlineKeyboardButton("🔗 Validate Links", callback_data="admin:validate")],
        [InlineKeyboardButton("🤖 Clone Bots", callback_data="admin:clones")],
        [InlineKeyboardButton("💾 Backup Now", callback_data="admin:backup"),
         InlineKeyboardButton("♻️ Restore Backup", callback_data="admin:restore")],
        [InlineKeyboardButton("🗄️ Backup Vault (channel)", callback_data="admin:vault")],
        [InlineKeyboardButton("📤 Export CSV", callback_data="admin:export"),
         InlineKeyboardButton("⚙️ Settings", callback_data="admin:settings")],
    ])


def back_admin_kb(target="admin:home"):
    return InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back to Panel", callback_data=target)]])


def confirm_kb(yes_cb: str, no_cb: str, yes="✅ Yes", no="❌ Cancel"):
    return InlineKeyboardMarkup([
        [InlineKeyboardButton(yes, callback_data=yes_cb)],
        [InlineKeyboardButton(no, callback_data=no_cb)],
    ])
