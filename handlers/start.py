"""/start command with deep linking, /help, /cancel."""
import logging

from telegram import Update
from telegram.ext import ContextTypes, ConversationHandler

import config
from database.queries import analytics as analytics_q
from database.queries import settings as settings_q
from database.queries import titles as titles_q
from database.queries import users as users_q
from utils import keyboards

log = logging.getLogger("start")


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    existing = await users_q.get_user(user.id)
    is_new = existing is None

    source = "organic"
    referred_by = None
    deep_slug = None
    if context.args:
        arg = context.args[0]
        if arg.startswith("title_"):
            deep_slug = arg[len("title_"):]
            source = "deeplink"
        elif arg.startswith("ref_") and arg[4:].isdigit():
            referred_by = int(arg[4:])
            source = "referral"

    await users_q.upsert_user(
        {
            "id": user.id,
            "username": user.username,
            "first_name": user.first_name,
            "last_name": user.last_name,
            "language_code": user.language_code,
        },
        source=source,
        referred_by=referred_by,
    )
    if is_new:
        await analytics_q.register_new_user_today()

    # maintenance / ban
    if await users_q.is_banned(user.id):
        await update.message.reply_text("🚫 Your access has been restricted.")
        return
    if await settings_q.get_bool("maintenance_mode"):
        msg = await settings_q.get("maintenance_message", "🔧 Under maintenance.")
        if not config.is_admin(user.id):
            await update.message.reply_text(msg)
            return

    welcome = await settings_q.get(
        "welcome_message",
        "🎌 Welcome to AnimeZone!\n\nBrowse thousands of anime, movies, and web series — all in one place!\n\nTap the button below to start exploring!",
    )
    is_admin = config.is_admin(user.id)

    if deep_slug:
        row = await titles_q.get_by_slug(deep_slug)
        if row:
            await update.message.reply_text(
                f"🎬 <b>{row['title']}</b>\n\nTap below to open it in AnimeZone 👇",
                reply_markup=keyboards.start_kb_title(deep_slug, is_admin),
                parse_mode="HTML",
            )
            return

    await update.message.reply_text(
        welcome, reply_markup=keyboards.start_kb(is_admin)
    )


async def help_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = (
        "❓ <b>How to use AnimeZone</b>\n\n"
        "1️⃣ Tap <b>Open AnimeZone</b> to launch the app.\n"
        "2️⃣ Browse Anime, Movies & Web Series.\n"
        "3️⃣ Tap a title → <b>Join Channel</b> to get content.\n"
        "4️⃣ Save favourites with the bookmark icon.\n"
        "5️⃣ Use /settings to toggle 18+ content & notifications.\n\n"
        "Enjoy! 🎌"
    )
    if update.callback_query:
        await update.callback_query.answer()
        await update.callback_query.message.reply_text(text, parse_mode="HTML")
    else:
        await update.message.reply_text(text, parse_mode="HTML")


async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data.clear()
    if update.message:
        await update.message.reply_text("❌ Cancelled.")
    return ConversationHandler.END
