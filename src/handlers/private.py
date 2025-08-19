import logging
import json
import base64
import asyncio
import html
import re
from typing import Dict, List

import aiohttp
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup, KeyboardButton
from telegram.ext import ContextTypes
from telegram.error import TelegramError

from ..config import GEMINI_API_KEY, GEMINI_API_URL, BOT_SIGNATURE, ADMIN_NOTIFICATION_ID
from ..utils.formatting import format_message, add_signature
from ..utils.search import search_exa
from ..utils.link_scanner import scan_url
from .admin import is_admin, admin_panel, handle_admin_message

logger = logging.getLogger(__name__)

conversation_history: Dict[int, List[Dict]] = {}
subscription_cache: Dict[int, tuple] = {}
SUBSCRIPTION_CACHE_DURATION = 60  # seconds


def get_base_keyboard():
    keyboard = [
        [KeyboardButton("🔄 محادثة جديدة")],
        [KeyboardButton("🔍 البحث في الويب")],
        [KeyboardButton("🔗 فحص الروابط")],
    ]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
async def check_subscription(user_id: int, context: ContextTypes.DEFAULT_TYPE) -> bool:
    """Check if user is subscribed to the channel."""
    try:
        member = await context.bot.get_chat_member(chat_id="@cyber_code1", user_id=user_id)
        return member.status in ['member', 'administrator', 'creator']
    except Exception:
        return False

