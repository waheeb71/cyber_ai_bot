from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, Message
from telegram.ext import ContextTypes
from telegram.constants import ParseMode
from telegram.error import TelegramError, Forbidden
import logging
import asyncio
from datetime import datetime

logger = logging.getLogger(__name__)

# States
WAITING_MESSAGE = "waiting_broadcast_message"
CONFIRM_BROADCAST = "confirm_broadcast"

def get_broadcast_keyboard(pin: bool = False, silent: bool = False):
    """Get broadcast control keyboard."""
    pin_status = "✅" if pin else "❌"
    silent_status = "✅" if silent else "❌"
    
    keyboard = [
        [InlineKeyboardButton("📨 إرسال للكل", callback_data="broadcast_send"),
         InlineKeyboardButton("🧪 تجربة لي", callback_data="broadcast_test")],
        [InlineKeyboardButton(f"تثبيت {pin_status}", callback_data="broadcast_toggle_pin"),
         InlineKeyboardButton(f"بدون صوت {silent_status}", callback_data="broadcast_toggle_silent")],
        [InlineKeyboardButton("❌ إلغاء", callback_data="broadcast_cancel")]
    ]
    return InlineKeyboardMarkup(keyboard)

async def start_broadcast(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Start the broadcast process."""
    if update.callback_query:
        await update.callback_query.answer()
        message = update.callback_query.message
    else:
        message = update.message

    context.user_data['broadcast_state'] = WAITING_MESSAGE
    # Reset options
    context.user_data['broadcast_pin'] = False
    context.user_data['broadcast_silent'] = False
    
    text = (
        "📢 *نظام الإذاعة المتطور*\n\n"
        "أرسل الرسالة التي تريد نشرها (نص، صورة، فيديو، ملف...).\n"
        "يمكنك استخدام تنسيق Markdown.\n\n"
        "💡 *ميزات متوفرة:*\n"
        "• دعم جميع أنواع الوسائط\n"
        "• إضافة أزرار شفاف (أضف في نهاية النص: `نص الزر | الرابط`)\n"
        "• تثبيت الرسالة (اختياري)\n"
        "• إرسال صامت (اختياري)\n\n"
        "لإلغاء العملية أرسل /cancel"
    )
    
    if update.callback_query:
        await message.edit_text(text, parse_mode=ParseMode.MARKDOWN)
    else:
        await message.reply_text(text, parse_mode=ParseMode.MARKDOWN)

async def handle_broadcast_input(update: Update, context: ContextTypes.DEFAULT_TYPE, db):
    """Handle the message input for broadcast."""
    if context.user_data.get('broadcast_state') != WAITING_MESSAGE:
        return

    message = update.message
    context.user_data['broadcast_message_obj'] = message
    context.user_data['broadcast_state'] = CONFIRM_BROADCAST

    # Create preview of buttons if any
    buttons = parse_buttons(message.caption or message.text or "")
    
    preview_text = "✅ *تم استلام الرسالة*\n\nاختر خيارات الإرسال من الأسفل:"
    
    await message.reply_text(
        preview_text,
        reply_markup=get_broadcast_keyboard(),
        parse_mode=ParseMode.MARKDOWN
    )

async def handle_broadcast_callback(update: Update, context: ContextTypes.DEFAULT_TYPE, db):
    """Handle broadcast button interactions."""
    query = update.callback_query
    data = query.data
    
    if not data.startswith("broadcast_"):
        return

    await query.answer()
    
    state = context.user_data.get('broadcast_state')
    if state != CONFIRM_BROADCAST and data != "broadcast_cancel":
        await query.message.edit_text("⚠️ انتهت جلسة الإذاعة. حاول مرة أخرى.")
        return

    if data == "broadcast_cancel":
        context.user_data.clear()
        await query.message.edit_text("❌ تم إلغاء الإذاعة.")
        return

    elif data == "broadcast_toggle_pin":
        context.user_data['broadcast_pin'] = not context.user_data.get('broadcast_pin', False)
        await query.message.edit_reply_markup(
            reply_markup=get_broadcast_keyboard(
                context.user_data['broadcast_pin'],
                context.user_data.get('broadcast_silent', False)
            )
        )

    elif data == "broadcast_toggle_silent":
        context.user_data['broadcast_silent'] = not context.user_data.get('broadcast_silent', False)
        await query.message.edit_reply_markup(
            reply_markup=get_broadcast_keyboard(
                context.user_data.get('broadcast_pin', False),
                context.user_data['broadcast_silent']
            )
        )

    elif data == "broadcast_test":
        await send_broadcast_message(
            context, 
            update.effective_user.id, 
            context.user_data['broadcast_message_obj'],
            pin=context.user_data.get('broadcast_pin', False),
            silent=context.user_data.get('broadcast_silent', False)
        )
        await query.message.reply_text("✅ تم إرسال نسخة تجريبية إليك.")

    elif data == "broadcast_send":
        await query.message.edit_text("⏳ جاري بدء الإذاعة... الرجاء الانتظار.")
        
        # Use existing method or fix the attribute error here
        # FIX: The error was db.data["users"]. keys() on Postgres DB
        try:
            users = db.get_all_user_ids_for_broadcast()
        except Exception as e:
            logger.error(f"DB Error getting users: {e}")
            await query.message.edit_text(f"❌ خطأ في قاعدة البيانات: {str(e)}")
            return

        total = len(users)
        success = 0
        failed = 0
        
        msg_obj = context.user_data['broadcast_message_obj']
        pin = context.user_data.get('broadcast_pin', False)
        silent = context.user_data.get('broadcast_silent', False)
        
        progress_msg = await query.message.reply_text(f"📊 جاري الإرسال... 0/{total}")
        
        for i, user_id in enumerate(users):
            if i % 20 == 0:  # Update progress every 20 users
                try:
                    await progress_msg.edit_text(f"📊 جاري الإرسال... {i}/{total}\n✅ نجح: {success}\n❌ فشل: {failed}")
                except:
                    pass
            
            if await send_broadcast_message(context, int(user_id), msg_obj, pin, silent):
                success += 1
            else:
                failed += 1
            
            await asyncio.sleep(0.05)  # Flood limit protection

        await progress_msg.edit_text(
            f"✅ *تمت الإذاعة بنجاح*\n\n"
            f"👥 المستهدفين: {total}\n"
            f"✅ وصل: {success}\n"
            f"❌ لم يصل: {failed}",
            parse_mode=ParseMode.MARKDOWN
        )
        context.user_data.clear()

async def send_broadcast_message(context, chat_id, message_obj, pin, silent):
    """Refined send logic with support for all media types and buttons."""
    try:
        # Extract buttons
        caption = message_obj.caption or ""
        text = message_obj.text or ""
        content_text = caption if caption else text
        
        buttons, clean_text = extract_buttons(content_text)
        
        # If we extracted buttons, we need to replace the text/caption
        kwargs = {
            'chat_id': chat_id,
            'disable_notification': silent,
            'reply_markup': buttons
        }

        sent_msg = None
        
        if message_obj.text:
            sent_msg = await context.bot.send_message(
                text=clean_text, 
                parse_mode=ParseMode.MARKDOWN,
                disable_web_page_preview=True,
                **kwargs
            )
        elif message_obj.photo:
            sent_msg = await context.bot.send_photo(
                photo=message_obj.photo[-1].file_id,
                caption=clean_text,
                parse_mode=ParseMode.MARKDOWN,
                **kwargs
            )
        elif message_obj.video:
            sent_msg = await context.bot.send_video(
                video=message_obj.video.file_id,
                caption=clean_text,
                parse_mode=ParseMode.MARKDOWN,
                **kwargs
            )
        elif message_obj.document:
            sent_msg = await context.bot.send_document(
                document=message_obj.document.file_id,
                caption=clean_text,
                parse_mode=ParseMode.MARKDOWN,
                **kwargs
            )
        elif message_obj.voice:
             sent_msg = await context.bot.send_voice(
                voice=message_obj.voice.file_id,
                caption=clean_text,
                parse_mode=ParseMode.MARKDOWN,
                **kwargs
            )
        elif message_obj.audio:
             sent_msg = await context.bot.send_audio(
                audio=message_obj.audio.file_id,
                caption=clean_text,
                parse_mode=ParseMode.MARKDOWN,
                **kwargs
            )
        elif message_obj.sticker:
             sent_msg = await context.bot.send_sticker(
                sticker=message_obj.sticker.file_id,
                disable_notification=silent,
                reply_markup=buttons
            )
        else:
            # Fallback for other types
            sent_msg = await message_obj.copy(
                chat_id=chat_id,
                disable_notification=silent,
                reply_markup=buttons,
                caption=clean_text if (message_obj.caption is not None) else None
            )

        if pin and sent_msg:
            try:
                await sent_msg.pin(disable_notification=silent)
            except:
                pass
                
        return True

    except Forbidden:
        # User blocked bot
        return False
    except TelegramError as e:
        logger.warning(f"Broadcast failed for {chat_id}: {e}")
        return False

def extract_buttons(text_content):
    """Extract buttons defined as 'Text | URL' from the end of the text."""
    if not text_content:
        return None, ""
        
    lines = text_content.split('\n')
    button_lines = []
    content_lines = []
    
    for line in lines:
        if '|' in line and not line.startswith('http'): # Simple heuristic
             # Maybe check if it looks like a button definition
             parts = line.split('|')
             if len(parts) == 2 and 'http' in parts[1]:
                 button_lines.append(line)
             else:
                 content_lines.append(line)
        else:
            content_lines.append(line)
            
    keyboard = []
    for line in button_lines:
        try:
            text, url = line.split('|')
            keyboard.append([InlineKeyboardButton(text.strip(), url=url.strip())])
        except:
            pass
            
    # Reassemble content
    clean_text = '\n'.join(content_lines).strip()
    reply_markup = InlineKeyboardMarkup(keyboard) if keyboard else None
    
    return reply_markup, clean_text

def parse_buttons(text):
    """Helper to just parse buttons for preview."""
    btns, _ = extract_buttons(text)
    return btns
