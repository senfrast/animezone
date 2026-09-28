"""Admin panel home + read-only dashboards + simple actions."""
import csv
import io
import logging

from telegram import Update
from telegram.ext import ContextTypes

import config
from database.queries import analytics as analytics_q
from database.queries import titles as titles_q
from database.queries import users as users_q
from services import link_validator
from utils import keyboards
from utils.decorators import admin_only, owner_only

log = logging.getLogger("admin")


async def _render_home(target, user_id, edit=True):
    is_owner = config.is_owner(user_id)
    if not is_owner:
        # Moderator view — minimal, no sensitive stats.
        text = (
            "🛠️ <b>SUB-ADMIN PANEL</b>\n\n"
            "You can submit new titles. Each submission is reviewed by the owner "
            "and goes live only after approval.\n\n"
            "Tap <b>➕ Add New Title</b> to begin."
        )
        kb = keyboards.admin_home_kb(is_owner=False)
    else:
        stats = await analytics_q.quick_stats()
        pending = await titles_q.count_pending()
        text = (
            "👑 <b>ANIMEZONE ADMIN PANEL</b>\n\n"
            "━━━ 📊 QUICK STATS ━━━━━━\n"
            f"👥 Users: {stats['users']} │ 📱 Opens Today: {stats['opens_today']}\n"
            f"🔗 Clicks Today: {stats['clicks_today']} │ 📂 Titles: {stats['titles']}\n"
            f"🕒 Pending Approvals: {pending} │ 📝 Requests: {stats['pending_requests']}"
        )
        kb = keyboards.admin_home_kb(is_owner=True, pending=pending)
    if hasattr(target, "edit_message_text") and edit:
        await target.edit_message_text(text, reply_markup=kb, parse_mode="HTML")
    else:
        await target.reply_text(text, reply_markup=kb, parse_mode="HTML")


@admin_only
async def admin_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await _render_home(update.message, update.effective_user.id, edit=False)


