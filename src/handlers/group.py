from telegram import Update
from telegram.ext import ContextTypes
import requests
import re
import html
import time
import asyncio
from datetime import datetime, timedelta
import base64
import io
import logging

from ..config import GEMINI_API_KEY, GEMINI_API_URL, GEMINI_VISION_API_URL, BOT_SIGNATURE
from ..utils.search import search_exa
from ..utils.formatting import format_message, add_signature

logger = logging.getLogger(__name__)

class GroupHandler:
    def __init__(self, database):
        self.db = database
        self.message_history = {}  # Dictionary to store message history for each group
        self.cleanup_task = None

    async def start_cleanup_task(self):
        """بدء مهمة تنظيف الرسائل القديمة"""
        if self.cleanup_task is None:
            self.cleanup_task = asyncio.create_task(self.cleanup_old_messages())

    async def cleanup_old_messages(self):
        """تنظيف الرسائل القديمة كل ساعة"""
        while True:
            try:
                current_time = time.time()
                for chat_id in list(self.message_history.keys()):
                    # حذف الرسائل الأقدم من 24 ساعة
                    messages_to_delete = []
                    for msg_id, msg_data in self.message_history[chat_id].items():
                        if current_time - msg_data['timestamp'] >= 24 * 3600:  # 24 hours in seconds
                            messages_to_delete.append(msg_id)

                    # حذف الرسائل القديمة من القاموس
                    for msg_id in messages_to_delete:
                        del self.message_history[chat_id][msg_id]

                    # حذف المجموعة إذا كانت فارغة
                    if not self.message_history[chat_id]:
                        del self.message_history[chat_id]

            except Exception as e:
                print(f"Error in cleanup task: {str(e)}")


            await asyncio.sleep(3600)  # 1 hour in seconds

    async def handle_my_chat_member(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """التعامل مع تحديثات حالة البوت في المجموعة (إضافة/طرد)"""
        chat = update.effective_chat
        user = update.effective_user
        status_change = update.my_chat_member.new_chat_member.status
        old_status = update.my_chat_member.old_chat_member.status

        # التحقق من أن التحديث في مجموعة
        if chat.type not in ['group', 'supergroup']:
            return

        # البوت تم إضافته للمجموعة
        if status_change in ['member', 'administrator']:
            logger.info(f"Bot added to group: {chat.title} ({chat.id})")
            
            # الحصول على عدد الأعضاء
            members_count = await chat.get_member_count()
            
            # إضافة المجموعة لقاعدة البيانات
            self.db.add_group(chat.id, chat.title, members_count)
            
            # إرسال رسالة ترحيبية إذا كانت إضافة جديدة
            if old_status in ['left', 'kicked']:
                welcome_text = (
                    f"شكراً لإضافتي إلى {chat.title}! 🤖\n\n"
                    "أنا بوت Cyber للذكاء الاصطناعي.\n"
                    "يمكنك التحدث معي عن طريق كتابة 'cyber' ثم سؤالك.\n"
                    "مثال: cyber كيف حالك؟\n\n"
                    "أوامر المشرفين:\n"
                    "/setprompt - تعيين شخصية مخصصة\n"
                    "/resetprompt - استعادة الشخصية الافتراضية"
                )
                await context.bot.send_message(chat_id=chat.id, text=welcome_text)

        # البوت تم طرده أو مغادرته
        elif status_change in ['left', 'kicked']:
            logger.info(f"Bot left group: {chat.title} ({chat.id})")
            # يمكننا هنا تحديث الحالة في قاعدة البيانات إلى غير نشطة إذا أردنا
            # حالياً add_group يقوم بالتحديث فقط، قد نحتاج لدالة لتعطيل المجموعة
            pass



    async def help_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """عرض تعليمات استخدام البوت"""
        help_text = """
 مرحباً بك في بوت Cyber!

الأوامر المتاحة:
• اكتب 'cyber' متبوعاً برسالتك للتحدث مع الذكاء الاصطناعي
• /cyber - للتعرف على البوت
• /help - لعرض هذه التعليمات
• /setprompt - لتعيين برومبت مخصص للمجموعة
• /resetprompt - لإعادة تعيين البرومبت للفاصل
• /getprompt - لعرض البرومبت الحالي

مثال:
cyber ما هو علم الأمن السيبراني؟
"""
        await update.message.reply_text(help_text)

    async def cyber_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """التعريف بالبوت"""
        about_text = """
 مرحباً! أنا بوت Cyber المتخصص في الذكاء الاصطناعي.

يمكنني:
• الإجابة على أسئلتك المتعلقة بالأمن السيبراني
• مساعدتك في فهم المفاهيم التقنية
• التفاعل مع ردودك ومناقشاتك

للبدء، فقط اكتب 'cyber' متبوعاً بسؤالك! 
"""
        await update.message.reply_text(about_text)

    async def set_prompt_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """تعيين برومبت مخصص للمجموعة"""
        chat_id = update.effective_chat.id
        user = update.effective_user
        
        # Check if user is admin
        member = await context.bot.get_chat_member(chat_id, user.id)
        if member.status not in ['administrator', 'creator']:
             await update.message.reply_text("⛔ عذراً، هذا الأمر مخصص للمشرفين فقط.")
             return

        if not context.args:
            await update.message.reply_text("الرجاء كتابة البرومبت الجديد بعد الأمر.\nمثال: /setprompt أنت مساعد متخصص في البرمجة")
            return

        new_prompt = ' '.join(context.args)
        self.db.set_group_prompt(chat_id, new_prompt)
        await update.message.reply_text("✅ تم تعيين البرومبت الجديد للمجموعة بنجاح!")

    async def reset_prompt_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """إعادة تعيين البرومبت للافتراضي"""
        chat_id = update.effective_chat.id
        user = update.effective_user
        
        # Check if user is admin
        member = await context.bot.get_chat_member(chat_id, user.id)
        if member.status not in ['administrator', 'creator']:
             await update.message.reply_text("⛔ عذراً، هذا الأمر مخصص للمشرفين فقط.")
             return

        self.db.reset_group_prompt(chat_id)
        await update.message.reply_text(" تم إعادة تعيين البرومبت إلى الوضع الافتراضي.")

    async def get_prompt_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """عرض البرومبت الحالي"""
        chat_id = update.effective_chat.id
        custom_prompt = self.db.get_group_prompt(chat_id)
        
        if custom_prompt:
            await update.message.reply_text(f"البرومبت الحالي للمجموعة:\n\n{custom_prompt}")
        else:
            default_prompt = self.db.get_prompt_content('default')
            await update.message.reply_text(f" تستخدم المجموعة البرومبت الافتراضي:\n\n{default_prompt}")

    async def handle_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """التعامل مع الرسائل في المجموعات"""
        message = update.message
        chat_id = update.effective_chat.id
        
        if not message:
             return

        # التأكد من تشغيل مهمة التنظيف
        await self.start_cleanup_task()

        # التحقق من أن الرسالة في مجموعة
        if update.effective_chat.type not in ['group', 'supergroup']:
            return

        # تحديث نشاط المجموعة
        try:
            if not self.db.update_group_activity(chat_id):
                # إذا لم تكن المجموعة موجودة، نقوم بإضافتها
                members_count = await update.effective_chat.get_member_count()
                self.db.add_group(chat_id, update.effective_chat.title, members_count)
                # تحديث النشاط مرة أخرى لزيادة عداد الرسائل
                self.db.update_group_activity(chat_id)
        except Exception as e:
            logger.error(f"Error updating group activity: {e}")

        # Context Info
        group_title = update.effective_chat.title
        user_first_name = message.from_user.first_name if message.from_user else "Unknown"
        user_username = message.from_user.username if message.from_user else "Unknown"

        # معالجة الصور (مع أو بدون نص)
        if message.photo:
            try:
                # الحصول على أفضل نسخة من الصورة
                photo = message.photo[-1]
                photo_file = await context.bot.get_file(photo.file_id)

                # تحميل الصورة
                photo_data = await photo_file.download_as_bytearray()

                # تحويل الصورة إلى base64
                base64_image = base64.b64encode(photo_data).decode('utf-8')

                # تحضير النص للتحليل
                caption = None
                if message.caption and 'cyber' in message.caption.lower():
                    # Remove the word 'cyber' and any extra spaces
                    caption = message.caption.lower().replace('cyber', '', 1).strip()

                if caption is not None:
                    # Get prompt
                    custom_prompt = self.db.get_group_prompt(chat_id)
                    system_prompt = custom_prompt if custom_prompt else self.db.get_prompt_content('default')

                    full_prompt = f"""
[System Context]
User: {user_first_name} (@{user_username})
Group: {group_title}

[System Prompt]
{system_prompt}

[User Request]
{caption} (Use emoji appropriately)
"""
                    # تحضير الطلب
                    payload = {
                        "contents": [{
                            "role": "user",
                            "parts": [
                                {"text": full_prompt},
                                {
                                    "inline_data": {
                                        "mime_type": "image/jpeg",
                                        "data": base64_image
                                    }
                                }
                            ]
                        }],
                        "generationConfig": {
                            "temperature": 0.7,
                            "topK": 32,
                            "topP": 1,
                            "maxOutputTokens": 4096,
                        }
                    }

                    # إرسال رسالة انتظار
                    processing_msg = await message.reply_text("🔍 جاري تحليل الصورة...")

                    # إرسال الطلب إلى Gemini Vision API
                    headers = {
                        "Content-Type": "application/json"
                    }

                    response = requests.post(
                        f"{GEMINI_VISION_API_URL}?key={GEMINI_API_KEY}",
                        headers=headers,
                        json=payload
                    )

                    if response.status_code == 200:
                        response_data = response.json()
                        ai_response = response_data.get('candidates', [{}])[0].get('content', {}).get('parts', [{}])[0].get('text', 'عذراً، لم أستطع تحليل الصورة.')

                        # تعديل النص في اي مكان في الرسالة
                        parts = ai_response.split("تم تدريبي بواسطة جوجل")
                        ai_response = "تم تدريبي بواسطة جوجل وتم ربطي في البوت وبرمجتي لاتعامل مع المستخدمين من قبل وهيب الشرعبي".join(parts)

                        # تنسيق النص
                        formatted_response = format_message(ai_response)
                        final_response = add_signature(formatted_response)

                        # إرسال التحليل
                        sent_message = await processing_msg.edit_text(final_response, parse_mode='HTML')

                        # حفظ الرد في التاريخ
                        if chat_id not in self.message_history:
                            self.message_history[chat_id] = {}
                        self.message_history[chat_id][sent_message.message_id] = {
                            'question': f"[صورة] {caption}",
                            'response': final_response,
                            'timestamp': time.time()
                        }
                    else:
                        await processing_msg.edit_text(" عذراً، حدث خطأ في معالجة الصورة. الرجاء المحاولة مرة أخرى.")
                        logger.error(f"API Error: {response.status_code}\n{response.text}")

            except Exception as e:
                await message.reply_text(" عذراً، حدث خطأ أثناء تحليل الصورة. الرجاء المحاولة مرة أخرى.")
                logger.error(f"Error processing image: {str(e)}")
            return

        # التحقق من نوع الرسالة
        if not message.text:
            return
        if message.text == " محادثة جديدة":

         self.message_history[chat_id] = {}  # Clear message history

         await update.message.reply_text(
          f"تم بدء محادثة جديدة.{BOT_SIGNATURE}",

         )
         return

        if message.text == " البحث في الويب":
            await update.message.reply_text("أدخل ما تريد البحث عنه:")
            context.user_data['waiting_for_search_query'] = True
            return
        if context.user_data.get('waiting_for_search_query'):
            await search_exa(update, context)
            context.user_data['waiting_for_search_query'] = False
            return
        # الحالة الأولى: رسالة تبدأ بـ cyber
        if message.text.lower().strip().startswith('cyber'):
            query = message.text.lower().replace('cyber', '', 1).strip()
            if query:
                try:
                    processing_msg = await message.reply_text("🤔 جاري التفكير...")
                    
                    # Get prompt
                    custom_prompt = self.db.get_group_prompt(chat_id)
                    system_prompt = custom_prompt if custom_prompt else self.db.get_prompt_content('default')

                    # Construct context-aware prompt
                    full_prompt = f"""
[System Context]
User: {user_first_name} (@{user_username})
Group: {group_title}

[System Prompt]
{system_prompt}

[User Request]
{query}
"""

                    response = await self.get_ai_response(full_prompt)
                    formatted_response = format_message(response)
                    full_response = f"{formatted_response}\n\n"
                    final_response = add_signature(full_response)
                    sent_message = await processing_msg.edit_text(final_response, parse_mode='HTML')

                    # حفظ الرسالة والسؤال في التاريخ مع الوقت
                    if chat_id not in self.message_history:
                        self.message_history[chat_id] = {}
                    self.message_history[chat_id][sent_message.message_id] = {
                        'question': query,
                        'response': final_response,
                        'timestamp': time.time()
                    }
                except Exception as e:
                    await message.reply_text(" عذراً، حدث خطأ أثناء معالجة طلبك. الرجاء المحاولة مرة أخرى.")
                    logger.error(f"Error handling group message: {e}", exc_info=True)
            else:
                await message.reply_text("👋 مرحباً! يرجى كتابة سؤالك بعد كلمة cyber")
            return

        # الحالة الثانية: رد على رسالة البوت
        if message.reply_to_message and message.reply_to_message.from_user.id == context.bot.id:
            try:
                # استرجاع السياق السابق من التاريخ
                previous_context = ""
                if chat_id in self.message_history and message.reply_to_message.message_id in self.message_history[chat_id]:
                    prev_msg = self.message_history[chat_id][message.reply_to_message.message_id]
                    previous_context = f"السؤال السابق: {prev_msg['question']}\nالإجابة السابقة: {prev_msg['response']}\nالرد الجديد: {message.text}"
                else:
                    previous_context = message.text

                processing_msg = await message.reply_text("🤔 جاري التفكير...")
                
                # Get prompt
                custom_prompt = self.db.get_group_prompt(chat_id)
                system_prompt = custom_prompt if custom_prompt else self.db.get_prompt_content('default')
                
                full_prompt = f"""
[System Context]
User: {user_first_name} (@{user_username})
Group: {group_title}

[System Prompt]
{system_prompt}

[Conversation Context]
{previous_context}
"""

                response = await self.get_ai_response(full_prompt)
                formatted_response = format_message(response)
                full_response = f"{formatted_response}\n\n"
                final_response = add_signature(full_response)
                sent_message = await processing_msg.edit_text(final_response, parse_mode='HTML')

                # حفظ الرد الجديد في التاريخ مع الوقت
                if chat_id not in self.message_history:
                    self.message_history[chat_id] = {}
                self.message_history[chat_id][sent_message.message_id] = {
                    'question': message.text,
                    'response': final_response,
                    'timestamp': time.time()
                }
            except Exception as e:
                await message.reply_text("⚠️ عذراً، حدث خطأ أثناء معالجة ردك. الرجاء المحاولة مرة أخرى.")

    async def broadcast_message(self, context: ContextTypes.DEFAULT_TYPE, message: str):
        """إرسال رسالة إلى جميع المجموعات"""
        groups = self.db.get_all_groups()
        success_count = 0
        fail_count = 0

        for group in groups:
            try:
                await context.bot.send_message(chat_id=group['chat_id'], text=message)
                success_count += 1
            except Exception as e:
                fail_count += 1
                continue

        return success_count, fail_count

    async def get_ai_response(self, text: str) -> str:
        """الحصول على رد من Gemini API"""
        try:
            headers = {
                "Content-Type": "application/json",
            }

            data = {
                "contents": [{
                    "parts": [{
                       "text": text
                    }]
                }]
            }

            response = requests.post(
                f"{GEMINI_API_URL}?key={GEMINI_API_KEY}",
                headers=headers,
                json=data
            )

            if response.status_code == 200:
                response_data = response.json()
                if response_data.get("candidates"):
                    ai_response = response_data["candidates"][0]["content"]["parts"][0]["text"]

                    # تعديل النص في اي مكان في الرسالة
                    parts = ai_response.split("تم تدريبي بواسطة جوجل")
                    ai_response = "تم تدريبي بواسطة جوجل وتم ربطي في البوت وبرمجتي لاتعامل مع المستخدمين من قبل وهيب الشرعبي".join(parts)

                    return ai_response
            return "عذراً، لم أستطع فهم طلبك. هل يمكنك إعادة صياغة السؤال؟"
        except Exception as e:
            raise Exception("حدث خطأ في الاتصال مع Gemini API")

    async def get_image_analysis(self, image_data: bytes, text: str) -> str:
        """تحليل الصورة باستخدام Gemini Vision API"""
        # ... (Existing logic, but we might want to update prompt logic here too if needed, but the main handle_message covers the primary image flow)
        # Note: The main logic for group images seems to be inside handle_message, so this method might be unused or secondary.
        # I will keep it as is for now to avoid breaking other flows, but handle_message handles the group image flow directly.
        try:
            # تحويل الصورة إلى Base64
            image_base64 = base64.b64encode(image_data).decode('utf-8')

            headers = {
                "Content-Type": "application/json",
            }

            data = {
                "contents": [{
                    "parts": [
                        {
                            "text": f"{text} (استخدم ايموجي تفاعلي مناسب مع كل فكرة في الرد)"
                        },
                        {
                            "inline_data": {
                                "mime_type": "image/jpeg",
                                "data": image_base64
                            }
                        }
                    ]
                }]
            }

            response = requests.post(
                f"{GEMINI_VISION_API_URL}?key={GEMINI_API_KEY}",
                headers=headers,
                json=data
            )

            if response.status_code == 200:
                response_data = response.json()
                if response_data.get("candidates"):
                    return response_data["candidates"][0]["content"]["parts"][0]["text"]
            return "عذراً، لم أستطع تحليل الصورة. هل يمكنك المحاولة مرة أخرى؟"
        except Exception as e:
            raise Exception(f"حدث خطأ في تحليل الصورة: {str(e)}")

    async def get_image_from_url(self, url: str) -> bytes:
        """تحميل الصورة من عنوان URL"""
        try:
            response = requests.get(url)
            return response.content
        except Exception as e:
            raise Exception(f"حدث خطأ في تحميل الصورة: {str(e)}")
