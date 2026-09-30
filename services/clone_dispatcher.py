"""Handles incoming updates for clone bots.

Deliberately lightweight: no PTB Application/ConversationHandler per clone. One
shared set of async functions processes updates for every clone, using the
clone's own ``telegram.Bot`` (from clone_manager) to reply. State needed for the
broadcast flow is kept in a tiny in-memory dict.
"""
import logging

from telegram import (
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    Update,
    WebAppInfo,
)

import config
from database.queries import analytics as analytics_q
from database.queries import clones as clones_q
from database.queries import settings as settings_q
from database.queries import titles as titles_q
from database.queries import users as users_q
from services import broadcast_engine, clone_manager
from utils import keyboards

log = logging.getLogger("clone.dispatch")

# (bot_id, owner_id) currently typing a broadcast message
_awaiting_broadcast: set[tuple[int, int]] = set()

WELCOME_TEXT = (
    "🎌 <b>Welcome to AnimeZone!</b>\n\n"
    "Browse thousands of anime, movies and web series — all in one place.\n\n"
    "Tap a button below 👇"
)

HELP_TEXT = (
    "❓ <b>How to use AnimeZone</b>\n\n"
    "1️⃣ Tap <b>Open AnimeZone</b> to launch the app.\n"
    "2️⃣ Browse Anime, Movies & Web Series.\n"
    "3️⃣ Tap a title → <b>Join Channel</b> to get content.\n"
    "4️⃣ Save favourites with the bookmark icon.\n"
    "5️⃣ Use <b>Settings</b> to toggle 18+ content & notifications.\n\n"
    "Enjoy! 🎌"
)


def _welcome_kb():
    return InlineKeyboardMarkup(
        [
            [InlineKeyboardButton("🎬 Open AnimeZone", web_app=WebAppInfo(url=config.MINI_APP_URL))],
            [InlineKeyboardButton("⚙️ Settings", callback_data="usettings"),
             InlineKeyboardButton("❓ Help", callback_data="help")],
        ]
    )


# backward-compat alias
def _open_app_kb():
    return _welcome_kb()


def _title_kb(slug: str):
    """Keyboard for a shared/deep-linked title — opens that exact title."""
    url = f"{config.MINI_APP_URL}#/title/{slug}"
    return InlineKeyboardMarkup(
        [
            [InlineKeyboardButton("🎬 Open This Title", web_app=WebAppInfo(url=url))],
            [InlineKeyboardButton("⚙️ Settings", callback_data="usettings"),
             InlineKeyboardButton("❓ Help", callback_data="help")],
        ]
    )


def _panel_kb(bot_id: int):
    on = clone_manager.is_maintenance(bot_id)
    maint = "🔴 Maintenance: ON — tap to turn OFF" if on else "🟢 Maintenance: OFF — tap to turn ON"
    return InlineKeyboardMarkup(
        [
            [InlineKeyboardButton("👥 User Stats", callback_data="cl:stats"),
             InlineKeyboardButton("📢 Broadcast", callback_data="cl:broadcast")],
            [InlineKeyboardButton("📊 Dashboard", callback_data="cl:dash")],
            [InlineKeyboardButton(maint, callback_data="cl:maint")],
        ]
    )


async def _send_panel(bot, bot_id: int, chat_id: int):
    clone = clone_manager.get_clone(bot_id) or {}
    name = clone.get("name") or clone.get("username") or "this bot"
    await bot.send_message(
        chat_id,
        f"👑 <b>{name} — Admin Panel</b>\n\n"
        "This is a clone of AnimeZone sharing the same content library.\n"
        "Choose an action 👇",
        reply_markup=_panel_kb(bot_id),
        parse_mode="HTML",
    )


async def dispatch(bot, bot_id: int, update: Update):
    try:
        if update.callback_query is not None:
            await _on_callback(bot, bot_id, update)
        elif update.message is not None:
            await _on_message(bot, bot_id, update)
    except Exception:  # noqa: BLE001
        log.exception("clone dispatch error (bot %s)", bot_id)


