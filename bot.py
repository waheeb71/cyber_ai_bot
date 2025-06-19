import logging
import json
import requests
import time
import base64
import asyncio
import os
import html
import datetime
import re
import aiohttp 
from telegram.error import TelegramError # <<<=== إضافة مهمة: لالتقاط أخطاء تليجرام المحددة
# --- Configuration Imports ---
from threading import Thread
from typing import Dict, List
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update, ReplyKeyboardMarkup, KeyboardButton
from telegram.constants import ChatMemberStatus # لاستخدامها في clear_messages
from telegram.error import *
from telegram.ext import *

# --- Configuration Imports ---
try:
    from config import TELEGRAM_TOKEN, GEMINI_API_KEY, GEMINI_API_URL, BOT_SIGNATURE, ADMIN_NOTIFICATION_ID
    from database import Database
    # تأكد من أن search_exa معرفة كـ async إذا كنت تستخدمها مع await
    from search import search_exa
    from admin_panel import (
    admin_panel,
    handle_admin_callback,
    handle_admin_message,
    get_admin_keyboard,
    get_groups_keyboard,
    show_groups,
    show_statistics,
    show_users,
    start_broadcast,
    show_ban_menu,
    start_ban,
    start_unban,
    show_banned_users,
    start_forward_ad,
    handle_forward_ad_message,
    start_groups_broadcast,
    handle_groups_broadcast,
    execute_groups_broadcast,
    is_admin
)
    from group_handler import GroupHandler
except ImportError as e:
    # استخدام logger هنا قد لا يكون متاحًا بعد، لذا نستخدم print
    print(f"Critical Import Error: {e}. Please ensure all required local files (config.py, database.py, etc.) are present.")
    exit(1)

# --- Flask Imports ---
from flask import Flask
from flask import request as flask_request # لتجنب التعارض

# --- Logging Setup ---
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
logger = logging.getLogger(__name__)

# --- Global Variables & Initialization ---
flask_app = Flask(__name__)
db = Database()

ptb_application: Application = None
main_event_loop: asyncio.AbstractEventLoop = None

WEBHOOK_URL = os.environ.get("RENDER_EXTERNAL_URL")
if not WEBHOOK_URL:
    logger.warning("WEBHOOK_URL not set. Webhook setup will be skipped. If deployed for webhook usage, the bot might not receive updates.")

conversation_history: Dict[int, List[Dict]] = {}
subscription_cache: Dict[int, tuple] = {}
SUBSCRIPTION_CACHE_DURATION = 60  # seconds


