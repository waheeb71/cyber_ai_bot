from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from ..config import ADMIN_USERS, BOT_SIGNATURE
from datetime import datetime
import logging
import asyncio

logger = logging.getLogger(__name__)

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
        await start_broadcast(query, context)
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
        await start_forward_ad(query, context)
    elif query.data == "confirm_broadcast":
        broadcast_msg = context.user_data.get('broadcast_message')
        confirm_msg = context.user_data.get('confirm_msg')

        if broadcast_msg and confirm_msg:
            await confirm_msg.edit_text("⏳ جاري إرسال الإعلان...")

            success_count = 0
            fail_count = 0

            # Get all users from database
            all_users = db.data["users"].keys()
            total_users = len(all_users)

            # Send to each user
            for user_id in all_users:
                try:
                    # Skip banned users
                    if user_id in db.data["banned_users"]:
                        continue

                    if broadcast_msg.photo:
                        await context.bot.send_photo(
                            chat_id=int(user_id),
                            photo=broadcast_msg.photo[-1].file_id,
                            caption=broadcast_msg.caption
                        )
                    elif broadcast_msg.video:
                        await context.bot.send_video(
                            chat_id=int(user_id),
                            video=broadcast_msg.video.file_id,
                            caption=broadcast_msg.caption
                        )
                    elif broadcast_msg.text:
                        await context.bot.send_message(
                            chat_id=int(user_id),
                            text=broadcast_msg.text
                        )
                    success_count += 1
                except Exception as e:
                    logger.error(f"Failed to send broadcast to user {user_id}: {str(e)}")
                    fail_count += 1

            # Send final status
            final_status = (
                f"✅ تم إرسال الإعلان بنجاح!\n\n"
                f"📊 إحصائيات:\n"
                f"- عدد المستخدمين الكلي: {total_users}\n"
                f"- تم الإرسال بنجاح: {success_count}\n"
                f"- فشل الإرسال: {fail_count}"
            )
            await confirm_msg.edit_text(final_status)

            # Clear user data
            context.user_data.clear()

            # Show admin panel after 3 seconds
            await asyncio.sleep(3)
            await query.message.reply_text(
                "🔰 لوحة تحكم المشرف\nاختر أحد الخيارات التالية:",
                reply_markup=get_admin_keyboard()
            )

    elif query.data == "cancel_broadcast":
        context.user_data.clear()
        await query.message.edit_text(
            "❌ تم إلغاء إرسال الإعلان",
            reply_markup=None
        )
        await asyncio.sleep(2)
        await query.message.reply_text(
            "🔰 لوحة تحكم المشرف\nاختر أحد الخيارات التالية:",
            reply_markup=get_admin_keyboard()
        )

    elif query.data == "confirm_forward_ad":
        forward_msg = context.user_data.get('forward_message')
        confirm_msg = context.user_data.get('confirm_msg')

        if forward_msg and confirm_msg:
            await confirm_msg.edit_text("⏳ جاري إرسال الإعلان...")

            success_count = 0
            fail_count = 0

            # Get all users from database
            all_users = db.data["users"].keys()
            total_users = len(all_users)

            # Handle forwarded advertisement
            buttons = None
            caption = forward_msg.caption if forward_msg.caption else ""
            text_content = forward_msg.text if forward_msg.text else ""

            # Check if there are button configurations in the text or caption
            content = text_content if text_content else caption
            if content and "|" in content:
                lines = content.split("\n")
                button_lines = [line for line in lines if "|" in line]
                content_lines = [line for line in lines if "|" not in line]

                # Create buttons
                keyboard = []
                for line in button_lines:
                    try:
                        title, url = [x.strip() for x in line.split("|")]
                        keyboard.append([InlineKeyboardButton(title, url=url)])
                    except Exception as e:
                        logger.error(f"Error parsing buttons: {str(e)}")
                        await confirm_msg.edit_text(f"❌ خطأ في تنسيق الأزرار: {str(e)}")
                        return

                if keyboard:
                    buttons = InlineKeyboardMarkup(keyboard)
                content = "\n".join(content_lines)
                if forward_msg.text:
                    text_content = content
                else:
                    caption = content

            # Send to each user
            for user_id in all_users:
                try:
                    # Skip banned users
                    if user_id in db.data["banned_users"]:
                        continue

                    if forward_msg.photo:
                        await context.bot.send_photo(
                            chat_id=int(user_id),
                            photo=forward_msg.photo[-1].file_id,
                            caption=caption,
                            reply_markup=buttons
                        )
                    elif forward_msg.video:
                        await context.bot.send_video(
                            chat_id=int(user_id),
                            video=forward_msg.video.file_id,
                            caption=caption,
                            reply_markup=buttons
                        )
                    elif forward_msg.text:
                        await context.bot.send_message(
                            chat_id=int(user_id),
                            text=text_content,
                            reply_markup=buttons
                        )
                    success_count += 1
                except Exception as e:
                    logger.error(f"Failed to send forward to user {user_id}: {str(e)}")
                    fail_count += 1

            # Send final status
            final_status = (
                f"✅ تم إرسال الإعلان بنجاح!\n\n"
                f"📊 إحصائيات:\n"
                f"- عدد المستخدمين الكلي: {total_users}\n"
                f"- تم الإرسال بنجاح: {success_count}\n"
                f"- فشل الإرسال: {fail_count}"
            )
            await confirm_msg.edit_text(final_status)

            # Clear user data
            context.user_data.clear()

            # Show admin panel after 3 seconds
            await asyncio.sleep(3)
            await query.message.reply_text(
                "🔰 لوحة تحكم المشرف\nاختر أحد الخيارات التالية:",
                reply_markup=get_admin_keyboard()
            )

    elif query.data == "cancel_forward_ad":
        context.user_data.clear()
        await query.message.edit_text(
            "❌ تم إلغاء إرسال الإعلان",
            reply_markup=None
        )
        await asyncio.sleep(2)
        await query.message.reply_text(
            "🔰 لوحة تحكم المشرف\nاختر أحد الخيارات التالية:",
            reply_markup=get_admin_keyboard()
        )

    elif query.data == "confirm_ban":
        user_id = context.user_data.get('ban_user_id')
        if user_id:
            try:
                # تنفيذ الحظر
                db.ban_user(user_id)
                username = db.data["users"][str(user_id)].get("username", "")
                first_name = db.data["users"][str(user_id)].get("first_name", "")

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
                username = db.data["users"][str(user_id)].get("username", "")
                first_name = db.data["users"][str(user_id)].get("first_name", "")

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
            if str(user_id) not in db.data["users"]:
                await update.message.reply_text("❌ المستخدم غير موجود في قاعدة البيانات.")
                return

            # التحقق مما إذا كان المستخدم محظوراً بالفعل
            if str(user_id) in db.data["banned_users"]:
                await update.message.reply_text("❌ هذا المستخدم محظور بالفعل!")
                return

            # حفظ معرف المستخدم وإرسال رسالة التأكيد
            context.user_data['ban_user_id'] = user_id
            username = db.data["users"][str(user_id)].get("username", "")
            first_name = db.data["users"][str(user_id)].get("first_name", "")

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
            if str(user_id) not in db.data["banned_users"]:
                await update.message.reply_text("❌ هذا المستخدم غير محظور!")
                return

            # حفظ معرف المستخدم وإرسال رسالة التأكيد
            context.user_data['unban_user_id'] = user_id
            username = db.data["users"][str(user_id)].get("username", "")
            first_name = db.data["users"][str(user_id)].get("first_name", "")

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
            if str(user_id) not in db.data["users"]:
                await update.message.reply_text("❌ المستخدم غير موجود في قاعدة البيانات.")
                return

            # التحقق مما إذا كان المستخدم مميزاً بالفعل
            if user_id in db.data.get("premium_users", []):
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
            if user_id not in db.data.get("premium_users", []):
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
            if str(user_id) not in db.data["users"]:
                await update.message.reply_text("❌ المستخدم غير موجود في قاعدة البيانات.")
                return

            # التحقق مما إذا كان المستخدم محظوراً بالفعل
            if str(user_id) in db.data["banned_users"]:
                await update.message.reply_text("❌ هذا المستخدم محظور بالفعل!")
                return

            # حفظ معرف المستخدم وإرسال رسالة التأكيد
            context.user_data['ban_user_id'] = user_id
            username = db.data["users"][str(user_id)].get("username", "")
            first_name = db.data["users"][str(user_id)].get("first_name", "")

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
            if str(user_id) not in db.data["banned_users"]:
                await update.message.reply_text("❌ هذا المستخدم غير محظور!")
                return

            # حفظ معرف المستخدم وإرسال رسالة التأكيد
            context.user_data['unban_user_id'] = user_id
            username = db.data["users"][str(user_id)].get("username", "")
            first_name = db.data["users"][str(user_id)].get("first_name", "")

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
    users = db.get_all_users()
    active_users = [u for u in users if datetime.fromisoformat(u['last_active']).date() == datetime.now().date()]
    users_text = f"""👥 معلومات المستخدمين:

📊 إجمالي المستخدمين: {len(users)}
📱 المستخدمين النشطين اليوم: {len(active_users)}

آخر 5 مستخدمين نشطين:"""

    sorted_users = sorted(users, key=lambda x: x['last_active'], reverse=True)[:5]
    for user in sorted_users:
        users_text += f"\n- {user['first_name']} (@{user['username']}) | الرسائل: {user['message_count']}"

    await query.message.edit_text(users_text, reply_markup=get_admin_keyboard())

