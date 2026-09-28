"""Owner tools to edit a title's genres (inline toggle) and image (photo upload).

Works on ANY title by id, so it is used both from the Pending Approvals cards and
from the "View All Titles" list (via /edit_<id>)."""
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
from database.queries import titles as titles_q
from utils import keyboards

log = logging.getLogger("edit")

IMG_WAIT = 0


def pending_kb(tid: int):
    """The button layout shown on a pending-approval card."""
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("✅ Approve", callback_data=f"approve:{tid}"),
         InlineKeyboardButton("🗑️ Reject", callback_data=f"reject:{tid}")],
        [InlineKeyboardButton("✏️ Edit Genres", callback_data=f"egen:{tid}"),
         InlineKeyboardButton("🖼️ Edit Image", callback_data=f"eimg:{tid}")],
    ])


def _genre_kb(tid, selected, genres):
    rows, row = [], []
    for g in genres:
        mark = "✅ " if g["genre_id"] in selected else ""
        row.append(InlineKeyboardButton(
            f"{mark}{g['emoji']} {g['name']}", callback_data=f"egt:{tid}:{g['genre_id']}"))
        if len(row) == 3:
            rows.append(row)
            row = []
    if row:
        rows.append(row)
    rows.append([InlineKeyboardButton("✅ Done", callback_data=f"egdone:{tid}")])
    return InlineKeyboardMarkup(rows)


async def open_genres(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    if not config.is_owner(q.from_user.id):
        await q.answer("⛔ Owner only", show_alert=True)
        return
    await q.answer()
    tid = int(q.data.split(":")[1])
    genres = await titles_q.all_genres()
    sel = await titles_q.title_genre_ids(tid)
    try:
        await q.edit_message_reply_markup(reply_markup=_genre_kb(tid, sel, genres))
    except Exception:  # noqa: BLE001
        await q.message.reply_text("🎭 Toggle genres, then Done:", reply_markup=_genre_kb(tid, sel, genres))


async def toggle_genre(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    if not config.is_owner(q.from_user.id):
        await q.answer("⛔ Owner only", show_alert=True)
        return
    _, tid, gid = q.data.split(":")
    tid, gid = int(tid), int(gid)
    sel = await titles_q.title_genre_ids(tid)
    if gid in sel:
        await titles_q.remove_genre(tid, gid)
        await q.answer("Removed")
    else:
        await titles_q.add_genre(tid, gid)
        await q.answer("Added")
    genres = await titles_q.all_genres()
    sel = await titles_q.title_genre_ids(tid)
    try:
        await q.edit_message_reply_markup(reply_markup=_genre_kb(tid, sel, genres))
    except Exception:  # noqa: BLE001
        pass


async def done_genres(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer("Saved ✅")
    tid = int(q.data.split(":")[1])
    names = await titles_q.genres_full(tid)
    label = ", ".join(g["name"] for g in names) or "(none)"
    if await titles_q.is_pending(tid):
        # restore the approval buttons on the card
        try:
            await q.edit_message_reply_markup(reply_markup=pending_kb(tid))
        except Exception:  # noqa: BLE001
            pass
        await q.message.reply_text(f"✅ Genres updated: {label}")
    else:
        try:
            await q.edit_message_reply_markup(reply_markup=None)
        except Exception:  # noqa: BLE001
            pass
        await q.message.reply_text(
            f"✅ Genres updated: {label}", reply_markup=keyboards.back_admin_kb())


# ---- image edit (conversation) ----
async def image_entry(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    if not config.is_owner(q.from_user.id):
        return ConversationHandler.END
    tid = int(q.data.split(":")[1])
    context.user_data["edit_img_tid"] = tid
    await q.message.reply_text("🖼️ Send the new image (as a photo) for this title.\nSend /cancel to abort.")
    return IMG_WAIT


async def image_receive(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message.photo:
        await update.message.reply_text("⚠️ Please send a photo.")
        return IMG_WAIT
    tid = context.user_data.pop("edit_img_tid", None)
    if not tid:
        return ConversationHandler.END
    fid = update.message.photo[-1].file_id
    await titles_q.set_image(tid, fid)
    await update.message.reply_photo(
        photo=fid,
        caption="✅ Image updated for this title.",
        reply_markup=keyboards.back_admin_kb(),
    )
    return ConversationHandler.END


async def _cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data.pop("edit_img_tid", None)
    await update.message.reply_text("❌ Cancelled.")
    return ConversationHandler.END


def build_edit_image_conv() -> ConversationHandler:
    return ConversationHandler(
        entry_points=[CallbackQueryHandler(image_entry, pattern=r"^eimg:\d+$")],
        states={IMG_WAIT: [MessageHandler(filters.PHOTO, image_receive)]},
        fallbacks=[CommandHandler("cancel", _cancel)],
        allow_reentry=True,
    )


# ---- /edit_<id> entry from "View All Titles" ----
async def edit_menu_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not config.is_owner(update.effective_user.id):
        return
    tid = (update.message.text or "").replace("/edit_", "").strip()
    if not tid.isdigit():
        return
    tid = int(tid)
    row = await titles_q.get_by_id(tid)
    if not row:
        await update.message.reply_text("Title not found.")
        return
    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton("✏️ Edit Genres", callback_data=f"egen:{tid}"),
         InlineKeyboardButton("🖼️ Edit Image", callback_data=f"eimg:{tid}")],
        [InlineKeyboardButton("🔙 Back to Panel", callback_data="admin:home")],
    ])
    genres = await titles_q.genres_full(tid)
    glabel = ", ".join(g["name"] for g in genres) or "(none)"
    await update.message.reply_text(
        f"✏️ <b>Editing #{tid} — {row['title']}</b>\nCurrent genres: {glabel}",
        reply_markup=kb, parse_mode="HTML",
    )
