import logging
import json
import base64
import asyncio
import html
import re
from typing import Dict, List, Optional
from collections import deque

import aiohttp
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup, KeyboardButton
from telegram.ext import ContextTypes
from telegram.error import TelegramError

from ..config import GEMINI_API_KEYS, GEMINI_API_URL, BOT_SIGNATURE, ADMIN_NOTIFICATION_ID
from ..utils.formatting import format_message, add_signature
from ..utils.key_manager import KeyManager
from ..utils.search import search_exa
from ..utils.link_scanner import scan_link
from .admin import is_admin, admin_panel, handle_admin_message

logger = logging.getLogger(__name__)

class ConversationManager:
    def __init__(self, max_history: int = 15):
        self.histories: Dict[int, List[Dict]] = {}
        self.max_history = max_history

    def get_history(self, user_id: int) -> List[Dict]:
        if user_id not in self.histories:
            self.histories[user_id] = []
        return self.histories[user_id]

    def add_message(self, user_id: int, role: str, text: str, image_data: str = None):
        if user_id not in self.histories:
            self.histories[user_id] = []
        
        parts = [{"text": text}]
        if image_data:
            parts.append({
                "inline_data": {
                    "mime_type": "image/jpeg",
                    "data": image_data
                }
            })
            
        self.histories[user_id].append({
            "role": role,
            "parts": parts
        })
        
        # Trim history (keep last max_history messages)
        # Ensure we don't cut in the middle of a turn if possible, but simple trimming is okay for now.
        if len(self.histories[user_id]) > self.max_history:
            removed = self.histories[user_id][:-self.max_history]
            self.histories[user_id] = self.histories[user_id][-self.max_history:]
            # If the new first message is 'model', remove it to start with 'user' if strictly needed,
            # but Gemini usually handles it. To be safe:
            if self.histories[user_id] and self.histories[user_id][0]['role'] == 'model':
                self.histories[user_id].pop(0)

    def clear_history(self, user_id: int):
        self.histories[user_id] = []

conversation_manager = ConversationManager()
key_manager = KeyManager(GEMINI_API_KEYS)
subscription_cache: Dict[int, tuple] = {}
SUBSCRIPTION_CACHE_DURATION = 60  # seconds


