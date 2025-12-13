from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from ..config import ADMIN_USERS, BOT_SIGNATURE
from datetime import datetime
import logging
import asyncio

logger = logging.getLogger(__name__)

# Import prompt management functions
from .prompt_management import (
    show_prompt_menu, view_current_prompt,
    start_edit_prompt, reset_to_default_prompt, handle_new_prompt,
    get_prompt_keyboard
)
from .broadcast import start_broadcast

def is_admin(username: str) -> bool:
    """Check if user is admin."""
    return username in ADMIN_USERS

def get_admin_keyboard():
    """Get admin panel keyboard."""
    keyboard = [
        [InlineKeyboardButton("📊 إحصائيات عامة", callback_data="admin_stats"),
         InlineKeyboardButton("👥 المستخدمين", callback_data="admin_users")],
        [InlineKeyboardButton("📢 إرسال إعلان", callback_data="admin_broadcast"),
         InlineKeyboardButton("🚫 إدارة الحظر", callback_data="admin_ban")],
        [InlineKeyboardButton("⭐ إضافة مستخدم مميز", callback_data="add_premium"),
         InlineKeyboardButton("❌ إزالة مستخدم مميز", callback_data="remove_premium")],
        [InlineKeyboardButton("👑 عرض المستخدمين المميزين", callback_data="list_premium")],
        [InlineKeyboardButton("🏢 إدارة المجموعات", callback_data="admin_groups")],
        [InlineKeyboardButton("⚙️ إدارة البرومبت", callback_data="manage_prompt")],
        [InlineKeyboardButton("📤 تحويل إعلان", callback_data="forward_ad")],
        [InlineKeyboardButton("🚪 تسجيل الخروج", callback_data="admin_logout")]
    ]
    return InlineKeyboardMarkup(keyboard)

def get_ban_keyboard():
    """Get ban management keyboard."""
    keyboard = [
        [InlineKeyboardButton("🚫 حظر مستخدم", callback_data="ban_user"),
         InlineKeyboardButton("✅ إلغاء حظر مستخدم", callback_data="unban_user")],
        [InlineKeyboardButton("📋 قائمة المحظورين", callback_data="banned_list")],
        [InlineKeyboardButton("🔙 رجوع", callback_data="admin_back")]
    ]
    return InlineKeyboardMarkup(keyboard)

def get_groups_keyboard():
    """Get groups management keyboard."""
    keyboard = [
        [InlineKeyboardButton("📊 إحصائيات المجموعات", callback_data="groups_stats"),
         InlineKeyboardButton("📢 إرسال رسالة", callback_data="groups_broadcast")],
        [InlineKeyboardButton("🔍 بحث عن مجموعة", callback_data="groups_search"),
         InlineKeyboardButton("⚠️ المجموعات غير النشطة", callback_data="groups_inactive")],
        [InlineKeyboardButton("🔄 تحديث البيانات", callback_data="groups_refresh"),
         InlineKeyboardButton("❌ حذف المجموعات غير النشطة", callback_data="groups_cleanup")],
        [InlineKeyboardButton("🔙 رجوع للقائمة الرئيسية", callback_data="admin_back")]
    ]
    return InlineKeyboardMarkup(keyboard)