async def admin_home(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    await _render_home(q.message, q.from_user.id)


async def dashboard(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    rng = await analytics_q.range_stats()
    days = await analytics_q.last_7_days()
    top = await analytics_q.top_titles_week(5)

    today = rng["today"] or {}
    week = rng["week"] or {}
    lines = ["📊 <b>ANALYTICS DASHBOARD</b>\n"]
    lines.append("<b>Today</b>")
    lines.append(f"  Opens: {today.get('total_app_opens',0)} │ Clicks: {today.get('total_clicks',0)} │ New: {today.get('total_new_users',0)}")
    lines.append("<b>Last 7 days</b>")
    lines.append(f"  Opens: {week.get('opens',0)} │ Clicks: {week.get('clicks',0)} │ New users: {week.get('new_users',0)}")
    lines.append("\n<b>7-Day Clicks</b>")
    max_c = max([d["total_clicks"] for d in days], default=0) or 1
    for d in days:
        bar = "█" * max(1, int((d["total_clicks"] / max_c) * 12)) if d["total_clicks"] else "▁"
        lines.append(f"  {d['date'].strftime('%d/%m')} {bar} {d['total_clicks']}")
    lines.append("\n<b>Top titles this week</b>")
    if top:
        for i, t in enumerate(top, 1):
            lines.append(f"  {i}. {t['title']} — {t['clicks']}")
    else:
        lines.append("  (no data yet)")
    await q.edit_message_text("\n".join(lines), reply_markup=keyboards.back_admin_kb(), parse_mode="HTML")


async def user_stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    total = await users_q.count_users()
    stats = await analytics_q.quick_stats()
    text = (
        "👥 <b>USER STATS</b>\n\n"
        f"Total users: {total}\n"
        f"App opens today: {stats['opens_today']}\n"
        f"Clicks today: {stats['clicks_today']}"
    )
    await q.edit_message_text(text, reply_markup=keyboards.back_admin_kb(), parse_mode="HTML")


async def top_titles(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    rows = await titles_q.popular(True, 10)
    lines = ["🔥 <b>TOP TITLES (all-time clicks)</b>\n"]
    if rows:
        for i, r in enumerate(rows, 1):
            lines.append(f"{i}. {r['title']} — {r['total_clicks']} clicks")
    else:
        lines.append("No titles yet. Add some!")
    await q.edit_message_text("\n".join(lines), reply_markup=keyboards.back_admin_kb(), parse_mode="HTML")


async def requests_list(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    rows = await analytics_q.pending_requests()
    lines = ["📝 <b>CONTENT REQUESTS (pending)</b>\n"]
    if rows:
        for r in rows:
            lines.append(f"• {r['title_requested']} ({r['category'] or '—'}) — /req_done_{r['request_id']}")
    else:
        lines.append("No pending requests.")
    await q.edit_message_text("\n".join(lines), reply_markup=keyboards.back_admin_kb(), parse_mode="HTML")


async def featured_list(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    rows = await titles_q.list_featured()
    lines = ["⭐ <b>FEATURED TITLES</b>\n"]
    if rows:
        for r in rows:
            lines.append(f"• [{r['featured_order']}] {r['title']} — remove: /unfeature_{r['title_id']}")
    else:
        lines.append("None featured yet.")
    lines.append("\nTo feature a title, open <b>View All Titles</b> and tap ⭐.")
    await q.edit_message_text("\n".join(lines), reply_markup=keyboards.back_admin_kb(), parse_mode="HTML")


async def validate_links(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer("Checking channels…")
    await q.edit_message_text("🔗 Validating channels, please wait…")
    dead = await link_validator.validate_all(context.bot)
    if dead:
        text = "🔗 <b>Dead channels:</b>\n" + "\n".join(f"• {d}" for d in dead[:30])
    else:
        text = "✅ All channels are alive."
    await q.edit_message_text(text, reply_markup=keyboards.back_admin_kb(), parse_mode="HTML")


async def export_csv(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer("Generating…")
    from database import pool as db

    # users csv
    urows = await db.fetch("SELECT user_id, username, first_name, app_opens_count, total_clicks, first_seen_at FROM users ORDER BY first_seen_at")
    ubuf = io.StringIO()
    uw = csv.writer(ubuf)
    uw.writerow(["user_id", "username", "first_name", "app_opens", "clicks", "first_seen"])
    for r in urows:
        uw.writerow([r["user_id"], r["username"], r["first_name"], r["app_opens_count"], r["total_clicks"], r["first_seen_at"]])
    await context.bot.send_document(
        chat_id=q.from_user.id,
        document=io.BytesIO(ubuf.getvalue().encode()),
        filename="users.csv",
    )
    # titles csv
    trows = await db.fetch("SELECT title_id, title, slug, language, status, total_clicks, total_joins FROM titles ORDER BY title_id")
    tbuf = io.StringIO()
    tw = csv.writer(tbuf)
    tw.writerow(["title_id", "title", "slug", "language", "status", "clicks", "joins"])
    for r in trows:
        tw.writerow([r["title_id"], r["title"], r["slug"], r["language"], r["status"], r["total_clicks"], r["total_joins"]])
    await context.bot.send_document(
        chat_id=q.from_user.id,
        document=io.BytesIO(tbuf.getvalue().encode()),
        filename="titles.csv",
    )
    await q.edit_message_text("📤 Export sent above.", reply_markup=keyboards.back_admin_kb())


async def settings_view(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    from database.queries import settings as settings_q

    s = await settings_q.all_settings(force=True)
    lines = ["⚙️ <b>PLATFORM SETTINGS</b>\n"]
    for k in ["app_name", "app_tagline", "max_featured", "max_bookmarks_per_user", "items_per_page", "maintenance_mode"]:
        lines.append(f"• <b>{k}</b>: {s.get(k)}")
    lines.append("\nEdit with: <code>/set key value</code>")
    await q.edit_message_text("\n".join(lines), reply_markup=keyboards.back_admin_kb(), parse_mode="HTML")


@owner_only
async def set_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    from database.queries import settings as settings_q

    if len(context.args) < 2:
        await update.message.reply_text("Usage: /set <key> <value>")
        return
    key = context.args[0]
    value = " ".join(context.args[1:])
    await settings_q.set(key, value)
    await update.message.reply_text(f"✅ {key} = {value}")


@owner_only
async def req_done_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text or ""
    rid = text.replace("/req_done_", "").strip()
    if rid.isdigit():
        await analytics_q.set_request_status(int(rid), "done")
        await update.message.reply_text(f"✅ Request #{rid} marked done.")


@owner_only
async def unfeature_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text or ""
    tid = text.replace("/unfeature_", "").strip()
    if tid.isdigit():
        await titles_q.set_featured(int(tid), False, 0)
        await update.message.reply_text(f"✅ Title #{tid} removed from featured.")


@owner_only
async def feature_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text or ""
    tid = text.replace("/feature_", "").strip()
    if tid.isdigit():
        rows = await titles_q.list_featured()
        order = len(rows) + 1
        await titles_q.set_featured(int(tid), True, order)
        await update.message.reply_text(f"⭐ Title #{tid} is now featured (order {order}).")


@owner_only
async def del_title_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text or ""
    tid = text.replace("/delete_", "").strip()
    if not tid.isdigit():
        return
    name = await titles_q.delete(int(tid))
    if name is None:
        await update.message.reply_text(f"⚠️ Title #{tid} not found (or already in Trash).")
        return
    await update.message.reply_text(
        f"🗑️ <b>{name}</b> (#{tid}) moved to Trash — it's hidden from the app "
        f"but <b>not gone</b>.\n\n↩️ Tap /restore_{tid} to bring it back.\n"
        f"🗂️ /trash to see everything you can restore.",
        parse_mode="HTML",
    )


@owner_only
async def restore_title_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text or ""
    tid = text.replace("/restore_", "").strip()
    if not tid.isdigit():
        return
    name = await titles_q.restore(int(tid))
    if name is None:
        await update.message.reply_text(f"⚠️ Title #{tid} was not in Trash.")
        return
    await update.message.reply_text(
        f"✅ <b>{name}</b> (#{tid}) restored and visible in the app again.",
        parse_mode="HTML",
    )


@owner_only
async def trash_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    rows = await titles_q.list_trash()
    if not rows:
        await update.message.reply_text("🗂️ Trash is empty — nothing to restore. ✅")
        return
    lines = ["🗂️ <b>TRASH</b> — tap /restore_&lt;id&gt; to bring one back:\n"]
    for r in rows[:50]:
        when = r["deleted_at"].strftime("%Y-%m-%d %H:%M") if r.get("deleted_at") else ""
        lines.append(f"• <b>{r['title']}</b> (#{r['title_id']}) · deleted {when} → /restore_{r['title_id']}")
    await update.message.reply_text("\n".join(lines), parse_mode="HTML")


async def pending_approvals(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Owner-only queue of titles awaiting approval."""
    from telegram import InlineKeyboardButton, InlineKeyboardMarkup

    q = update.callback_query
    await q.answer()
    if not config.is_owner(q.from_user.id):
        await q.answer("⛔ Owner only", show_alert=True)
        return
    rows = await titles_q.list_pending()
    if not rows:
        await q.edit_message_text(
            "🕒 <b>PENDING APPROVALS</b>\n\nNothing waiting. You're all caught up! ✅",
            reply_markup=keyboards.back_admin_kb(),
            parse_mode="HTML",
        )
        return
    await q.edit_message_text(
        f"🕒 <b>PENDING APPROVALS ({len(rows)})</b>\n\nReview each below 👇",
        reply_markup=keyboards.back_admin_kb(),
        parse_mode="HTML",
    )
    for r in rows[:15]:
        caption = (
            f"<b>{r['title']}</b>\n"
            f"📂 {r['category_emoji']} {r['category_name']}\n"
            f"🌐 {r['language']} · 📊 {r['status']} · 📺 {r['episode_count']} eps\n"
            f"🔞 {'Yes' if r['is_nsfw'] else 'No'}\n"
            f"🔗 {r['channel_link']}\n"
            f"👤 Submitted by: {r['added_by']}"
        )
        from handlers.admin.edit import pending_kb
        kb = pending_kb(r["title_id"])
        try:
            if r["image_file_id"]:
                await context.bot.send_photo(q.from_user.id, r["image_file_id"], caption=caption, reply_markup=kb, parse_mode="HTML")
            else:
                await context.bot.send_message(q.from_user.id, caption, reply_markup=kb, parse_mode="HTML")
        except Exception:  # noqa: BLE001
            pass


async def approve_title(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    if not config.is_owner(q.from_user.id):
        await q.answer("⛔ Owner only", show_alert=True)
        return
    # Answer the callback FIRST so the button never hangs, even if the DB
    # round-trips to Singapore take a moment.
    try:
        await q.answer("⏳ Approving…")
    except Exception:  # noqa: BLE001
        pass
    tid = int(q.data.split(":")[1])
    pending = await titles_q.get_pending_by_id(tid)
    if not pending:
        await _mark_handled(q, "⚠️ Already handled or not found.")
        return
    row = await titles_q.approve(tid)
    await categories_q.refresh_count(row["category_id"])
    await _mark_handled(q, f"✅ APPROVED — {row['title']} is now live.")
    # notify the moderator who submitted it
    if row["added_by"]:
        try:
            await context.bot.send_message(
                row["added_by"], f"✅ Your submission <b>{row['title']}</b> was approved and is now live!",
                parse_mode="HTML",
            )
        except Exception:  # noqa: BLE001
            pass


async def reject_title(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    if not config.is_owner(q.from_user.id):
        await q.answer("⛔ Owner only", show_alert=True)
        return
    # Answer the callback FIRST so the button never hangs.
    try:
        await q.answer("🗑️ Rejecting…")
    except Exception:  # noqa: BLE001
        pass
    tid = int(q.data.split(":")[1])
    pending = await titles_q.get_pending_by_id(tid)
    if not pending:
        await _mark_handled(q, "⚠️ Already handled or not found.")
        return
    submitter = pending["added_by"]
    title_name = pending["title"]
    # A rejected submission was never live — remove it permanently so it
    # disappears from the pending queue (soft-delete would keep it queued).
    await titles_q.hard_delete(tid)
    await _mark_handled(q, f"🗑️ REJECTED — {title_name} was removed.")
    if submitter:
        try:
            await context.bot.send_message(
                submitter, f"🗑️ Your submission <b>{title_name}</b> was not approved by the owner.",
                parse_mode="HTML",
            )
        except Exception:  # noqa: BLE001
            pass


async def _mark_handled(q, text):
    try:
        if q.message and q.message.caption is not None:
            await q.edit_message_caption(caption=text, reply_markup=None)
        else:
            await q.edit_message_text(text, reply_markup=None)
    except Exception:  # noqa: BLE001
        pass


async def _clear_markup(q):
    try:
        await q.edit_message_reply_markup(reply_markup=None)
    except Exception:  # noqa: BLE001
        pass


async def titles_page(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    data = q.data  # admin:titles:<offset>
    parts = data.split(":")
    offset = int(parts[2]) if len(parts) > 2 else 0
    rows = await titles_q.list_all(limit=10, offset=offset)
    total = await titles_q.count_all()
    lines = [f"📋 <b>ALL TITLES</b> ({total})\n"]
    if rows:
        for i, r in enumerate(rows, start=offset + 1):
            star = "⭐" if r["is_featured"] else ""
            nsfw = "🔞" if r["is_nsfw"] else ""
            lines.append(
                f"{i}. {star}{nsfw} <b>{r['title']}</b>\n"
                f"   ✏️ /edit_{r['title_id']} │ ⭐ /feature_{r['title_id']} │ 🗑️ /delete_{r['title_id']}"
            )
    else:
        lines.append("No titles yet. Use ➕ Add New Title.")
    from telegram import InlineKeyboardButton, InlineKeyboardMarkup

    nav = []
    if offset > 0:
        nav.append(InlineKeyboardButton("⬅️ Prev", callback_data=f"admin:titles:{max(offset-10,0)}"))
    if offset + 10 < total:
        nav.append(InlineKeyboardButton("Next ➡️", callback_data=f"admin:titles:{offset+10}"))
    kb_rows = []
    if nav:
        kb_rows.append(nav)
    kb_rows.append([InlineKeyboardButton("🔙 Back to Panel", callback_data="admin:home")])
    await q.edit_message_text("\n".join(lines), reply_markup=InlineKeyboardMarkup(kb_rows), parse_mode="HTML")