def get_base_keyboard():
    keyboard = [
        [KeyboardButton(" محادثة جديدة")],
        [KeyboardButton(" البحث في الويب")],
        [KeyboardButton(" فحص الروابط")],
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

    is_new_user = not db.is_user_exist(user_id)
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

    conversation_manager.clear_history(user_id)
    welcome_message = (
        f"مرحباً بك {user.first_name} في بوت المساعد الذكي للطلاب! 👋\n\n"
        "يمكنني مساعدتك في:\n"
        "- الإجابة على الأسئلة الأكاديمية\n"
        "- شرح المفاهيم المعقدة\n"
        "- تحليل الصور وشرح محتواها\n"
        "- المساعدة في حل المسائل\n"
        "- تقديم نصائح للدراسة\n\n"
         "- البحث في الويب باستخدام الذكاء الاصطناعي \n\n"
        "يمكنك إرسال سؤال نصي أو صورة وسأقوم بمساعدتك! \n\n"
        "━━━━━━━━━━━━━━\n"
        " قناة التلجرام: @SyberSc71\n"
        " برمجة: @WAT4F"
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

        if user_message == " محادثة جديدة":
            conversation_manager.clear_history(user_id)
            await update.message.reply_text(
                f"تم مسح الذاكرة وبدء محادثة جديدة! كيف يمكنني مساعدتك؟{BOT_SIGNATURE}",
                reply_markup=get_base_keyboard()
            )
            return

        # ... (Search and Link Scan checks remain same) ...
        if user_message == " البحث في الويب":
            await update.message.reply_text("أدخل ما تريد البحث عنه:")
            context.user_data['waiting_for_search_query'] = True
            return

        if context.user_data.get('waiting_for_search_query'):
            await search_exa(update, context)
            context.user_data['waiting_for_search_query'] = False
            return
        if user_message == " فحص الروابط":
            await update.message.reply_text("الرجاء إدخال الرابط الذي تريد فحصه:")
            context.user_data["waiting_for_url_scan"] = True
            return

        if context.user_data.get("waiting_for_url_scan"):
            url_to_scan = user_message
            await update.message.reply_text("جارٍ فحص الرابط... ")
            scan_results = await scan_link(url_to_scan)
            await update.message.reply_text(f"نتائج الفحص:\n{scan_results}", reply_markup=get_base_keyboard())
            context.user_data["waiting_for_url_scan"] = False
            return    

        db.update_user_activity(user_id, "text")

        # Add user message to history
        conversation_manager.add_message(user_id, "user", user_message)

        # Get active prompt from database for System Instruction
        prompt_template = db.get_active_prompt()
        
        # Prepare payload
        history = conversation_manager.get_history(user_id)
        
        payload = {
            "system_instruction": {
                "parts": [{"text": prompt_template}]
            },
            "contents": history,
            "generationConfig": {
                "temperature": 0.7, "topK": 40, "topP": 0.95, "maxOutputTokens": 1024,
            }
        }
        headers = {"Content-Type": "application/json"}

        thinking_message = await update.message.reply_text("جار التفكير... ⏳")

        max_retries = 3
        for attempt in range(max_retries):
            current_key = key_manager.get_current_key()
            try:
                async with aiohttp.ClientSession() as session:
                    async with session.post(
                        f"{GEMINI_API_URL}?key={current_key}",
                        headers=headers, json=payload, timeout=aiohttp.ClientTimeout(total=50)
                    ) as response:
                        if response.status == 200:
                            # Success! cleanup thinking message if exists (only once)
                            if thinking_message:
                                try:
                                    await thinking_message.delete()
                                    thinking_message = None # Prevent multi-delete attempts
                                except (TelegramError, Exception) as e:
                                    logger.warning(f"Failed to delete thinking_message: {e}")

                            response_data = await response.json()

                            ai_response_text = "عذراً، لم أتمكن من معالجة طلبك."
                            try:
                                ai_response_text = response_data['candidates'][0]['content']['parts'][0]['text']
                            except (KeyError, IndexError, TypeError) as e:
                                logger.error(f"Error parsing Gemini response: {e}\nResponse: {response_data}")

                            # Format the raw text for displaying in Telegram
                            formatted_ai_response = format_message(ai_response_text)

                            # Add model response to history
                            conversation_manager.add_message(user_id, "model", ai_response_text)

                            await update.message.reply_text(
                                f"{formatted_ai_response}{BOT_SIGNATURE}",
                                reply_markup=get_base_keyboard(),
                                parse_mode='HTML'
                            )
                            return # Exit function on success
                        
                        elif response.status in [400, 403, 429, 500, 503]:
                            error_text = await response.text()
                            logger.warning(f"API Error (Attempt {attempt+1}): {response.status} - {error_text}")
                            key_manager.rotate_key()
                            continue # Retry loop
                        else:
                            # Fatal error
                            error_text = await response.text()
                            logger.error(f"API Fatal Error for user {user_id}: {response.status}\n{error_text}")
                            break # Exit loop
            except aiohttp.ClientError as e:
                logger.error(f"Network error in API request for user {user_id}: {e}")
                key_manager.rotate_key()
                continue
            
        # If we reach here, all retries failed
        if thinking_message:
             try:
                await thinking_message.delete()
             except: pass

        await update.message.reply_text(
            f"عذراً، هناك مشكلة في الاتصال أو الخوادم مشغولة. الرجاء المحاولة مرة أخرى.{BOT_SIGNATURE}",
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

        # Add image message to history
        conversation_manager.add_message(user_id, "user", caption, base64_image)

        # Get prompt and history
        prompt_template = db.get_active_prompt()
        history = conversation_manager.get_history(user_id)

        # Note: We use the same URL for generic content generation which supports both text and images if using gemini-1.5-flash or similar.
        # Ensure GEMINI_API_URL points to a multimodal model.
        
        payload = {
            "system_instruction": {
                "parts": [{"text": prompt_template}]
            },
            "contents": history,
            "generationConfig": {"temperature": 0.7, "topK": 32, "topP": 1, "maxOutputTokens": 4096}
        }

        processing_message = await update.message.reply_text("جاري معالجة الصورة... ⏳")
        headers = {"Content-Type": "application/json"}
        vision_url = GEMINI_API_URL 

        max_retries = 2
        success = False
        for attempt in range(max_retries):
            current_key = key_manager.get_current_key()
            try:
                async with aiohttp.ClientSession() as session:
                    async with session.post(
                        f"{vision_url}?key={current_key}",
                        headers=headers, json=payload, timeout=aiohttp.ClientTimeout(total=90)
                    ) as response:
                        if response.status == 200:
                            if processing_message:
                                try:
                                    await processing_message.delete()
                                    processing_message = None
                                except Exception as e:
                                    logger.warning(f"Failed to delete processing_message: {e}")

                            response_data = await response.json()

                            ai_response_text = "عذراً، لم أتمكن من تحليل الصورة."
                            try:
                                ai_response_text = response_data['candidates'][0]['content']['parts'][0]['text']
                            except (KeyError, IndexError, TypeError) as e:
                                logger.error(f"Error parsing Vision API response: {e}\nResponse: {response_data}")

                            formatted_response = format_message(ai_response_text)
                            
                            # Add model response to history
                            conversation_manager.add_message(user_id, "model", ai_response_text)

                            await update.message.reply_text(
                                f"{formatted_response}{BOT_SIGNATURE}",
                                reply_markup=get_base_keyboard(),
                                parse_mode='HTML'
                            )
                            success = True
                            break # Exit loop
                        elif response.status in [400, 403, 429, 500, 503]:
                            logger.warning(f"Vision API Error (Attempt {attempt+1}): {response.status}")
                            key_manager.rotate_key()
                            continue
                        else:
                            error_text = await response.text()
                            logger.error(f"Vision API Error for user {user_id}: {response.status}\n{error_text}")
                            break
            except Exception as e:
                logger.error(f"Vision Network Error: {e}")
                key_manager.rotate_key()
                continue
        
        if not success:
             if processing_message:
                try: await processing_message.delete()
                except: pass
             await update.message.reply_text(
                f"عذراً، معالجة الصور متوقفة مؤقتاً أو حدث خطأ.{BOT_SIGNATURE}",
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