def get_base_keyboard():
    keyboard = [
        [KeyboardButton("🔄 محادثة جديدة")],
        [KeyboardButton("🔍 البحث في الويب")],
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

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Send a message when the command /start is issued."""
    user = update.effective_user
    user_id = user.id

    # Print user ID for admin
    if is_admin(user.username):
        await update.message.reply_text(f"Your numeric ID is: {user_id}")

    # Add user to database
    is_new_user = str(user_id) not in db.data["users"]
    db.add_user(user_id, user.username or "", user.first_name)

    # Send notification to admin about new user
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

    # Check if user is banned
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

def format_text(text: str) -> str:
    """Format mixed text (Arabic/English) for better readability with HTML support."""
    # Split text into paragraphs while preserving code blocks
    parts = []
    current_part = []
    in_code_block = False

    # First, split the text while preserving code blocks
    for line in text.split('\n'):
        if line.strip().startswith('```'):
            if in_code_block:
                # End of code block
                current_part.append(line)
                parts.append('\n'.join(current_part))
                current_part = []
                in_code_block = False
            else:
                # Start of code block
                if current_part:
                    parts.append('\n'.join(current_part))
                    current_part = []
                current_part.append(line)
                in_code_block = True
        else:
            current_part.append(line)

    # Add any remaining content
    if current_part:
        parts.append('\n'.join(current_part))

    formatted_parts = []
    for part in parts:
        if part.strip().startswith('```'):
            # Handle code block
            code_content = part.replace('```python', '').replace('```', '').strip()
            formatted_parts.append(f'<pre><code>{html.escape(code_content)}</code></pre>')
        else:
            # Handle regular text
            lines = part.split('\n')
            formatted_lines = []

            for line in lines:
                # Skip empty lines
                if not line.strip():
                    formatted_lines.append(line)
                    continue

                # Handle inline code
                line = re.sub(r'`([^`]+)`', lambda m: f'<code>{html.escape(m.group(1))}</code>', line)

                # Handle bold text
                line = re.sub(r'\*\*(.+?)\*\*', r'<b>\1</b>', line)
                line = re.sub(r'__(.+?)__', r'<b>\1</b>', line)

                # Handle italic text
                line = re.sub(r'\*(.+?)\*', r'<i>\1</i>', line)
                line = re.sub(r'_(.+?)_', r'<i>\1</i>', line)

                # Handle bullet points
                if line.strip().startswith(('•', '-', '*')):
                    line = f'• {line.strip().lstrip("•-* ")}'

                formatted_lines.append(line)

            formatted_parts.append('\n'.join(formatted_lines))

    # Join all parts with appropriate spacing
    final_text = '\n\n'.join(part for part in formatted_parts if part.strip())
    return final_text

def add_signature(text: str):
    """Add a signature to long messages"""
    signature = "\n\n━━━━━━━━━━━━━━\n📢 قناة التلجرام: @SyberSc71\n👨‍💻 برمجة: @WAT4F"
    return text + signature

def escape_markdown_v2(text: str) -> str:
    """Escape special characters for Markdown V2 format"""
    special_chars = ['_', '*', '[', ']', '(', ')', '~', '`', '>', '#', '+', '-', '=', '|', '{', '}', '.', '!']
    for char in special_chars:
        text = text.replace(char, f'\\{char}')
    return text

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle text messages with conversation history using aiohttp."""
    if not await force_subscription(update, context): # افترض أن force_subscription معرفة
        return

    # هذا try-except الخارجي جيد للمشاكل العامة في الدالة
    try:
        user = update.effective_user
        user_id = user.id
        user_message = update.message.text

        # التحقق إذا كان المستخدم محظورًا
        if db.is_user_banned(user_id):
            await update.message.reply_text("عذراً، تم حظرك من استخدام البوت.")
            return

        # التحقق إذا كان المستخدم هو الأدمن وفي وضع الأدمن
        # تأكد أن is_admin تتعامل مع حالة أن user.username قد يكون None
        if user.username and is_admin(user.username):
            if user_message == "/admin":
                await admin_panel(update, context)
                return
            if context.user_data.get("admin_state"):
                await handle_admin_message(update, context, db)
                return

        # التحقق من الأزرار الخاصة
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

        # التحقق إذا كان البوت ينتظر استعلام بحث
        if context.user_data.get('waiting_for_search_query'):
            await search_exa(update, context) # تأكد أن search_exa هي async
            context.user_data['waiting_for_search_query'] = False
            return
        
        db.update_user_activity(user_id, "text")

        if user_id not in conversation_history:
            conversation_history[user_id] = []

        conversation_history[user_id].append({
           "role": "user",
            "parts": [{
             "text": f"""{user_message} ━━━━━━━━━━━━━━
ملاحظة مرفقة مع الرسالة: كن إنسانيًا في تواصلك مع المستخدمين، 
وتحدث بأسلوب طبيعي يشعرهم بالود والحب. اجعل ردودك محببة وتصرفاتك مميزة. 
لا تذكر اسمي إلا إذا طُلب منك ذلك. 
اسمك على تليجرام هو ابو راس ، وتم ربطك عبر بوت تليجرام من قِبل وهيب الشرعبي من اليمن. 
تذكّر أن جنسيتك يمنية. 
وفي حال طُلب منك تقديم معلومة، كن عاقلًا وواقعيًا في ردك. 
استخدم الإيموجيات التفاعلية لجعل تواصلك أكثر مرحًا وجاذبية 😊✨.
 مهم :لو سالك حد عن مرضك قول له قد تحسنت لو ماحد سالك تجاهل  
"""
    }]
        })
        
        messages_for_api = conversation_history[user_id][-10:] # استخدام اسم متغير مختلف هنا
        payload = {
            "contents": messages_for_api,
            "generationConfig": {
                "temperature": 0.7,
                "topK": 40,
                "topP": 0.95,
                "maxOutputTokens": 1024,
            }
        }
        headers = {"Content-Type": "application/json"}

        thinking_message = None
        if update.message: # تأكد أن update.message ليس None
            thinking_message = await update.message.reply_text("جار التفكير... ⏳")

        ai_response_text_from_api = "" # تهيئة لتجنب خطأ UnboundLocalError

        try: # هذا الـ try خاص بطلب الـ API ومعالجته
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    f"{GEMINI_API_URL}?key={GEMINI_API_KEY}",
                    headers=headers,
                    json=payload,
                    timeout=aiohttp.ClientTimeout(total=50) # مهلة aiohttp
                ) as response:
                    # تم استلام كائن الرد (حتى لو كان خطأ HTTP)
                    # احذف رسالة "جار التفكير" الآن، قبل معالجة المحتوى أو إرسال الرد النهائي
                    if thinking_message:
                        try:
                            await thinking_message.delete()
                        except TelegramError as tg_err:
                            logger.warning(f"Failed to delete thinking_message (TelegramError): {tg_err} for user {user_id}")
                        except Exception as e_del:
                            logger.warning(f"Failed to delete thinking_message (General Error): {e_del} for user {user_id}")
                        thinking_message = None # للإشارة إلى أنه تم التعامل معها

                    if response.status == 200:
                        response_data = await response.json()
                        
                        # تحليل أكثر أمانًا للرد من Gemini
                        candidates = response_data.get('candidates')
                        if candidates and isinstance(candidates, list) and len(candidates) > 0:
                            content = candidates[0].get('content')
                            if content and isinstance(content, dict):
                                parts_list = content.get('parts')
                                if parts_list and isinstance(parts_list, list) and len(parts_list) > 0:
                                    ai_response_text_from_api = parts_list[0].get('text', 'عذراً، لم أستطع فهم الرسالة.')
                                else:
                                    ai_response_text_from_api = 'عذراً، تنسيق الرد غير متوقع (no parts list).'
                                    logger.warning(f"Gemini API: No 'parts' list in response content for user {user_id}. Response: {response_data}")
                            else:
                                ai_response_text_from_api = 'عذراً، تنسيق الرد غير متوقع (no content dict).'
                                logger.warning(f"Gemini API: No 'content' dict in candidate for user {user_id}. Response: {response_data}")
                        else:
                            ai_response_text_from_api = 'عذراً، لم يتم العثور على مرشحين في الرد.'
                            logger.warning(f"Gemini API: No 'candidates' list in response for user {user_id}. Response: {response_data}")

                        # تعديل نص الرد
                        parts_google = ai_response_text_from_api.split("تم تدريبي بواسطة جوجل")
                        ai_response_text_from_api = "تم تدريبي بواسطة جوجل وتم ربطي في البوت وبرمجتي لاتعامل مع المستخدمين من قبل وهيب الشرعبي".join(parts_google)
                        parts_large_model = ai_response_text_from_api.split("أنا نموذج لغوي كبير")
                        ai_response_text_from_api = "تم ربطي في البوت وبرمجتي لاتعامل مع المستخدمين من قبل وهيب الشرعبي".join(parts_large_model)

                        formatted_ai_response = format_text(ai_response_text_from_api) # هذا قد يسبب خطأ أيضاً

                        conversation_history[user_id].append({
                            "role": "assistant",
                            "parts": [{"text": formatted_ai_response}] # حفظ النص المنسق أو الأصلي؟ يفضل الأصلي إذا كان التنسيق للعرض فقط
                        })

                        await update.message.reply_text(
                            f"{formatted_ai_response}{BOT_SIGNATURE}",
                            reply_markup=get_base_keyboard(),
                            parse_mode='HTML'
                        )
                    elif response.status == 503:
                        logger.warning(f"Gemini API returned 503 for user {user_id}. Full response status: {response.status}")
                        await update.message.reply_text("حدث خطاء في الخادم. يرجى المحاولة لاحقاً.", reply_markup=get_base_keyboard())
                    else: # أخطاء HTTP أخرى غير 200 و 503
                        error_text_from_api = await response.text() # مهم لقراءة نص الخطأ
                        error_message = f"خطأ في الAPI لـ user {user_id}: {response.status}\n{error_text_from_api}"
                        logger.error(error_message)
                        await update.message.reply_text(
                            "عذراً، الخدمة مشغولة حالياً. حاول مرة أخرى بعد قليل. 🙏",
                            reply_markup=get_base_keyboard()
                        )
        
        except aiohttp.ClientError as e_aio: # لمعالجة أخطاء الشبكة مثل انتهاء المهلة، فشل الاتصال، إلخ.
            logger.error(f"Network error (aiohttp.ClientError) in API request for user {user_id}: {str(e_aio)}")
            if thinking_message: # إذا حدث الخطأ بعد إرسال رسالة "جار التفكير"
                try: await thinking_message.delete()
                except: pass # محاولة أخيرة للحذف
            await update.message.reply_text(
                f"عذراً، هناك مشكلة في الاتصال. الرجاء المحاولة مرة أخرى.{BOT_SIGNATURE}",
                reply_markup=get_base_keyboard(),
                parse_mode='HTML'
            )
        except Exception as e_api_proc: # لالتقاط الأخطاء من .json(), format_text, أو مشاكل غير متوقعة أخرى
                                        # أثناء معالجة كتلة API بعد اتصال ناجح.
            logger.error(f"Error during API response processing for user {user_id}: {str(e_api_proc)}", exc_info=True)
            if thinking_message: # إذا حدث الخطأ قبل حذف الرسالة (مثلاً فشل .json() على بيانات تالفة)
                try: await thinking_message.delete()
                except: pass
            await update.message.reply_text(
                f"عذراً، حدث خطأ أثناء معالجة الرد. الرجاء المحاولة مرة أخرى.{BOT_SIGNATURE}",
                reply_markup=get_base_keyboard(),
                parse_mode='HTML'
            )

    except Exception as e_outer: # try-except الخارجي لأي أخطاء أخرى في الدالة
        user_id_for_log = update.effective_user.id if update and update.effective_user else 'UnknownUser'
        logger.error(f"Outer error in handle_message for user {user_id_for_log}: {str(e_outer)}", exc_info=True)
        # لا تحاول حذف thinking_message هنا بشكل مباشر، فقد يكون قد تم حذفه أو لم يتم إنشاؤه.
        # الكتل الداخلية يجب أن تكون قد تعاملت معه.
        if update and update.message: # تأكد من وجود update.message قبل محاولة الرد
            await update.message.reply_text(
                f"عذراً، حدث خطأ ما. الرجاء المحاولة مرة أخرى.{BOT_SIGNATURE}",
                reply_markup=get_base_keyboard(),
                parse_mode='HTML'
            )
        else:
            logger.error(f"Outer error in handle_message for user {user_id_for_log} but update.message is None. Cannot send reply.")

