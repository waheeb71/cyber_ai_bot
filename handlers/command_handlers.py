import logging
import asyncio
from telegram import Update
from telegram.ext import ContextTypes
from telegram.constants import ChatMemberStatus
from database import Database
from admin_panel import is_admin
from config import ADMIN_NOTIFICATION_ID
from .utils import get_base_keyboard

logger = logging.getLogger(__name__)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE, db: Database):
    """Send a message when the command /start is issued."""
    user = update.effective_user
    user_id = user.id

    if user.username and is_admin(user.username):
        await update.message.reply_text(f"Your numeric ID is: {user_id}")

   # is_new_user = str(user_id) not in db.get_all_users()
    is_new_user = str(user_id) not in db.get_all_users_data()

    db.add_user(user_id, user.username or "", user.first_name)

    if is_new_user and ADMIN_NOTIFICATION_ID:
        admin_notification = (
            f"🔔 مستخدم جديد انضم للبوت:\n"
            f"الاسم: {user.first_name}\n"
            f"المعرف: @{user.username if user.username else 'لا يوجد'}\n"
            f"الآيدي: {user_id}"
        )
        try:
            await context.bot.send_message(chat_id=ADMIN_NOTIFICATION_ID, text=admin_notification)
        except Exception as e:
            logger.error(f"Failed to send admin notification: {e}")

    if db.is_user_banned(user_id):
        await update.message.reply_text("عذراً، تم حظرك من استخدام البوت.")
        return

    db.clear_conversation_history(user_id)
    welcome_message = (
        f"مرحباً بك {user.first_name} في بوت المساعد الذكي للطلاب! 👋\n\n"
        "يمكنني مساعدتك في:\n"
        "- الإجابة على الأسئلة الأكاديمية\n"
        "- شرح المفاهيم المعقدة\n"
        "- تحليل الصور وشرح محتواها\n"
        "- المساعدة في حل المسائل\n"
        "- تقديم نصائح للدراسة\n\n"
        "- البحث في الويب باستخدام الذكاء الاصطناعي 🔍\n\n"
        "يمكنك إرسال سؤال نصي أو صورة وسأقوم بمساعدتك! 📚✨\n\n"
        "━━━━━━━━━━━━━━\n"
        "📢 قناة التلجرام: @SyberSc71\n"
        "👨‍💻 برمجة: @WAT4F"
    )
    await update.message.reply_text(
        welcome_message,
        reply_markup=get_base_keyboard()
    )

async def clear_messages(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Clear messages in a group chat."""
    if not update.message or not update.message.chat.type in ['group', 'supergroup']:
        await update.message.reply_text("هذا الأمر يعمل فقط في المجموعات!")
        return

    try:
        chat_member = await context.bot.get_chat_member(update.message.chat_id, context.bot.id)
        if not chat_member.can_delete_messages:
            await update.message.reply_text("عذراً، لا أملك صلاحية حذف الرسائل في هذه المجموعة!")
            return
    except Exception as e:
        logger.error(f"Could not check bot permissions in clear_messages: {e}")
        await update.message.reply_text("حدث خطأ أثناء التحقق من الصلاحيات.")
        return

    try:
        await update.message.delete()
        message_id = update.message.message_id

        # Telegram API allows deleting messages up to 48 hours old.
        # Deleting a wide range of IDs might fail for old messages.
        # It's better to fetch recent message IDs if possible, but for a simple clear, this is a start.
        for i in range(message_id - 100, message_id):
            try:
                await context.bot.delete_message(update.message.chat_id, i)
            except Exception:
                continue # Ignore errors for messages that can't be deleted

        msg = await context.bot.send_message(update.message.chat_id, "تم تنظيف الرسائل! ✨")
        await asyncio.sleep(5)
        await msg.delete()

    except Exception as e:
        logger.error(f"Error in clear_messages: {e}")
        await context.bot.send_message(update.message.chat_id, "حدث خطأ أثناء محاولة حذف الرسائل.")