async def admin_panel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Show admin panel."""
    if not update.message.from_user.username or not is_admin(update.message.from_user.username):
        await update.message.reply_text("عذراً، هذا الأمر متاح للمشرفين فقط.")
        return

    # Set admin state
    context.user_data["admin_state"] = True

    await update.message.reply_text(
        "🔰 لوحة تحكم المشرف\nاختر أحد الخيارات التالية:",
        reply_markup=get_admin_keyboard()
    )

async def handle_admin_callback(update: Update, context: ContextTypes.DEFAULT_TYPE, db) -> None:
    """Handle admin panel callbacks."""
    query = update.callback_query
    await query.answer()

    if not query.from_user.username or not is_admin(query.from_user.username):
        await query.message.reply_text("عذراً، هذا الأمر متاح للمشرفين فقط.")
        return

    if query.data == "admin_stats":
        await show_statistics(query, db)
    elif query.data == "admin_users":
        await show_users(query, db)
    elif query.data == "admin_broadcast":
        await start_broadcast(update, context)
    elif query.data == "admin_ban":
        await show_ban_menu(query)
    elif query.data == "admin_groups":
        await query.message.edit_text(
            "🏢 إدارة المجموعات\nاختر أحد الخيارات التالية:",
            reply_markup=get_groups_keyboard()
        )
    elif query.data == "groups_stats":
        await show_groups(query, db)
    elif query.data == "groups_broadcast":
        await start_groups_broadcast(query, context)
    elif query.data == "ban_user":
        await start_ban(query, context)
    elif query.data == "unban_user":
        await start_unban(query, context)
    elif query.data == "banned_list":
        await show_banned_users(query, db)
    elif query.data == "admin_back":
        await query.message.edit_text(
            "🔰 لوحة تحكم المشرف\nاختر أحد الخيارات التالية:",
            reply_markup=get_admin_keyboard()
        )
    # --- Prompt Management ---
    elif query.data == "manage_prompt":
        await show_prompt_menu(query, db)
    elif query.data == "view_prompt":
        await view_current_prompt(query, db)
    elif query.data == "edit_prompt":
        await start_edit_prompt(query, context)
    elif query.data == "reset_prompt":
        await reset_to_default_prompt(query, db)
    # -------------------------
    elif query.data == "add_premium":
        context.user_data['admin_state'] = 'waiting_add_premium'
        await query.message.edit_text(
            "⭐ إضافة مستخدم مميز\n\n"
            "قم بإرسال معرف المستخدم (ID) الذي تريد إضافته كمستخدم مميز.\n\n"
            "للإلغاء، أرسل /cancel",
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("❌ إلغاء", callback_data="admin_back")
            ]])
        )

    elif query.data == "remove_premium":
        context.user_data['admin_state'] = 'waiting_remove_premium'
        await query.message.edit_text(
            "❌ إزالة مستخدم مميز\n\n"
            "قم بإرسال معرف المستخدم (ID) الذي تريد إزالته من المستخدمين المميزين.\n\n"
            "للإلغاء، أرسل /cancel",
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("❌ إلغاء", callback_data="admin_back")
            ]])
        )

    elif query.data == "confirm_add_premium":
        user_id = context.user_data.get('premium_user_id')
        confirm_msg = context.user_data.get('confirm_msg')

        if user_id and confirm_msg:
            try:
                db.add_premium_user(user_id)
                await confirm_msg.edit_text(f"✅ تم إضافة المستخدم {user_id} كمستخدم مميز بنجاح!")
            except Exception as e:
                await confirm_msg.edit_text(f"❌ حدث خطأ: {str(e)}")

            await asyncio.sleep(2)
            context.user_data.clear()
            await query.message.reply_text(
                "🔰 لوحة تحكم المشرف\nاختر أحد الخيارات التالية:",
                reply_markup=get_admin_keyboard()
            )

    elif query.data == "confirm_remove_premium":
        user_id = context.user_data.get('premium_user_id')
        confirm_msg = context.user_data.get('confirm_msg')

        if user_id and confirm_msg:
            try:
                db.remove_premium_user(user_id)
                await confirm_msg.edit_text(f"✅ تم إزالة المستخدم {user_id} من المستخدمين المميزين بنجاح!")
            except Exception as e:
                await confirm_msg.edit_text(f"❌ حدث خطأ: {str(e)}")

            await asyncio.sleep(2)
            context.user_data.clear()
            await query.message.reply_text(
                "🔰 لوحة تحكم المشرف\nاختر أحد الخيارات التالية:",
                reply_markup=get_admin_keyboard()
            )

    elif query.data == "cancel_premium_action":
        context.user_data.clear()
        await query.message.edit_text(
            "❌ تم إلغاء العملية",
            reply_markup=None
        )
        await asyncio.sleep(2)
        await query.message.reply_text(
            "🔰 لوحة تحكم المشرف\nاختر أحد الخيارات التالية:",
            reply_markup=get_admin_keyboard()
        )

    elif query.data == "admin_logout":
        # Clear admin session
        if "admin_state" in context.user_data:
            del context.user_data["admin_state"]
        await query.message.edit_text("تم تسجيل الخروج بنجاح من لوحة التحكم. ✅")
    elif query.data == "list_premium":
        await show_premium_users(query, db)
    elif query.data == "forward_ad":
        await start_broadcast(update, context)
    elif query.data == "admin_broadcast":
        # New broadcast system
        from .broadcast import start_broadcast
        await start_broadcast(query, context)

    elif query.data == "forward_ad":
         # Use same broadcast system for forwarding
        from .broadcast import start_broadcast
        await start_broadcast(query, context)

    elif query.data == "confirm_ban":
        user_id = context.user_data.get('ban_user_id')
        if user_id:
            try:
                # تنفيذ الحظر
                db.ban_user(user_id)
                user_info = db.get_user_info(user_id) or {}
                username = user_info.get("username", "")
                first_name = user_info.get("first_name", "")

                # محاولة إرسال إشعار للمستخدم
                try:
                    await context.bot.send_message(
                        chat_id=user_id,
                        text="⚠️ تم حظرك من استخدام البوت من قبل المشرف."
                    )
                except Exception:
                    pass  # تجاهل الفشل في إرسال الإشعار

                await query.message.edit_text(
                    f"✅ تم حظر المستخدم بنجاح!\n\n"
                    f"معلومات المستخدم:\n"
                    f"- الاسم: {first_name}\n"
                    f"- المعرف: @{username}\n"
                    f"- رقم المعرف: {user_id}"
                )

                # مسح حالة الأدمن وإظهار لوحة التحكم
                context.user_data.clear()
                await asyncio.sleep(2)
                await query.message.reply_text(
                    "🔰 لوحة تحكم المشرف\nاختر أحد الخيارات التالية:",
                    reply_markup=get_admin_keyboard()
                )
            except Exception as e:
                await query.message.edit_text(f"❌ حدث خطأ: {str(e)}")
                context.user_data.clear()

    elif query.data == "confirm_unban":
        user_id = context.user_data.get('unban_user_id')
        if user_id:
            try:
                # تنفيذ إلغاء الحظر
                db.unban_user(user_id)
                user_info = db.get_user_info(user_id) or {}
                username = user_info.get("username", "")
                first_name = user_info.get("first_name", "")

                # محاولة إرسال إشعار للمستخدم
                try:
                    await context.bot.send_message(
                        chat_id=user_id,
                        text="✅ تم إلغاء حظرك من البوت. يمكنك الآن استخدام البوت مرة أخرى."
                    )
                except Exception:
                    pass  # تجاهل الفشل في إرسال الإشعار

                await query.message.edit_text(
                    f"✅ تم إلغاء حظر المستخدم بنجاح!\n\n"
                    f"معلومات المستخدم:\n"
                    f"- الاسم: {first_name}\n"
                    f"- المعرف: @{username}\n"
                    f"- رقم المعرف: {user_id}"
                )

                # مسح حالة الأدمن وإظهار لوحة التحكم
                context.user_data.clear()
                await asyncio.sleep(2)
                await query.message.reply_text(
                    "🔰 لوحة تحكم المشرف\nاختر أحد الخيارات التالية:",
                    reply_markup=get_admin_keyboard()
                )
            except Exception as e:
                await query.message.edit_text(f"❌ حدث خطأ: {str(e)}")
                context.user_data.clear()

    elif query.data in ["cancel_ban", "cancel_unban"]:
        context.user_data.clear()
        await query.message.edit_text(
            "❌ تم إلغاء العملية",
            reply_markup=None
        )
        await asyncio.sleep(2)
        await query.message.reply_text(
            "🔰 لوحة تحكم المشرف\nاختر أحد الخيارات التالية:",
            reply_markup=get_admin_keyboard()
        )

async def handle_admin_message(update: Update, context: ContextTypes.DEFAULT_TYPE, db) -> None:
    """Handle admin messages."""
    if not update.message.from_user.username or not is_admin(update.message.from_user.username):
        await update.message.reply_text("عذراً، هذا الأمر متاح للمشرفين فقط.")
        return

    message_text = update.message.text
    admin_state = context.user_data.get('admin_state', '')

    if message_text == "/cancel":
        context.user_data.clear()
        await update.message.reply_text(
            "تم إلغاء العملية الحالية.",
            reply_markup=get_admin_keyboard()
        )
        return

    if admin_state == 'waiting_for_ban':
        try:
            user_id = int(message_text)
            # التحقق من وجود المستخدم في قاعدة البيانات
            if not db.is_user_exist(user_id):
                await update.message.reply_text("❌ المستخدم غير موجود في قاعدة البيانات.")
                return

            # التحقق مما إذا كان المستخدم محظوراً بالفعل
            if db.is_user_banned(user_id):
                await update.message.reply_text("❌ هذا المستخدم محظور بالفعل!")
                return

            # حفظ معرف المستخدم وإرسال رسالة التأكيد
            context.user_data['ban_user_id'] = user_id
            user_info = db.get_user_info(user_id) or {}
            username = user_info.get("username", "")
            first_name = user_info.get("first_name", "")

            await update.message.reply_text(
                f"⚠️ تأكيد حظر المستخدم\n\n"
                f"معلومات المستخدم:\n"
                f"- الاسم: {first_name}\n"
                f"- المعرف: @{username}\n"
                f"- رقم المعرف: {user_id}\n\n"
                f"هل أنت متأكد من حظر هذا المستخدم؟",
                reply_markup=InlineKeyboardMarkup([
                    [
                        InlineKeyboardButton("✅ نعم، احظر", callback_data="confirm_ban"),
                        InlineKeyboardButton("❌ إلغاء", callback_data="cancel_ban")
                    ]
                ])
            )

        except ValueError:
            await update.message.reply_text("❌ الرجاء إدخال رقم معرف صحيح.")
        return

    elif admin_state == 'waiting_for_unban':
        try:
            user_id = int(message_text)
            # التحقق من أن المستخدم محظور
            if not db.is_user_banned(user_id):
                await update.message.reply_text("❌ هذا المستخدم غير محظور!")
                return

            # حفظ معرف المستخدم وإرسال رسالة التأكيد
            context.user_data['unban_user_id'] = user_id
            user_info = db.get_user_info(user_id) or {}
            username = user_info.get("username", "")
            first_name = user_info.get("first_name", "")

            await update.message.reply_text(
                f"⚠️ تأكيد إلغاء حظر المستخدم\n\n"
                f"معلومات المستخدم:\n"
                f"- الاسم: {first_name}\n"
                f"- المعرف: @{username}\n"
                f"- رقم المعرف: {user_id}\n\n"
                f"هل أنت متأكد من إلغاء حظر هذا المستخدم؟",
                reply_markup=InlineKeyboardMarkup([
                    [
                        InlineKeyboardButton("✅ نعم، ألغِ الحظر", callback_data="confirm_unban"),
                        InlineKeyboardButton("❌ إلغاء", callback_data="cancel_unban")
                    ]
                ])
            )

        except ValueError:
            await update.message.reply_text("❌ الرجاء إدخال رقم معرف صحيح.")
        return

    # Handle prompt editing
    if admin_state == 'waiting_for_new_prompt':
        await handle_new_prompt(update, context, db)
        return

    # Handle other admin states...
    if admin_state == 'waiting_for_broadcast':
        # Get all users from database
        all_users = db.data["users"].keys()
        total_users = len(all_users)

        # Send confirmation message with user count
        confirm_msg = await update.message.reply_text(
            f"⚠️ تأكيد إرسال الإعلان\n\n"
            f"سيتم إرسال الإعلان إلى {total_users} مستخدم\n"
            f"هل تريد المتابعة؟",
            reply_markup=InlineKeyboardMarkup([
                [
                    InlineKeyboardButton("✅ نعم، أرسل", callback_data="confirm_broadcast"),
                    InlineKeyboardButton("❌ إلغاء", callback_data="cancel_broadcast")
                ]
            ])
        )

        # Store the message to be broadcasted
        context.user_data['broadcast_message'] = update.message
        context.user_data['confirm_msg'] = confirm_msg
        return

    elif admin_state == 'waiting_groups_broadcast':
        # معالجة إرسال الرسالة للمجموعات
        await handle_groups_broadcast(update.message, context, db)
        return

    elif admin_state == 'waiting_add_premium':
        try:
            user_id = message_text.strip()
            # التحقق من وجود المستخدم في قاعدة البيانات
            if not db.is_user_exist(int(user_id)):
                await update.message.reply_text("❌ المستخدم غير موجود في قاعدة البيانات.")
                return

            # التحقق مما إذا كان المستخدم مميزاً بالفعل
            if db.is_user_premium(int(user_id)):
                await update.message.reply_text("❌ هذا المستخدم مميز بالفعل!")
                return

            # حفظ معرف المستخدم وإرسال رسالة التأكيد
            context.user_data['premium_user_id'] = user_id
            confirm_msg = await update.message.reply_text(
                f"⚠️ تأكيد إضافة مستخدم مميز\n\n"
                f"هل أنت متأكد من إضافة المستخدم {user_id} كمستخدم مميز؟",
                reply_markup=InlineKeyboardMarkup([
                    [
                        InlineKeyboardButton("✅ نعم، أضف", callback_data="confirm_add_premium"),
                        InlineKeyboardButton("❌ إلغاء", callback_data="cancel_premium_action")
                    ]
                ])
            )
            context.user_data['confirm_msg'] = confirm_msg

        except ValueError:
            await update.message.reply_text("❌ الرجاء إدخال معرف صحيح.")
        return

    elif admin_state == 'waiting_remove_premium':
        try:
            user_id = message_text.strip()
            # التحقق من وجود المستخدم في قائمة المميزين
            if not db.is_user_premium(int(user_id)):
                await update.message.reply_text("❌ هذا المستخدم ليس مميزاً!")
                return

            # حفظ معرف المستخدم وإرسال رسالة التأكيد
            context.user_data['premium_user_id'] = user_id
            confirm_msg = await update.message.reply_text(
                f"⚠️ تأكيد إزالة مستخدم مميز\n\n"
                f"هل أنت متأكد من إزالة المستخدم {user_id} من المستخدمين المميزين؟",
                reply_markup=InlineKeyboardMarkup([
                    [
                        InlineKeyboardButton("✅ نعم، أزل", callback_data="confirm_remove_premium"),
                        InlineKeyboardButton("❌ إلغاء", callback_data="cancel_premium_action")
                    ]
                ])
            )
            context.user_data['confirm_msg'] = confirm_msg

        except ValueError:
            await update.message.reply_text("❌ الرجاء إدخال معرف صحيح.")
        return

    # Check for new broadcast state
    from .broadcast import handle_broadcast_input, WAITING_MESSAGE
    if context.user_data.get('broadcast_state') == WAITING_MESSAGE:
        await handle_broadcast_input(update, context, db)
        return

    # If no specific state or unknown state, show admin panel
    await update.message.reply_text(
        "🔰 لوحة تحكم المشرف\nاختر أحد الخيارات التالية:",
        reply_markup=get_admin_keyboard()
    )

async def handle_ban_unban_message(update: Update, context: ContextTypes.DEFAULT_TYPE, db) -> None:
    """Handle ban/unban user messages from admin."""
    if not update.message.from_user.username or not is_admin(update.message.from_user.username):
        await update.message.reply_text("عذراً، هذا الأمر متاح للمشرفين فقط.")
        return

    message_text = update.message.text
    admin_state = context.user_data.get('admin_state', '')

    if message_text == "/cancel":
        context.user_data.clear()
        await update.message.reply_text(
            "تم إلغاء العملية الحالية.",
            reply_markup=get_admin_keyboard()
        )
        return

    if admin_state == 'waiting_for_ban':
        try:
            user_id = int(message_text)
            # التحقق من وجود المستخدم في قاعدة البيانات
            if not db.is_user_exist(user_id):
                await update.message.reply_text("❌ المستخدم غير موجود في قاعدة البيانات.")
                return

            # التحقق مما إذا كان المستخدم محظوراً بالفعل
            if db.is_user_banned(user_id):
                await update.message.reply_text("❌ هذا المستخدم محظور بالفعل!")
                return

            # حفظ معرف المستخدم وإرسال رسالة التأكيد
            context.user_data['ban_user_id'] = user_id
            user_info = db.get_user_info(user_id) or {}
            username = user_info.get("username", "")
            first_name = user_info.get("first_name", "")

            await update.message.reply_text(
                f"⚠️ تأكيد حظر المستخدم\n\n"
                f"معلومات المستخدم:\n"
                f"- الاسم: {first_name}\n"
                f"- المعرف: @{username}\n"
                f"- رقم المعرف: {user_id}\n\n"
                f"هل أنت متأكد من حظر هذا المستخدم؟",
                reply_markup=InlineKeyboardMarkup([
                    [
                        InlineKeyboardButton("✅ نعم، احظر", callback_data="confirm_ban"),
                        InlineKeyboardButton("❌ إلغاء", callback_data="cancel_ban")
                    ]
                ])
            )

        except ValueError:
            await update.message.reply_text("❌ الرجاء إدخال رقم معرف صحيح.")
        return

    elif admin_state == 'waiting_for_unban':
        try:
            user_id = int(message_text)
            # التحقق من أن المستخدم محظور
            if not db.is_user_banned(user_id):
                await update.message.reply_text("❌ هذا المستخدم غير محظور!")
                return

            # حفظ معرف المستخدم وإرسال رسالة التأكيد
            context.user_data['unban_user_id'] = user_id
            user_info = db.get_user_info(user_id) or {}
            username = user_info.get("username", "")
            first_name = user_info.get("first_name", "")

            await update.message.reply_text(
                f"⚠️ تأكيد إلغاء حظر المستخدم\n\n"
                f"معلومات المستخدم:\n"
                f"- الاسم: {first_name}\n"
                f"- المعرف: @{username}\n"
                f"- رقم المعرف: {user_id}\n\n"
                f"هل أنت متأكد من إلغاء حظر هذا المستخدم؟",
                reply_markup=InlineKeyboardMarkup([
                    [
                        InlineKeyboardButton("✅ نعم، ألغِ الحظر", callback_data="confirm_unban"),
                        InlineKeyboardButton("❌ إلغاء", callback_data="cancel_unban")
                    ]
                ])
            )

        except ValueError:
            await update.message.reply_text("❌ الرجاء إدخال رقم معرف صحيح.")
        return

async def show_statistics(query, db):
    """Show bot statistics."""
    stats = db.get_total_stats()
    daily_stats = db.get_daily_activity_stats()
    stats_text = f"""📊 إحصائيات البوت:

