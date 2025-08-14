import logging
import base64
import asyncio
import html
import re
import aiohttp
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from telegram.error import TelegramError

from config import (
    GEMINI_API_KEY, GEMINI_API_URL, GEMINI_VISION_API_URL,
    BOT_SIGNATURE, PROMPT_PREFIX
)
from database import Database
from search import search_exa
from admin_panel import admin_panel, handle_admin_message, is_admin
from link_scanner import scan_url_all
from .utils import force_subscription, get_base_keyboard, format_text

logger = logging.getLogger(__name__)

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE, db: Database):
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
            db.clear_conversation_history(user_id)
            await update.message.reply_text(
                f"تم بدء محادثة جديدة! كيف يمكنني مساعدتك؟{BOT_SIGNATURE}",
                reply_markup=get_base_keyboard()
            )
            return
        if user_message == "🔍 البحث في الويب":
            await update.message.reply_text("أدخل ما تريد البحث عنه:")
            context.user_data['waiting_for_search_query'] = True
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

        if context.user_data.get('waiting_for_search_query'):
            await search_exa(update, context)
            context.user_data['waiting_for_search_query'] = False
            return

        db.update_user_activity(user_id, "text")
        
        user_message_payload = {
            "role": "user",
            "parts": [{"text": f"{PROMPT_PREFIX}\n\nUser message: {user_message}"}]
        }
        db.add_message_to_history(user_id, user_message_payload)

        # Retrieve the last 10 messages for the API call
        messages_for_api = db.get_conversation_history(user_id, limit=10)
        validated_messages = []
        for msg in messages_for_api:
            if isinstance(msg, dict) and "role" in msg and "parts" in msg:
                validated_messages.append(msg)
        validated_messages.append(user_message_payload)        
        payload = {
    "contents": validated_messages,  # استخدم هنا الرسائل المصفاة
    "generationConfig": {
        "temperature": 0.7,
        "topK": 40,
        "topP": 0.95,
        "maxOutputTokens": 1024,
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
                            logger.warning(f"Failed to delete thinking_message: {e} for user {user_id}")

                    if response.status == 200:
                        response_data = await response.json()
                        candidates = response_data.get('candidates')
                        if candidates and candidates[0].get('content', {}).get('parts'):
                            ai_response_text = candidates[0]['content']['parts'][0].get('text', 'عذراً، لم أستطع فهم الرسالة.')
                        else:
                            ai_response_text = 'عذراً، تنسيق الرد غير متوقع.'
                            logger.warning(f"Gemini API: Unexpected response format for user {user_id}. Response: {response_data}")

                        parts_google = ai_response_text.split("تم تدريبي بواسطة جوجل")
                        ai_response_text = "تم تدريبي بواسطة جوجل وتم ربطي في البوت وبرمجتي لاتعامل مع المستخدمين من قبل وهيب الشرعبي".join(parts_google)
                        parts_large_model = ai_response_text.split("أنا نموذج لغوي كبير")
                        ai_response_text = "تم ربطي في البوت وبرمجتي لاتعامل مع المستخدمين من قبل وهيب الشرعبي".join(parts_large_model)

                        formatted_ai_response = format_text(ai_response_text)

                        # Save assistant's response to history
                        assistant_message_payload = {"role": "model", "parts": [{"text": ai_response_text}]}
                        db.add_message_to_history(user_id, assistant_message_payload)

                        await update.message.reply_text(
                            f"{formatted_ai_response}{BOT_SIGNATURE}",
                            reply_markup=get_base_keyboard(), parse_mode='HTML'
                        )
                    else:
                        logger.error(f"API error for user {user_id}: {response.status} - {await response.text()}")
                        await update.message.reply_text("عذراً، الخدمة مشغولة حالياً. حاول مرة أخرى بعد قليل. 🙏", reply_markup=get_base_keyboard())

        except aiohttp.ClientError as e:
            logger.error(f"Network error for user {user_id}: {e}")
            await update.message.reply_text(f"عذراً، هناك مشكلة في الاتصال. الرجاء المحاولة مرة أخرى.{BOT_SIGNATURE}", reply_markup=get_base_keyboard())
        except Exception as e:
            logger.error(f"Error processing API response for user {user_id}: {e}", exc_info=True)
            await update.message.reply_text(f"عذراً، حدث خطأ أثناء معالجة الرد.{BOT_SIGNATURE}", reply_markup=get_base_keyboard())

    except Exception as e:
        logger.error(f"Outer error in handle_message for user {update.effective_user.id}: {e}", exc_info=True)
        await update.message.reply_text(f"عذراً، حدث خطأ ما. الرجاء المحاولة مرة أخرى.{BOT_SIGNATURE}", reply_markup=get_base_keyboard())

async def handle_photo(update: Update, context: ContextTypes.DEFAULT_TYPE, db: Database):
    """Handles photo messages and analyzes them using Gemini Vision."""
    if not await force_subscription(update, context):
        return

    processing_message = None
    try:
        user = update.effective_user
        user_id = user.id

        if db.is_user_banned(user_id):
            await update.message.reply_text("عذراً، تم حظرك من استخدام البوت.")
            return

        if not db.is_user_premium(user_id) and db.get_daily_image_count_for_user(user_id) >= 7:
            keyboard = [[InlineKeyboardButton("⭐️ الترقية للعضوية المميزة", url="https://t.me/WAT4F")]]
            await update.message.reply_text(
                "عذراً، لقد وصلت للحد الأقصى من الصور المسموح بها يومياً (7 صور).",
                reply_markup=InlineKeyboardMarkup(keyboard)
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
        vision_url = f"{GEMINI_VISION_API_URL}?key={GEMINI_API_KEY}"

        MAX_RETRIES = 2
        RETRY_DELAY = 5

        async with aiohttp.ClientSession() as session:
            for attempt in range(MAX_RETRIES + 1):
                try:
                    async with session.post(vision_url, headers=headers, json=payload, timeout=60) as response:
                        if processing_message:
                            try: await processing_message.delete()
                            except (TelegramError, Exception): pass
                            processing_message = None

                        if response.status == 200:
                            response_data = await response.json()
                            candidates = response_data.get('candidates')
                            if candidates and candidates[0].get('content', {}).get('parts'):
                                ai_response_text = candidates[0]['content']['parts'][0].get('text', 'عذراً، لم أستطع تحليل الصورة.')
                            else:
                                ai_response_text = 'عذراً، تنسيق الرد غير متوقع.'

                            formatted_response = format_text(ai_response_text)
                            await update.message.reply_text(
                                f"{formatted_response}{BOT_SIGNATURE}",
                                reply_markup=get_base_keyboard(), parse_mode='HTML'
                            )
                            return

                        elif response.status == 503 and attempt < MAX_RETRIES:
                            logger.warning(f"Gemini Vision API 503 (Attempt {attempt + 1}), retrying...")
                            await asyncio.sleep(RETRY_DELAY)
                            if not processing_message:
                                processing_message = await update.message.reply_text("جاري معالجة الصورة (إعادة محاولة)... ⏳")
                            continue
                        else:
                            logger.error(f"Vision API Error: {response.status} - {await response.text()}")
                            await update.message.reply_text("عذراً، حدث خطأ في معالجة الصورة.", reply_markup=get_base_keyboard())
                            return

                except aiohttp.ClientError as e:
                    logger.error(f"Network error in Vision API (Attempt {attempt + 1}): {e}")
                    if attempt < MAX_RETRIES:
                        await asyncio.sleep(RETRY_DELAY)
                        if processing_message:
                            try: await processing_message.delete()
                            except (TelegramError, Exception): pass
                        processing_message = await update.message.reply_text("جاري معالجة الصورة (إعادة محاولة اتصال)... ⏳")
                        continue
                    else:
                        await update.message.reply_text("مشكلة في الاتصال بالخدمة.", reply_markup=get_base_keyboard())
                        return

    except Exception as e:
        logger.error(f"Unhandled error in handle_photo for user {update.effective_user.id}: {e}", exc_info=True)
        if processing_message:
            try: await processing_message.delete()
            except (TelegramError, Exception): pass
        await update.message.reply_text("عذراً، حدث خطأ غير متوقع.", reply_markup=get_base_keyboard())