async def _on_message(bot, bot_id: int, update: Update):
    msg = update.message
    user = msg.from_user
    if user is None:
        return
    uid = user.id
    text = (msg.text or "").strip()
    is_owner = config.is_owner(uid)

    # Track every user of this clone (for per-clone stats & broadcast).
    await clones_q.upsert_subscriber(bot_id, user)

    # Owner is mid-broadcast: this message is the content.
    if is_owner and (bot_id, uid) in _awaiting_broadcast:
        _awaiting_broadcast.discard((bot_id, uid))
        if not text:
            await bot.send_message(uid, "❌ Broadcast needs text. Cancelled.")
            return
        await _do_broadcast(bot, bot_id, uid, text)
        return

    if text.startswith("/start"):
        # keep the shared users table in sync so Settings works everywhere
        try:
            await users_q.upsert_user(
                {"id": uid, "username": user.username, "first_name": user.first_name}
            )
        except Exception:  # noqa: BLE001
            pass
        # deep link: /start title_<slug>  ->  open that exact title
        parts = text.split(maxsplit=1)
        deep_slug = None
        if len(parts) > 1 and parts[1].strip().startswith("title_"):
            deep_slug = parts[1].strip()[len("title_"):]
        if deep_slug and not clone_manager.is_maintenance(bot_id):
            row = await titles_q.get_by_slug(deep_slug)
            if row:
                await bot.send_message(
                    uid,
                    f"🎬 <b>{row['title']}</b>\n\nTap below to open it in AnimeZone 👇",
                    reply_markup=_title_kb(deep_slug), parse_mode="HTML",
                )
                return
        if is_owner:
            await _send_panel(bot, bot_id, uid)
        elif clone_manager.is_maintenance(bot_id):
            await bot.send_message(uid, "🔧 This bot is under maintenance. Please check back soon!")
        else:
            await bot.send_message(
                uid, WELCOME_TEXT, reply_markup=_welcome_kb(), parse_mode="HTML"
            )
        return

    if text.startswith("/settings"):
        await _show_settings(bot, user)
        return

    if text.startswith("/help"):
        await bot.send_message(uid, HELP_TEXT, parse_mode="HTML")
        return

    if text.startswith("/panel") or text.startswith("/admin"):
        if is_owner:
            await _send_panel(bot, bot_id, uid)
        return

    # Any other message from a normal user -> nudge them to open the app.
    if not is_owner and not clone_manager.is_maintenance(bot_id):
        await bot.send_message(uid, "Tap a button below 👇", reply_markup=_welcome_kb())


# ---------------- user-facing settings/help (any user) ----------------
async def _show_settings(bot, user, message_id: int | None = None):
    uid = user.id
    row = await users_q.get_user(uid)
    if row is None:
        row = await users_q.upsert_user(
            {"id": uid, "username": getattr(user, "username", None),
             "first_name": getattr(user, "first_name", None)}
        )
    text = (
        "⚙️ <b>SETTINGS</b>\n\n"
        "━━━ CONTENT ━━━━━━━━━━━━\n"
        f"🔞 18+ Content: {'🟢 ON' if row['show_nsfw'] else '🔴 OFF'}\n\n"
        f"🔔 Notifications: {'🟢 ON' if row['notifications_enabled'] else '🔴 OFF'}"
    )
    kb = keyboards.user_settings_kb(row["show_nsfw"], row["notifications_enabled"])
    if message_id is not None:
        try:
            await bot.edit_message_text(chat_id=uid, message_id=message_id, text=text,
                                        reply_markup=kb, parse_mode="HTML")
            return
        except Exception:  # noqa: BLE001
            pass
    await bot.send_message(uid, text, reply_markup=kb, parse_mode="HTML")


async def _user_callback(bot, cq, data: str) -> bool:
    """Handle callbacks available to every user. Returns True if handled."""
    user = cq.from_user
    uid = user.id
    mid = cq.message.message_id if cq.message else None

    if data == "help":
        await bot.answer_callback_query(cq.id)
        await bot.send_message(uid, HELP_TEXT, parse_mode="HTML")
        return True
    if data == "start":
        await bot.answer_callback_query(cq.id)
        try:
            await bot.edit_message_text(chat_id=uid, message_id=mid, text=WELCOME_TEXT,
                                        reply_markup=_welcome_kb(), parse_mode="HTML")
        except Exception:  # noqa: BLE001
            await bot.send_message(uid, WELCOME_TEXT, reply_markup=_welcome_kb(), parse_mode="HTML")
        return True
    if data == "usettings":
        await bot.answer_callback_query(cq.id)
        await _show_settings(bot, user, mid)
        return True
    if data == "uset:nsfw":
        row = await users_q.get_user(uid)
        if row and row["show_nsfw"]:
            await users_q.set_nsfw(uid, False)
            await bot.answer_callback_query(cq.id)
            await _show_settings(bot, user, mid)
        else:
            await bot.answer_callback_query(cq.id)
            warning = await settings_q.get(
                "nsfw_warning_text",
                "⚠️ AGE VERIFICATION\n\nThis will show 18+ content.\n\nBy enabling, you confirm you are 18+.",
            )
            try:
                await bot.edit_message_text(chat_id=uid, message_id=mid, text=warning,
                                            reply_markup=keyboards.nsfw_confirm_kb())
            except Exception:  # noqa: BLE001
                await bot.send_message(uid, warning, reply_markup=keyboards.nsfw_confirm_kb())
        return True
    if data == "uset:nsfw_yes":
        await users_q.set_nsfw(uid, True)
        await bot.answer_callback_query(cq.id, "18+ content enabled")
        await _show_settings(bot, user, mid)
        return True
    if data == "uset:notif":
        row = await users_q.get_user(uid)
        newval = not (row and row["notifications_enabled"])
        await users_q.set_notifications(uid, newval)
        await bot.answer_callback_query(cq.id)
        await _show_settings(bot, user, mid)
        return True
    return False