import logging
import json
import base64
import asyncio
import html # يفترض أنه موجود

import aiohttp # <<<=== إضافة مهمة
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from telegram.error import TelegramError # <<<=== إضافة مهمة

# افترض أن المتغيرات والدوال التالية معرفة في النطاق العام أو مستوردة:
# db, GEMINI_API_KEY, BOT_SIGNATURE, force_subscription, get_base_keyboard, format_text
# logger (يفترض أنه مهيأ)

logger = logging.getLogger(__name__) # تأكد من وجود هذا أو أنه مهيأ في الملف الرئيسي

# --- دوال مساعدة (يفترض أنها معرفة في مكان آخر) ---
# async def force_subscription(update: Update, context: ContextTypes.DEFAULT_TYPE) -> bool: ...
# def get_base_keyboard(): ...
# def format_text(text: str) -> str: ...
# class Database: ... (أو db instance)
# GEMINI_API_KEY = "YOUR_API_KEY"
# BOT_SIGNATURE = "Your Bot Signature"
# ----------------------------------------------------


async def handle_photo(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not await force_subscription(update, context):
        return

    processing_message = None # تهيئة المتغير

    try:
        user = update.effective_user
        user_id = user.id

        if db.is_user_banned(user_id):
            await update.message.reply_text("عذراً، تم حظرك من استخدام البوت.")
            return

        # التحقق من العضوية المميزة وحدود الاستخدام اليومي للصور
        # if not db.is_user_premium(user_id): # افترض أن db.is_user_premium معرفة
        #     daily_count = db.get_daily_image_count_for_user(user_id) # افترض أن db.get_daily_image_count_for_user معرفة
        #     # ضع حدًا هنا (مثلاً 7 صور)
        #     IMAGE_LIMIT_NON_PREMIUM = 7
        #     if daily_count >= IMAGE_LIMIT_NON_PREMIUM:
        #         keyboard = [
        #             [InlineKeyboardButton("⭐️ الترقية للعضوية المميزة", url="https://t.me/WAT4F")],
        #             [InlineKeyboardButton("💬 تواصل مع الأدمن", url="https://t.me/WAT4F")]
        #         ]
        #         reply_markup = InlineKeyboardMarkup(keyboard)
        #         await update.message.reply_text(
        #             f"عذراً، لقد وصلت للحد الأقصى من الصور المسموح بها يومياً ({IMAGE_LIMIT_NON_PREMIUM} صور).\n"
        #             "للحصول على استخدام غير محدود، يرجى الترقية إلى العضوية المميزة.",
        #             reply_markup=reply_markup
        #         )
        #         return
        # الكود الموجود يفعل هذا بشكل صحيح

        # الكود الأصلي للتحقق من العضوية المميزة وحدود الاستخدام اليومي:
        if not db.is_user_premium(user_id):
            daily_count = db.get_daily_image_count_for_user(user_id)
            if daily_count >= 7: # يمكنك جعل '7' ثابتًا أو قابل للتكوين
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


        db.update_user_activity(user_id, "image") # افترض أن db.update_user_activity معرفة

        photo = update.message.photo[-1]
        photo_file = await context.bot.get_file(photo.file_id)
        photo_data = await photo_file.download_as_bytearray()
        base64_image = base64.b64encode(photo_data).decode('utf-8')
        caption = update.message.caption or "قم بتحليل هذه الصورة وشرح محتواها"

        payload = {
            "contents": [{
                "role": "user",
                "parts": [
                    {"text": caption},
                    {
                        "inline_data": {
                            "mime_type": "image/jpeg", # أو image/png إذا كنت تدعمها
                            "data": base64_image
                        }
                    }
                ]
            }],
            "generationConfig": {
                "temperature": 0.7,
                "topK": 32,
                "topP": 1,
                "maxOutputTokens": 4096, # تأكد من أن هذا مناسب لـ gemini-2.0-flash
            }
        }

        if update.message: # تأكد من وجود update.message قبل إرسال الرد
            processing_message = await update.message.reply_text("جاري معالجة الصورة... ⏳")

        headers = {"Content-Type": "application/json"}
        # تأكد من أن اسم النموذج صحيح. Gemini Pro Vision كان "gemini-pro-vision".
        # "gemini-2.0-flash" قد لا يكون نموذج vision، أو قد يكون له endpoint مختلف.
        # راجع وثائق Gemini للنماذج المتاحة ونقاط النهاية الصحيحة.
        # سأستخدم "gemini-pro-vision" كمثال، عدله إذا كان "gemini-2.0-flash" هو الصحيح لـ vision.
        # vision_url = "https://generativelanguage.googleapis.com/v1beta/models/gemini-pro-vision:generateContent"
        vision_url = "https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash-latest:generateContent" # أو اسم النموذج الصحيح الذي تستخدمه
        # لقد استخدمت gemini-1.5-flash-latest لأنه نموذج أحدث ويدعم الصور. تأكد من مطابقته لما لديك.

        MAX_RETRIES = 2 # عدد مرات إعادة المحاولة في حالة 503
        RETRY_DELAY = 5 # ثواني

        response_obj = None # لتعريف المتغير خارج الحلقة

        async with aiohttp.ClientSession() as session:
            for attempt in range(MAX_RETRIES + 1): # +1 لأن المحاولة الأولى هي attempt 0
                try:
                    async with session.post(
                        f"{vision_url}?key={GEMINI_API_KEY}",
                        headers=headers,
                        json=payload,
                        timeout=aiohttp.ClientTimeout(total=60) # مهلة إجمالية 60 ثانية
                    ) as response_obj_inner: # استخدم اسمًا مختلفًا هنا لتجنب التضارب
                        response_obj = response_obj_inner # قم بتعيينه للمتغير الخارجي
                        
                        # حذف رسالة "جاري المعالجة" بمجرد الحصول على الرد (حتى لو كان خطأ)
                        if processing_message:
                            try:
                                await processing_message.delete()
                            except TelegramError as tg_err:
                                logger.warning(f"Failed to delete processing_message (TelegramError): {tg_err} for user {user_id}")
                            except Exception as e_del:
                                logger.warning(f"Failed to delete processing_message (General Error): {e_del} for user {user_id}")
                            processing_message = None # للإشارة إلى أنه تم التعامل معها

                        if response_obj.status == 200:
                            response_data = await response_obj.json()
                            
                            # تحليل أكثر أمانًا للرد
                            candidates = response_data.get('candidates')
                            ai_response_text = 'عذراً، لم أستطع تحليل الصورة.' # قيمة افتراضية
                            if candidates and isinstance(candidates, list) and len(candidates) > 0:
                                content = candidates[0].get('content')
                                if content and isinstance(content, dict):
                                    parts_list = content.get('parts')
                                    if parts_list and isinstance(parts_list, list) and len(parts_list) > 0:
                                        ai_response_text = parts_list[0].get('text', ai_response_text)
                                    else: logger.warning(f"Gemini Vision: No 'parts' list in response for user {user_id}. Response: {response_data}")
                                else: logger.warning(f"Gemini Vision: No 'content' dict in candidate for user {user_id}. Response: {response_data}")
                            else: logger.warning(f"Gemini Vision: No 'candidates' list in response for user {user_id}. Response: {response_data}")

                            formatted_response = format_text(ai_response_text) # افترض أن format_text معرفة
                            await update.message.reply_text(
                                f"{formatted_response}{BOT_SIGNATURE}",
                                reply_markup=get_base_keyboard(),
                                parse_mode='HTML'
                            )
                            return # تم بنجاح، اخرج من الدالة

                        elif response_obj.status == 503:
                            logger.warning(f"Gemini Vision API returned 503 (Attempt {attempt + 1}/{MAX_RETRIES + 1}) for user {user_id}.")
                            if attempt < MAX_RETRIES:
                                logger.info(f"Retrying after {RETRY_DELAY} seconds...")
                                await asyncio.sleep(RETRY_DELAY)
                                # أعد إرسال رسالة "جاري المعالجة" إذا تم حذفها
                                if update.message and not processing_message:
                                    processing_message = await update.message.reply_text("جاري معالجة الصورة (إعادة محاولة)... ⏳")
                                continue # انتقل إلى المحاولة التالية
                            else:
                                logger.error(f"Max retries reached for 503 error for user {user_id}.")
                                await update.message.reply_text(
                                    f"عذراً، الخدمة مشغولة جداً حالياً. حاول مرة أخرى بعد قليل.{BOT_SIGNATURE}",
                                    reply_markup=get_base_keyboard(),
                                    parse_mode='HTML'
                                )
                                return # فشل بعد كل المحاولات

                        else: # أخطاء HTTP أخرى
                            error_text = await response_obj.text()
                            logger.error(f"❌ خطأ في Gemini Vision API لـ user {user_id}: {response_obj.status}\n{error_text}")
                            await update.message.reply_text(
                                f"عذراً، حدث خطأ في معالجة الصورة. الرجاء المحاولة مرة أخرى.{BOT_SIGNATURE}",
                                reply_markup=get_base_keyboard(),
                                parse_mode='HTML'
                            )
                            return # فشل، اخرج

                except aiohttp.ClientError as e_aio: # أخطاء الشبكة (مثل انتهاء المهلة)
                    logger.error(f"Network error (aiohttp.ClientError) in Vision API request for user {user_id} (Attempt {attempt + 1}): {str(e_aio)}")
                    if attempt < MAX_RETRIES:
                        if processing_message: # حاول حذفها إذا كانت لا تزال موجودة
                            try: await processing_message.delete(); processing_message = None
                            except: pass
                        logger.info(f"Retrying after {RETRY_DELAY} seconds due to network error...")
                        await asyncio.sleep(RETRY_DELAY)
                        if update.message and not processing_message: # أعد إرسالها قبل المحاولة التالية
                             processing_message = await update.message.reply_text("جاري معالجة الصورة (إعادة محاولة اتصال)... ⏳")
                        continue
                    else:
                        logger.error(f"Max retries reached for network error for user {user_id}.")
                        if processing_message: # تأكد من حذفها إذا لم يتم حذفها بالفعل
                            try: await processing_message.delete(); processing_message = None
                            except: pass
                        await update.message.reply_text(
                            f"عذراً، هناك مشكلة في الاتصال بالخدمة. الرجاء المحاولة مرة أخرى.{BOT_SIGNATURE}",
                            reply_markup=get_base_keyboard(),
                            parse_mode='HTML'
                        )
                        return
                # لا يوجد داعي لكتلة finally هنا لأن حذف processing_message يتم الآن داخل الحلقة

            # إذا وصلنا إلى هنا، فهذا يعني أن جميع المحاولات فشلت ولم يتم الخروج من داخل الحلقة
            # هذا السيناريو يجب أن يتم تغطيته بالفعل بالـ returns داخل الحلقة
            logger.error(f"Fell through retry loop for user {user_id}, this should not happen if logic is correct.")
            if processing_message: # محاولة أخيرة للحذف إذا لزم الأمر
                try: await processing_message.delete()
                except: pass
            await update.message.reply_text(
                f"عذراً، فشلت معالجة الصورة بعد عدة محاولات.{BOT_SIGNATURE}",
                reply_markup=get_base_keyboard(), parse_mode='HTML'
            )


    except Exception as e: # try-except الخارجي لأي أخطاء غير معالجة
        user_id_for_log = update.effective_user.id if update and update.effective_user else 'UnknownUser'
        logger.error(f"Unhandled Error in handle_photo for user {user_id_for_log}: {str(e)}", exc_info=True)
        if processing_message: # إذا كان الخطأ غير المعالج حدث بعد إرسال رسالة المعالجة
            try:
                await processing_message.delete()
            except Exception as e_del_final:
                logger.warning(f"Failed to delete processing_message in outer catch: {e_del_final}")
        
        if update and update.message:
            await update.message.reply_text(
                f"عذراً، حدث خطأ غير متوقع. الرجاء المحاولة لاحقاً.{BOT_SIGNATURE}",
                reply_markup=get_base_keyboard(),
                parse_mode='HTML'
            )
        else:
            logger.error(f"Outer error in handle_photo for user {user_id_for_log} but update.message is None. Cannot send reply.")
async def admin_callback_wrapper(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Wrapper for admin callback to include database."""
    query = update.callback_query

    if not query.from_user.username or not is_admin(query.from_user.username):
        await query.answer("عذراً، هذا الأمر متاح للمشرفين فقط.")
        return

    try:
        if query.data == "confirm_broadcast":
            await execute_groups_broadcast(query, context, db)
        elif query.data in ["groups_stats", "groups_search", "groups_inactive", "groups_refresh", "groups_cleanup"]:
            if query.data == "groups_stats":
                await show_groups(query, db)
            elif query.data == "groups_search":
                context.user_data['admin_state'] = 'waiting_group_search'
                await query.message.edit_text(
                    "🔍 *البحث عن مجموعة*\n\n"
                    "أرسل اسم المجموعة أو معرفها للبحث عنها",
                    reply_markup=InlineKeyboardMarkup([[
                        InlineKeyboardButton("🔙 رجوع", callback_data="admin_groups")
                    ]]),
                    parse_mode='Markdown'
                )
            elif query.data == "groups_inactive":
                inactive_groups = [g for g in db.get_all_groups() if g.get('message_count', 0) == 0]
                message = "⚠️ *المجموعات غير النشطة*\n\n"

                if not inactive_groups:
                    message += "لا توجد مجموعات غير نشطة! 🎉"
                else:
                    for i, group in enumerate(inactive_groups, 1):
                        message += f"{i}. *{group.get('title', 'مجموعة غير معروفة')}*\n"
                        message += f"   📱 المعرف: `{group.get('chat_id')}`\n"
                        join_date = datetime.fromisoformat(group.get('join_date', datetime.now().isoformat()))
                        days_since_join = (datetime.now() - join_date).days
                        message += f"   ⏰ مضى على الانضمام: `{days_since_join} يوم`\n\n"

                await query.message.edit_text(
                    message,
                    reply_markup=get_groups_keyboard(),
                    parse_mode='Markdown'
                )
            elif query.data == "groups_refresh":
                # تحديث معلومات المجموعات
                await query.message.edit_text(
                    "🔄 جاري تحديث معلومات المجموعات...",
                    reply_markup=None
                )

                groups = db.get_all_groups()
                updated = 0
                removed = 0

                for group in groups:
                    try:
                        chat = await context.bot.get_chat(int(group['chat_id']))
                        db.update_group_info(group['chat_id'], {
                            'title': chat.title,
                            'members_count': chat.get_member_count()
                        })
                        updated += 1
                    except telegram.error.BadRequest:
                        # المجموعة غير موجودة أو تم طرد البوت
                        db.remove_group(group['chat_id'])
                        removed += 1
                    except Exception as e:
                        logging.error(f"Error updating group {group['chat_id']}: {str(e)}")

                await query.message.edit_text(
                    f"✅ *تم تحديث المعلومات!*\n\n"
                    f"📊 النتائج:\n"
                    f"• تم تحديث: `{updated}` مجموعة\n"
                    f"• تم حذف: `{removed}` مجموعة\n"
                    f"• المجموع: `{updated + removed}` مجموعة",
                    reply_markup=get_groups_keyboard(),
                    parse_mode='Markdown'
                )
            elif query.data == "groups_cleanup":
                inactive_groups = [g for g in db.get_all_groups() if g.get('message_count', 0) == 0]
                if not inactive_groups:
                    await query.message.edit_text(
                        "✨ لا توجد مجموعات غير نشطة للحذف!",
                        reply_markup=get_groups_keyboard()
                    )
                    return

                # تأكيد الحذف
                await query.message.edit_text(
                    f"⚠️ *تأكيد الحذف*\n\n"
                    f"سيتم حذف {len(inactive_groups)} مجموعة غير نشطة.\n"
                    f"هل أنت متأكد؟",
                    reply_markup=InlineKeyboardMarkup([
                        [InlineKeyboardButton("✅ نعم، احذف", callback_data="confirm_cleanup"),
                         InlineKeyboardButton("❌ لا، إلغاء", callback_data="admin_groups")]
                    ]),
                    parse_mode='Markdown'
                )
        else:
            await handle_admin_callback(update, context, db)
    except Exception as e:
        logging.error(f"Error in admin_callback_wrapper: {str(e)}")
        await query.message.edit_text(
            "⚠️ حدث خطأ أثناء تنفيذ العملية\nالرجاء المحاولة مرة أخرى",
            reply_markup=get_admin_keyboard()
        )

async def check_subscription_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle subscription check callback."""
    query = update.callback_query
    user_id = query.from_user.id

    if await check_subscription(user_id, context):
        await query.answer("✅ شكراً لك! يمكنك الآن استخدام البوت")
        await query.message.edit_text("تم التحقق من اشتراكك بنجاح! يمكنك الآن استخدام البوت ✅")
        await start(update, context)
    else:
        await query.answer("❌ عذراً، يجب عليك الاشتراك في القناة أولاً!")

async def clear_messages(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Clear messages in a group chat."""
    if not update.message or not update.message.chat.type in ['group', 'supergroup']:
        await update.message.reply_text("هذا الأمر يعمل فقط في المجموعات!")
        return

    # Check if the bot has delete messages permission
    chat_member = await context.bot.get_chat_member(update.message.chat_id, context.bot.id)
    if not chat_member.can_delete_messages:
        await update.message.reply_text("عذراً، لا أملك صلاحية حذف الرسائل في هذه المجموعة!")
        return

    try:
        # Delete the command message first
        await update.message.delete()

        # Get the message ID of the command
        message_id = update.message.message_id

        # Delete 100 messages before this one (you can adjust this number)
        for i in range(message_id - 100, message_id):
            try:
                await context.bot.delete_message(update.message.chat_id, i)
            except Exception:
                continue

        # Send confirmation message that will be deleted after 5 seconds
        msg = await context.bot.send_message(
            update.message.chat_id,
            "تم تنظيف الرسائل! ✨"
        )

        # Delete the confirmation message after 5 seconds
        await asyncio.sleep(5)
        await msg.delete()

    except Exception as e:
        logger.error(f"Error in clear_messages: {str(e)}")
        await update.message.reply_text("حدث خطأ أثناء محاولة حذف الرسائل.")

# --- Flask Routes ---
@flask_app.route(f"/{TELEGRAM_TOKEN}", methods=["POST"])
def telegram_webhook_sync():
    global ptb_application, main_event_loop
    if not ptb_application or not main_event_loop or not main_event_loop.is_running():
        logger.error("PTB Application or its event loop is not ready for webhook.")
        return "Internal Server Error: Bot not ready", 500

    try:
        raw_json_data = flask_request.get_data()
        update_dict = json.loads(raw_json_data.decode("utf-8"))
        update = Update.de_json(update_dict, ptb_application.bot)

        asyncio.run_coroutine_threadsafe(ptb_application.process_update(update), main_event_loop)
    except json.JSONDecodeError:
        logger.error("Failed to decode JSON from webhook.", exc_info=True)
        return "Bad Request: Invalid JSON", 400
    except Exception as e:
        logger.error(f"Error processing update in webhook: {e}", exc_info=True)
        return "Internal Server Error", 500
    return "ok", 200

@flask_app.route("/", methods=["GET"])
def home():
    return "✅ Bot is alive and webhook is configured!", 200


# --- PTB Setup and Main Execution ---
def setup_handlers(app: Application):
    group_handler_instance = GroupHandler(db) # مرر db إذا كان GroupHandler يحتاجها

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("admin", admin_panel))
    app.add_handler(CommandHandler("clear", clear_messages))

    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND & filters.ChatType.PRIVATE, handle_message))
    app.add_handler(MessageHandler(filters.PHOTO & filters.ChatType.PRIVATE, handle_photo))
    
    app.add_handler(CallbackQueryHandler(check_subscription_callback, pattern="^check_subscription$"))
    # تأكد أن admin_callback_wrapper لا يتداخل مع check_subscription.
    # إذا كان admin_callback_wrapper عامًا جدًا (بدون نمط)، يجب أن يكون بعد check_subscription.
    app.add_handler(CallbackQueryHandler(admin_callback_wrapper)) 

    # Group Handlers
    app.add_handler(CommandHandler('cyber', group_handler_instance.cyber_command))
    app.add_handler(CommandHandler('help', group_handler_instance.help_command))
    app.add_handler(MessageHandler(filters.ChatType.GROUPS & filters.TEXT & ~filters.COMMAND, group_handler_instance.handle_message))
    app.add_handler(MessageHandler(filters.ChatType.GROUPS & filters.PHOTO, group_handler_instance.handle_message))
    
    logger.info("All PTB handlers added.")

async def ptb_async_setup_and_run(app_instance: Application, loop: asyncio.AbstractEventLoop):
    asyncio.set_event_loop(loop)
    await app_instance.initialize()
    logger.info("PTB Application initialized in its dedicated event loop.")

    if WEBHOOK_URL:
        webhook_full_url = f"{WEBHOOK_URL}/{TELEGRAM_TOKEN}"
        try:
            current_webhook = await app_instance.bot.get_webhook_info()
            if not current_webhook or current_webhook.url != webhook_full_url:
                await app_instance.bot.set_webhook(
                    url=webhook_full_url,
                    allowed_updates=Update.ALL_TYPES,
                    drop_pending_updates=True # تجاهل التحديثات المعلقة عند البدء
                )
                logger.info(f"Webhook set/updated to {webhook_full_url} successfully!")
            else:
                logger.info(f"Webhook already correctly set to {webhook_full_url}.")
            
            webhook_info = await app_instance.bot.get_webhook_info()
            logger.info(f"Current webhook_info: {webhook_info}")

        except Exception as e:
            logger.error(f"Failed to set webhook: {e}", exc_info=True)
            logger.error("Exiting due to webhook setup failure. Ensure TELEGRAM_TOKEN and WEBHOOK_URL are correct and the bot can be reached.")
            os._exit(1) # خروج فوري لأن هذا thread
    else:
        logger.warning("WEBHOOK_URL not defined. Webhook not set. Bot will not process webhook updates.")
        logger.info("If you intend to run locally with polling, uncomment the run_polling line below and ensure Flask is not started, or manage them carefully.")
        # logger.info("Starting PTB in polling mode as WEBHOOK_URL is not set.")
        # await app_instance.run_polling(allowed_updates=Update.ALL_TYPES)
        # return # إنهاء الدالة إذا بدأت polling
    # لا تستدعي run_polling إذا كنت تستخدم webhook. الـ loop سيبقى يعمل.

def run_ptb_thread_target(app_inst: Application, loop: asyncio.AbstractEventLoop):
    global main_event_loop # تأكد من تحديث الـ global loop المستخدم في webhook_sync
    main_event_loop = loop
    
    asyncio.set_event_loop(loop)
    try:
        loop.run_until_complete(ptb_async_setup_and_run(app_inst, loop))
        loop.run_forever()
    except KeyboardInterrupt:
        logger.info("PTB event loop interrupted by KeyboardInterrupt (from run_ptb_thread_target).")
    finally:
        logger.info("PTB event loop is stopping (from run_ptb_thread_target).")
        if loop.is_running():
            loop.run_until_complete(app_inst.shutdown())
        loop.close()
        logger.info("PTB event loop closed (from run_ptb_thread_target).")

if __name__ == "__main__":
    ptb_application_instance = ApplicationBuilder().token(TELEGRAM_TOKEN).build()
    setup_handlers(ptb_application_instance)

    ptb_application = ptb_application_instance # تعيين للمتغير العام
    ptb_event_loop = asyncio.new_event_loop() # إنشاء loop جديد لـ PTB

    ptb_thread = Thread(target=run_ptb_thread_target, args=(ptb_application, ptb_event_loop), name="PTBThread")
    ptb_thread.daemon = True
    ptb_thread.start()
    logger.info("PTB thread started.")

    port = int(os.environ.get("PORT", 10000))
    logger.info(f"Starting Flask app on host 0.0.0.0 and port {port}")
    
    try:
      
        flask_app.run(host="0.0.0.0", port=port, debug=False, use_reloader=False)
    except KeyboardInterrupt:
        logger.info("Flask app interrupted by KeyboardInterrupt (from __main__).")
    finally:
        logger.info("Flask app is shutting down (from __main__).")
        if ptb_event_loop and ptb_event_loop.is_running():
            logger.info("Signaling PTB event loop to stop (from __main__).")
            ptb_event_loop.call_soon_threadsafe(ptb_event_loop.stop)
        
        if ptb_thread.is_alive():
            logger.info("Waiting for PTB thread to finish (from __main__)...")
            ptb_thread.join(timeout=10)
            if ptb_thread.is_alive():
                logger.warning("PTB thread did not finish in time (from __main__).")
            else:
                logger.info("PTB thread finished (from __main__).")
        logger.info("Application shutdown sequence complete (from __main__).")
