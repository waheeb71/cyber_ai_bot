import html
import re
from telegram import (
    Update, InlineKeyboardButton, InlineKeyboardMarkup,
    ReplyKeyboardMarkup, KeyboardButton
)
from telegram.ext import ContextTypes

async def check_subscription(user_id: int, context: ContextTypes.DEFAULT_TYPE) -> bool:
    """Check if user is subscribed to the channel."""
    try:
        # It's better to get the channel name from config
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
        # Check if update.message exists before replying
        if update.message:
            await update.message.reply_text(
                "عذراً! يجب عليك الاشتراك في قناتنا أولاً للاستمرار.\n"
                "اشترك ثم اضغط على زر التحقق 👇 أو اضغط /start",
                reply_markup=keyboard
            )
        return False
    return True

def get_base_keyboard():
    """Returns the main reply keyboard."""
    keyboard = [
        [KeyboardButton("🔄 محادثة جديدة")],
        [KeyboardButton("🔍 البحث في الويب")],
        [KeyboardButton("🔗 فحص الروابط")],
    ]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

def format_text(text: str) -> str:
    """Format mixed text (Arabic/English) for better readability with HTML support."""
    parts = []
    current_part = []
    in_code_block = False

    for line in text.split('\n'):
        if line.strip().startswith('```'):
            if in_code_block:
                current_part.append(line)
                parts.append('\n'.join(current_part))
                current_part = []
                in_code_block = False
            else:
                if current_part:
                    parts.append('\n'.join(current_part))
                    current_part = []
                current_part.append(line)
                in_code_block = True
        else:
            current_part.append(line)

    if current_part:
        parts.append('\n'.join(current_part))

    formatted_parts = []
    for part in parts:
        if part.strip().startswith('```'):
            code_content = part.replace('```python', '').replace('```', '').strip()
            formatted_parts.append(f'<pre><code>{html.escape(code_content)}</code></pre>')
        else:
            lines = part.split('\n')
            formatted_lines = []
            for line in lines:
                if not line.strip():
                    formatted_lines.append(line)
                    continue
                line = re.sub(r'`([^`]+)`', lambda m: f'<code>{html.escape(m.group(1))}</code>', line)
                line = re.sub(r'\*\*(.+?)\*\*', r'<b>\1</b>', line)
                line = re.sub(r'__(.+?)__', r'<b>\1</b>', line)
                line = re.sub(r'\*(.+?)\*', r'<i>\1</i>', line)
                line = re.sub(r'_(.+?)_', r'<i>\1</i>', line)
                if line.strip().startswith(('•', '-', '*')):
                    line = f'• {line.strip().lstrip("•-* ")}'
                formatted_lines.append(line)
            formatted_parts.append('\n'.join(formatted_lines))

    final_text = '\n\n'.join(part for part in formatted_parts if part.strip())
    return final_text
