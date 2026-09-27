"""Handler decorators: @admin_only and @track_user."""
from functools import wraps

import config
from database.queries import users as users_q


def admin_only(func):
    @wraps(func)
    async def wrapper(update, context, *args, **kwargs):
        user = update.effective_user
        if not user or not config.is_admin(user.id):
            if update.callback_query:
                await update.callback_query.answer("⛔ Admins only", show_alert=True)
            elif update.message:
                await update.message.reply_text("⛔ This command is for admins only.")
            return
        return await func(update, context, *args, **kwargs)

    return wrapper


def owner_only(func):
    @wraps(func)
    async def wrapper(update, context, *args, **kwargs):
        user = update.effective_user
        if not user or not config.is_owner(user.id):
            if update.callback_query:
                await update.callback_query.answer(
                    "⛔ Only the owner can do this.", show_alert=True
                )
            elif update.message:
                await update.message.reply_text("⛔ Only the owner can use this.")
            return
        return await func(update, context, *args, **kwargs)

    return wrapper


def track_user(func):
    @wraps(func)
    async def wrapper(update, context, *args, **kwargs):
        user = update.effective_user
        if user:
            try:
                await users_q.upsert_user(
                    {
                        "id": user.id,
                        "username": user.username,
                        "first_name": user.first_name,
                        "last_name": user.last_name,
                        "language_code": user.language_code,
                    }
                )
            except Exception:  # noqa: BLE001
                pass
        return await func(update, context, *args, **kwargs)

    return wrapper