async def force_subscription(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Force user to subscribe to channel."""
    user_id = update.effective_user.id
    if not await check_subscription(user_id, context):
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("اشترك في القناة 📢", url="https://t.me/cyber_code1")],
            [InlineKeyboardButton("تحقق من الاشتراك ✅", callback_data="check_subscription")]
        ])
        await update.message.reply_text(
            "عذراً! يجب عليك الاشتراك في قناتنا أولاً للاستمرار.\n"
            "اشترك ثم اضغط على زر التحقق 👇 أو اضغط /start",
            reply_markup=keyboard
        )
        return False
    return True

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE, db) -> None:
    """Send a message when the command /start is issued."""
    user = update.effective_user
    user_id = user.id

    if user.username and is_admin(user.username):
        await update.message.reply_text(f"Your numeric ID is: {user_id}")

    is_new_user = str(user_id) not in db.data["users"]
    db.add_user(user_id, user.username or "", user.first_name)

    if is_new_user:
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

    conversation_history[user_id] = []
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

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE, db) -> None:
    """Handle text messages with conversation history using aiohttp."""
    if not await force_subscription(update, context):
        return

    try:
        user = update.effective_user
        user_id = user.id
        user_message = update.message.text

        if db.is_user_banned(user_id):
            await update.message.reply_text("عذراً، تم حظرك من استخدام البوت.")
            return

        if user.username and is_admin(user.username):
            if user_message == "/admin":
                await admin_panel(update, context)
                return
            if context.user_data.get("admin_state"):
                await handle_admin_message(update, context, db)
                return

        if user_message == "🔄 محادثة جديدة":
            conversation_history[user_id] = []
            await update.message.reply_text(
                f"تم بدء محادثة جديدة! كيف يمكنني مساعدتك؟{BOT_SIGNATURE}",
                reply_markup=get_base_keyboard()
            )
            return
        if user_message == "🔍 البحث في الويب":
            await update.message.reply_text("أدخل ما تريد البحث عنه:")
            context.user_data['waiting_for_search_query'] = True
            return

        if context.user_data.get('waiting_for_search_query'):
            await search_exa(update, context)
            context.user_data['waiting_for_search_query'] = False
            return
        if user_message == "🔗 فحص الروابط":
            await update.message.reply_text("الرجاء إدخال الرابط الذي تريد فحصه:")
            context.user_data["waiting_for_url_scan"] = True
            return

        if context.user_data.get("waiting_for_url_scan"):
            url_to_scan = user_message
            await update.message.reply_text("جارٍ فحص الرابط... ⏳")
            scan_results = await scan_url_all(url_to_scan)
            await update.message.reply_text(f"نتائج الفحص:\n{scan_results}", reply_markup=get_base_keyboard())
            context.user_data["waiting_for_url_scan"] = False
            return    

        db.update_user_activity(user_id, "text")

        if user_id not in conversation_history:
            conversation_history[user_id] = []

        conversation_history[user_id].append({
           "role": "user",
            "parts": [{"text": f"{user_message}"}]
        })

        messages_for_api = conversation_history[user_id][-10:]
        payload = {
            "contents": messages_for_api,
            "generationConfig": {
                "temperature": 0.7, "topK": 40, "topP": 0.95, "maxOutputTokens": 1024,
            }
        }
        headers = {"Content-Type": "application/json"}

        thinking_message = await update.message.reply_text("جار التفكير... ⏳")

        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    f"{GEMINI_API_URL}?key={GEMINI_API_KEY}",
                    headers=headers, json=payload, timeout=aiohttp.ClientTimeout(total=50)
                ) as response:
                    if thinking_message:
                        try:
                            await thinking_message.delete()
                        except (TelegramError, Exception) as e:
                            logger.warning(f"Failed to delete thinking_message: {e}")

                    if response.status == 200:
                        response_data = await response.json()
                        candidates = response_data.get('candidates')
                        if candidates and isinstance(candidates, list) and len(candidates) > 0:
                            content = candidates[0].get('content')
                            if content and isinstance(content, dict):
                                parts_list = content.get('parts')
                                if parts_list and isinstance(parts_list, list) and len(parts_list) > 0:
                                    ai_response_text = parts_list[0].get('text', 'عذراً، لم أستطع فهم الرسالة.')
                                else:
                                    ai_response_text = 'عذراً، تنسيق الرد غير متوقع.'
                            else:
                                ai_response_text = 'عذراً، تنسيق الرد غير متوقع.'
                        else:
                            ai_response_text = 'عذراً، لم يتم العثور على مرشحين في الرد.'

                        formatted_ai_response = format_message(ai_response_text)

                        conversation_history[user_id].append({
                            "role": "assistant",
                            "parts": [{"text": formatted_ai_response}]
                        })

                        await update.message.reply_text(
                            f"{formatted_ai_response}{BOT_SIGNATURE}",
                            reply_markup=get_base_keyboard(),
                            parse_mode='HTML'
                        )
                    else:
                        error_text = await response.text()
                        logger.error(f"API Error for user {user_id}: {response.status}\n{error_text}")
                        await update.message.reply_text(
                            "عذراً، الخدمة مشغولة حالياً. حاول مرة أخرى بعد قليل. 🙏",
                            reply_markup=get_base_keyboard()
                        )
        except aiohttp.ClientError as e:
            logger.error(f"Network error in API request for user {user_id}: {e}")
            await update.message.reply_text(
                f"عذراً، هناك مشكلة في الاتصال. الرجاء المحاولة مرة أخرى.{BOT_SIGNATURE}",
                reply_markup=get_base_keyboard(),
                parse_mode='HTML'
            )
    except Exception as e:
        logger.error(f"Outer error in handle_message for user {update.effective_user.id}: {e}", exc_info=True)
        await update.message.reply_text(
            f"عذراً، حدث خطأ ما. الرجاء المحاولة مرة أخرى.{BOT_SIGNATURE}",
            reply_markup=get_base_keyboard(),
            parse_mode='HTML'
        )

async def handle_photo(update: Update, context: ContextTypes.DEFAULT_TYPE, db) -> None:
    if not await force_subscription(update, context):
        return

    processing_message = None
    try:
        user = update.effective_user
        user_id = user.id

        if db.is_user_banned(user_id):
            await update.message.reply_text("عذراً، تم حظرك من استخدام البوت.")
            return

        if not db.is_user_premium(user_id):
            daily_count = db.get_daily_image_count_for_user(user_id)
            if daily_count >= 7:
                keyboard = [
                    [InlineKeyboardButton("⭐️ الترقية للعضوية المميزة", url="https://t.me/WAT4F")],
                    [InlineKeyboardButton("💬 تواصل مع الأدمن", url="https://t.me/WAT4F")]
                ]
                reply_markup = InlineKeyboardMarkup(keyboard)
                await update.message.reply_text(
                    "عذراً، لقد وصلت للحد الأقصى من الصور المسموح بها يومياً (7 صور).\n"
                    "للحصول على استخدام غير محدود، يرجى الترقية إلى العضوية المميزة.",
                    reply_markup=reply_markup
                )
                return

        db.update_user_activity(user_id, "image")

        photo = update.message.photo[-1]
        photo_file = await context.bot.get_file(photo.file_id)
        photo_data = await photo_file.download_as_bytearray()
        base64_image = base64.b64encode(photo_data).decode('utf-8')
        caption = update.message.caption or "قم بتحليل هذه الصورة وشرح محتواها"

        payload = {
            "contents": [{"role": "user", "parts": [
                {"text": caption},
                {"inline_data": {"mime_type": "image/jpeg", "data": base64_image}}
            ]}],
            "generationConfig": {"temperature": 0.7, "topK": 32, "topP": 1, "maxOutputTokens": 4096}
        }

        processing_message = await update.message.reply_text("جاري معالجة الصورة... ⏳")
        headers = {"Content-Type": "application/json"}
        vision_url = "https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash-latest:generateContent"

        async with aiohttp.ClientSession() as session:
            async with session.post(
                f"{vision_url}?key={GEMINI_API_KEY}",
                headers=headers, json=payload, timeout=aiohttp.ClientTimeout(total=60)
            ) as response:
                if processing_message:
                    try:
                        await processing_message.delete()
                    except Exception as e:
                        logger.warning(f"Failed to delete processing_message: {e}")

                if response.status == 200:
                    response_data = await response.json()
                    candidates = response_data.get('candidates')
                    ai_response_text = 'عذراً، لم أستطع تحليل الصورة.'
                    if candidates and isinstance(candidates, list) and len(candidates) > 0:
                        content = candidates[0].get('content')
                        if content and isinstance(content, dict):
                            parts_list = content.get('parts')
                            if parts_list and isinstance(parts_list, list) and len(parts_list) > 0:
                                ai_response_text = parts_list[0].get('text', ai_response_text)

                    formatted_response = format_text(ai_response_text)
                    await update.message.reply_text(
                        f"{formatted_response}{BOT_SIGNATURE}",
                        reply_markup=get_base_keyboard(),
                        parse_mode='HTML'
                    )
                else:
                    error_text = await response.text()
                    logger.error(f"Vision API Error for user {user_id}: {response.status}\n{error_text}")
                    await update.message.reply_text(
                        f"عذراً، حدث خطأ في معالجة الصورة. الرجاء المحاولة مرة أخرى.{BOT_SIGNATURE}",
                        reply_markup=get_base_keyboard(),
                        parse_mode='HTML'
                    )

    except Exception as e:
        logger.error(f"Unhandled Error in handle_photo for user {update.effective_user.id}: {e}", exc_info=True)
        if processing_message:
            try:
                await processing_message.delete()
            except Exception as e_del:
                logger.warning(f"Failed to delete processing_message in outer catch: {e_del}")

        await update.message.reply_text(
            f"عذراً، حدث خطأ غير متوقع. الرجاء المحاولة لاحقاً.{BOT_SIGNATURE}",
            reply_markup=get_base_keyboard(),
            parse_mode='HTML'
        )

async def check_subscription_callback(update: Update, context: ContextTypes.DEFAULT_TYPE, db):
    """Handle subscription check callback."""
    query = update.callback_query
    user_id = query.from_user.id

    if await check_subscription(user_id, context):
        await query.answer("✅ شكراً لك! يمكنك الآن استخدام البوت")
        await query.message.edit_text("تم التحقق من اشتراكك بنجاح! يمكنك الآن استخدام البوت ✅")
        await start(update, context, db)
    else:
        await query.answer("❌ عذراً، يجب عليك الاشتراك في القناة أولاً!")
