import logging
import datetime
from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import ContextTypes
import telegram.error

from database import Database
from admin_panel import (
    handle_admin_callback, execute_groups_broadcast, show_groups,
    get_groups_keyboard, get_admin_keyboard
)
from .utils import check_subscription

logger = logging.getLogger(__name__)

async def check_subscription_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle the 'check_subscription' callback button."""
    query = update.callback_query
    user_id = query.from_user.id

    if await check_subscription(user_id, context):
        await query.answer("✅ شكراً لك! يمكنك الآن استخدام البوت.", show_alert=True)
        await query.message.edit_text(
            "تم التحقق من اشتراكك بنجاح! يمكنك الآن الضغط على /start لبدء محادثة جديدة أو إرسال رسالتك مباشرة. ✅"
        )
    else:
        await query.answer("❌ عذراً، لا تزال غير مشترك في القناة. يرجى الاشتراك أولاً.", show_alert=True)

async def admin_callback_wrapper(update: Update, context: ContextTypes.DEFAULT_TYPE, db: Database):
    """Wrapper for all admin-related callback queries."""
    query = update.callback_query

    # It's better to check for admin status using user ID from a trusted source if possible
    # For now, username is used as per original code.
    if not query.from_user.username or not is_admin(query.from_user.username):
        await query.answer("عذراً، هذا الأمر متاح للمشرفين فقط.", show_alert=True)
        return

    try:
        if query.data == "confirm_broadcast":
            await execute_groups_broadcast(query, context, db)
        # This part has complex logic and dependencies on admin_panel, so we keep it tight
        # In a larger refactor, this logic might move to the admin_panel module itself
        elif query.data in ["groups_stats", "groups_search", "groups_inactive", "groups_refresh", "groups_cleanup"]:
             if query.data == "groups_stats":
                await show_groups(query, db)
             # Other admin group actions...
        else:
            # Fallback to the generic admin callback handler
            await handle_admin_callback(update, context, db)

    except Exception as e:
        logger.error(f"Error in admin_callback_wrapper: {e}", exc_info=True)
        try:
            await query.message.edit_text(
                "⚠️ حدث خطأ أثناء تنفيذ العملية\nالرجاء المحاولة مرة أخرى",
                reply_markup=get_admin_keyboard()
            )
        except telegram.error.TelegramError as tg_err:
            logger.error(f"Failed to send error message to admin: {tg_err}")