async def _on_callback(bot, bot_id: int, update: Update):
    cq = update.callback_query
    uid = cq.from_user.id
    data = cq.data or ""

    # user-facing settings/help work for everyone
    if await _user_callback(bot, cq, data):
        return

    # everything below (clone admin panel) is owner-only
    if not config.is_owner(uid):
        await bot.answer_callback_query(cq.id, "⛔ Owner only", show_alert=True)
        return

    await bot.answer_callback_query(cq.id)

    if data == "cl:home":
        await _send_panel(bot, bot_id, uid)
        return

    if data == "cl:stats":
        total = await clones_q.sub_count(bot_id)
        new_today = await clones_q.sub_new_today(bot_id)
        active7 = await clones_q.sub_active_since(bot_id, 7)
        await bot.send_message(
            uid,
            f"👥 <b>User Stats (this bot)</b>\n\n"
            f"• Total users: <b>{total}</b>\n"
            f"• New today: <b>{new_today}</b>\n"
            f"• Active last 7 days: <b>{active7}</b>",
            reply_markup=_back_kb(),
            parse_mode="HTML",
        )
        return

    if data == "cl:dash":
        try:
            s = await analytics_q.quick_stats()
        except Exception:  # noqa: BLE001
            s = {"titles": 0, "opens_today": 0, "clicks_today": 0}
        subs = await clones_q.sub_count(bot_id)
        await bot.send_message(
            uid,
            f"📊 <b>Dashboard</b>\n\n"
            f"<b>Shared library</b>\n"
            f"• Titles: <b>{s.get('titles', 0)}</b>\n"
            f"• App opens today: <b>{s.get('opens_today', 0)}</b>\n"
            f"• Link clicks today: <b>{s.get('clicks_today', 0)}</b>\n\n"
            f"<b>This bot</b>\n"
            f"• Subscribers: <b>{subs}</b>\n"
            f"• Maintenance: <b>{'ON' if clone_manager.is_maintenance(bot_id) else 'OFF'}</b>",
            reply_markup=_back_kb(),
            parse_mode="HTML",
        )
        return

    if data == "cl:maint":
        new_state = not clone_manager.is_maintenance(bot_id)
        await clone_manager.set_maintenance(bot_id, new_state)
        await bot.send_message(
            uid,
            f"🔧 Maintenance mode is now <b>{'ON' if new_state else 'OFF'}</b>."
            + ("\nUsers now see a maintenance notice instead of the app." if new_state
               else "\nUsers can open the app again."),
            reply_markup=_panel_kb(bot_id),
            parse_mode="HTML",
        )
        return

    if data == "cl:broadcast":
        _awaiting_broadcast.add((bot_id, uid))
        await bot.send_message(
            uid,
            "📢 Send the message you want to broadcast to <b>this bot's</b> users.\n"
            "Send /cancel to abort.",
            parse_mode="HTML",
        )
        return


def _back_kb():
    return InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back to Panel", callback_data="cl:home")]])


async def _do_broadcast(bot, bot_id: int, owner_id: int, text: str):
    if text.strip() == "/cancel":
        await bot.send_message(owner_id, "❌ Broadcast cancelled.", reply_markup=_back_kb())
        return
    ids = await clones_q.subscriber_ids(bot_id)
    status = await bot.send_message(owner_id, f"📤 Broadcasting to {len(ids)} user(s)…")

    async def progress(i, total, sent, failed, blocked):
        try:
            await bot.edit_message_text(
                chat_id=owner_id, message_id=status.message_id,
                text=f"📤 {i}/{total} — sent {sent}, failed {failed}, blocked {blocked}",
            )
        except Exception:  # noqa: BLE001
            pass

    result = await broadcast_engine.broadcast_to(bot, ids, text, progress)
    try:
        await bot.edit_message_text(
            chat_id=owner_id, message_id=status.message_id,
            text=(f"✅ Broadcast complete.\nTotal: {result['total']}\n"
                  f"Sent: {result['sent']}\nFailed: {result['failed']}\nBlocked: {result['blocked']}"),
            reply_markup=_back_kb(),
        )
    except Exception:  # noqa: BLE001
        pass