👥 عدد المستخدمين: {stats['total_users']}
📝 مجموع الرسائل: {stats['total_messages']}
🖼 مجموع الصور: {stats['total_images']}

📅 إحصائيات اليوم:
📝 الرسائل: {daily_stats['messages']}
🖼 الصور: {daily_stats['images']}"""

    await query.message.edit_text(stats_text, reply_markup=get_admin_keyboard())

async def show_users(query, db):
    """Show users information."""
    users = list(db.get_all_users_data().values())
    active_users = [u for u in users if datetime.fromisoformat(u['last_active']).date() == datetime.now().date()]
    users_text = f"""👥 معلومات المستخدمين:

📊 إجمالي المستخدمين: {len(users)}
📱 المستخدمين النشطين اليوم: {len(active_users)}

آخر 5 مستخدمين نشطين:"""

    sorted_users = sorted(users, key=lambda x: x['last_active'], reverse=True)[:5]
    for user in sorted_users:
        users_text += f"\n- {user['first_name']} (@{user['username']}) | الرسائل: {user['message_count']}"

    await query.message.edit_text(users_text, reply_markup=get_admin_keyboard())



async def show_groups(query, db):
    """Show groups information."""
    try:
        groups = db.get_all_groups()
        total_groups = len(groups)
        active_groups = sum(1 for g in groups if g.get('message_count', 0) > 0)

        message = (
            f"📊 *إحصائيات المجموعات*\n\n"
            f"📱 العدد الكلي: `{total_groups}`\n"
            f"✅ المجموعات النشطة: `{active_groups}`\n"
            f"⚠️ المجموعات غير النشطة: `{total_groups - active_groups}`\n\n"
            f"📋 *آخر 5 مجموعات:*\n"
        )

        # عرض آخر 5 مجموعات فقط لتجنب الرسائل الطويلة
        for i, group in enumerate(groups[:5], 1):
            group_name = group.get('title', 'مجموعة غير معروفة')
            message_count = group.get('message_count', 0)
            
            # Safe date parsing
            last_active_str = group.get('last_active')
            if isinstance(last_active_str, str):
                try:
                    last_active = datetime.fromisoformat(last_active_str)
                except ValueError:
                    last_active = datetime.now()
            else:
                last_active = datetime.now()
                
            days_inactive = (datetime.now() - last_active).days

            status = "✅ نشطة" if message_count > 0 else "⚠️ غير نشطة"
            message += (
                f"\n{i}. *{group_name}*\n"
                f"   💬 الرسائل: `{message_count}`\n"
                f"   ⏰ آخر نشاط: `{days_inactive} يوم`\n"
                f"   📊 الحالة: {status}\n"
            )

        await query.message.edit_text(
            message,
            reply_markup=get_groups_keyboard(),
            parse_mode='Markdown'
        )
    except Exception as e:
        error_message = (
            "⚠️ حدث خطأ أثناء عرض المجموعات\n"
            "الرجاء المحاولة مرة أخرى"
        )
        await query.message.edit_text(
            error_message,
            reply_markup=get_groups_keyboard()
        )
        logging.error(f"Error in show_groups: {str(e)}")

async def start_groups_broadcast(query: Update.callback_query, context: ContextTypes.DEFAULT_TYPE):
    """بدء عملية إرسال رسالة للمجموعات."""
    context.user_data['admin_state'] = 'waiting_groups_broadcast'

    message = (
        "📢 *إرسال رسالة للمجموعات*\n\n"
        "• أرسل الرسالة التي تريد إرسالها للمجموعات\n"
        "• يمكنك استخدام تنسيق Markdown\n\n"
        "*التنسيقات المتاحة:*\n"
        "• `**نص غامق**`\n"
        "• `*نص مائل*`\n"
        "• `[رابط](URL)`\n"
        "• استخدم الإيموجي 😊\n\n"
        "*ملاحظة:* سيتم إرسال رسالة تأكيد قبل الإرسال النهائي"
    )

    keyboard = [
        [InlineKeyboardButton("❌ إلغاء", callback_data="admin_groups")]
    ]

    await query.message.edit_text(
        message,
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode='Markdown'
    )

async def handle_groups_broadcast(message: str, context: ContextTypes.DEFAULT_TYPE, db) -> None:
    """معالجة إرسال الرسالة للمجموعات."""
    try:
        groups = db.get_all_groups()
        if not groups:
            await message.reply_text(
                "⚠️ لا توجد مجموعات متاحة للإرسال",
                reply_markup=InlineKeyboardMarkup([[
                    InlineKeyboardButton("🔙 رجوع", callback_data="admin_groups")
                ]])
            )
            return

        # رسالة تأكيد قبل الإرسال
        confirm_message = (
            f"📝 *مراجعة الرسالة*\n\n"
            f"الرسالة التي سيتم إرسالها:\n"
            f"```\n{message.text}\n```\n\n"
            f"📊 سيتم الإرسال إلى {len(groups)} مجموعة\n\n"
            f"هل تريد المتابعة؟"
        )

        keyboard = [
            [InlineKeyboardButton("✅ تأكيد الإرسال", callback_data="confirm_broadcast"),
             InlineKeyboardButton("❌ إلغاء", callback_data="admin_groups")]
        ]

        confirm_msg = await message.reply_text(
            confirm_message,
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode='Markdown'
        )

        # حفظ المعلومات للتأكيد
        context.user_data['broadcast_message'] = message.text
        context.user_data['confirm_msg_id'] = confirm_msg.message_id

    except Exception as e:
        await message.reply_text(
            "⚠️ حدث خطأ أثناء تجهيز الرسالة. الرجاء المحاولة مرة أخرى.",
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("🔙 رجوع", callback_data="admin_groups")
            ]])
        )
        logging.error(f"Error in handle_groups_broadcast: {str(e)}")

async def execute_groups_broadcast(query: Update.callback_query, context: ContextTypes.DEFAULT_TYPE, db):
    """تنفيذ إرسال الرسالة للمجموعات."""
    message = context.user_data.get('broadcast_message')
    if not message:
        await query.message.edit_text(
            "⚠️ حدث خطأ: لم يتم العثور على الرسالة",
            reply_markup=get_groups_keyboard()
        )
        return

    status_message = await query.message.edit_text(
        "⏳ جاري إرسال الرسالة للمجموعات...\n"
        "0% مكتمل"
    )

    groups = db.get_all_groups()
    success_count = 0
    fail_count = 0
    total = len(groups)

    for i, group in enumerate(groups, 1):
        try:
            await context.bot.send_message(
                chat_id=int(group['chat_id']),
                text=message,
                parse_mode='Markdown'
            )
            success_count += 1

            # تحديث حالة التقدم كل 5 مجموعات
            if i % 5 == 0:
                progress = (i / total) * 100
                await status_message.edit_text(
                    f"⏳ جاري إرسال الرسالة للمجموعات...\n"
                    f"{progress:.1f}% مكتمل\n"
                    f"✅ نجح: {success_count}\n"
                    f"❌ فشل: {fail_count}"
                )
        except Exception as e:
            fail_count += 1
            logging.error(f"Failed to send to group {group['chat_id']}: {str(e)}")

    result_message = (
        f"✅ *اكتمل إرسال الرسالة!*\n\n"
        f"📊 *النتائج:*\n"
        f"• نجح: `{success_count}` مجموعة\n"
        f"• فشل: `{fail_count}` مجموعة\n"
        f"• المجموع: `{total}` مجموعة\n\n"
        f"نسبة النجاح: `{(success_count/total)*100:.1f}%`"
    )

    await status_message.edit_text(
        result_message,
        reply_markup=get_groups_keyboard(),
        parse_mode='Markdown'
    )