async def start_broadcast(query: Update.callback_query, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Start broadcast message process."""
    context.user_data['admin_state'] = 'waiting_for_broadcast'
    await query.message.edit_text(
        "📢 إرسال إعلان للمستخدمين\n\n"
        "قم بإرسال الإعلان الذي تريد إرساله للمستخدمين.\n"
        "يمكنك إرسال:\n"
        "- نص\n"
        "- صورة مع نص\n"
        "- فيديو مع نص\n\n"
        "لإضافة أزرار، أضف في نهاية النص:\n"
        "عنوان الزر | الرابط\n\n"
        "مثال:\n"
        "مرحباً بكم في قناتنا\n"
        "اشترك الآن | https://t.me/channel\n\n"
        "للإلغاء، أرسل /cancel",
        reply_markup=InlineKeyboardMarkup([[
            InlineKeyboardButton("❌ إلغاء", callback_data="admin_back")
        ]])
    )

async def show_ban_menu(query):
    """Show ban management menu."""
    await query.message.edit_text(
        "🚫 إدارة الحظر\nاختر أحد الخيارات:",
        reply_markup=get_ban_keyboard()
    )

async def start_ban(query: Update.callback_query, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Start ban user process."""
    context.user_data['admin_state'] = 'waiting_for_ban'
    await query.message.edit_text(
        "🚫 حظر مستخدم\n\n"
        "قم بإرسال معرف المستخدم (ID) الذي تريد حظره.\n\n"
        "للإلغاء، أرسل /cancel",
        reply_markup=InlineKeyboardMarkup([[
            InlineKeyboardButton("❌ إلغاء", callback_data="admin_back")
        ]])
    )

async def start_unban(query: Update.callback_query, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Start unban user process."""
    context.user_data['admin_state'] = 'waiting_for_unban'
    await query.message.edit_text(
        "✅ إلغاء حظر مستخدم\n\n"
        "قم بإرسال معرف المستخدم (ID) الذي تريد إلغاء حظره.\n\n"
        "للإلغاء، أرسل /cancel",
        reply_markup=InlineKeyboardMarkup([[
            InlineKeyboardButton("❌ إلغاء", callback_data="admin_back")
        ]])
    )

async def show_premium_users(query, db):
    """Show list of premium users."""
    premium_users = db.get_premium_users()

    if not premium_users:
        await query.message.edit_text(
            "📝 لا يوجد مستخدمين مميزين حالياً.",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 رجوع", callback_data="admin_back")]])
        )
        return

    # Get user details for each premium user
    premium_users_details = []
    for user_id in premium_users:
        user_data = db.get_user_stats(int(user_id))
        if user_data:
            username = user_data.get('username', 'غير معروف')
            first_name = user_data.get('first_name', 'غير معروف')
            premium_users_details.append(f"👤 المعرف: {user_id}\n   الاسم: {first_name}\n   المستخدم: @{username if username else 'غير متوفر'}\n")

    # Create the message
    message = "👑 قائمة المستخدمين المميزين:\n\n"
    message += "\n".join(premium_users_details)
    message += f"\n\nالعدد الإجمالي: {len(premium_users)} مستخدم"

    # Split message if it's too long
    if len(message) > 4096:
        message = message[:4000] + f"\n\n... والمزيد\nالعدد الإجمالي: {len(premium_users)} مستخدم"

    await query.message.edit_text(
        message,
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 رجوع", callback_data="admin_back")]])
    )

async def show_banned_users(query, db):
    """Show list of banned users."""
    banned_users = db.data["banned_users"]
    if not banned_users:
        await query.message.edit_text(
            "لا يوجد مستخدمين محظورين حالياً. ✅",
            reply_markup=get_admin_keyboard()
        )
        return

    banned_users_text = "📋 قائمة المستخدمين المحظورين:\n\n"
    for user_id in banned_users:
        user_data = db.data["users"].get(str(user_id), {})
        username = user_data.get("username", "")
        first_name = user_data.get("first_name", "")
        banned_users_text += f"- الاسم: {first_name}\n  المعرف: @{username}\n  رقم المعرف: {user_id}\n\n"

    await query.message.edit_text(
        banned_users_text,
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("🔙 رجوع", callback_data="admin_back")]
        ])
    )

async def start_forward_ad(query: Update.callback_query, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Start forward advertisement process."""
    # Clear any previous state
    context.user_data.clear()
    # Set new state
    context.user_data["admin_state"] = "waiting_forward_ad"
    await query.edit_message_text(
        "📤 تحويل إعلان\n\n"
        "قم بإرسال الإعلان الذي تريد تحويله (نص، صورة، فيديو، الخ).\n"
        "يمكنك إضافة أزرار للإعلان عن طريق إرسال الأزرار بالتنسيق التالي:\n"
        "عنوان الزر | الرابط\n"
        "عنوان الزر 2 | الرابط 2\n\n"
        "أو أرسل الإعلان بدون أزرار مباشرة.\n\n"
        "للإلغاء، أرسل /cancel"
    )

async def handle_forward_ad_message(update: Update, context: ContextTypes.DEFAULT_TYPE, db) -> None:
    """Handle forwarded advertisement message."""
    if not context.user_data.get("admin_state"):
        return

    message = update.message

    if message.text == "/cancel":
        context.user_data.clear()
        await message.reply_text(
            "تم إلغاء العملية الحالية.",
            reply_markup=get_admin_keyboard()
        )
        return

    if context.user_data["admin_state"] == "waiting_forward_ad":
        # Get all users from database
        all_users = db.data["users"].keys()
        total_users = len(all_users)

        # Send confirmation message with user count
        confirm_msg = await message.reply_text(
            f"⚠️ تأكيد إرسال الإعلان\n\n"
            f"سيتم إرسال الإعلان إلى {total_users} مستخدم\n"
            f"هل تريد المتابعة؟",
            reply_markup=InlineKeyboardMarkup([
                [
                    InlineKeyboardButton("✅ نعم، أرسل", callback_data="confirm_forward_ad"),
                    InlineKeyboardButton("❌ إلغاء", callback_data="cancel_forward_ad")
                ]
            ])
        )

        # Store the message and confirmation message
        context.user_data['forward_message'] = message
        context.user_data['confirm_msg'] = confirm_msg
        return

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
            last_active = datetime.fromisoformat(group.get('last_active', datetime.now().isoformat()))
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
