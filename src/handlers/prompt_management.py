import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes

logger = logging.getLogger(__name__)

def get_prompt_keyboard():
    """Get prompt management keyboard."""
    keyboard = [
        [InlineKeyboardButton("👁️ عرض البرومبت الحالي", callback_data="view_prompt")],
        [InlineKeyboardButton("✏️ تعديل البرومبت", callback_data="edit_prompt")],
        [InlineKeyboardButton("🔄 إعادة للافتراضي", callback_data="reset_prompt")],
        [InlineKeyboardButton("🔙 رجوع للقائمة الرئيسية", callback_data="admin_back")]
    ]
    return InlineKeyboardMarkup(keyboard)

# Prompt management functions for admin panel

async def show_prompt_menu(query, db):
    """Show prompt management menu."""
    await query.message.edit_text(
        "⚙️ إدارة البرومبت\nاختر أحد الخيارات:",
        reply_markup=get_prompt_keyboard()
    )

async def view_current_prompt(query, db):
    """View the current active prompt."""
    try:
        prompt_content = db.get_active_prompt()
        
        # Truncate if too long for Telegram message
        if len(prompt_content) > 3500:
            display_prompt = prompt_content[:3500] + "\n\n... (تم قطع الرسالة لطولها)"
        else:
            display_prompt = prompt_content
        
        message = (
            "👁️ البرومبت الحالي:\n\n"
            "━━━━━━━━━━━━━━\n\n"
            f"{display_prompt}\n\n"
            "━━━━━━━━━━━━━━"
        )
        
        await query.message.edit_text(
            message,
            reply_markup=get_prompt_keyboard()
        )
    except Exception as e:
        logger.error(f"Error viewing prompt: {e}")
        await query.message.edit_text(
            "❌ حدث خطأ أثناء عرض البرومبت",
            reply_markup=get_prompt_keyboard()
        )

async def start_edit_prompt(query, context):
    """Start the prompt editing process."""
    context.user_data['admin_state'] = 'waiting_for_new_prompt'
    await query.message.edit_text(
        "✏️ تعديل البرومبت\n\n"
        "قم بإرسال البرومبت الجديد.\n\n"
        "⚠️ ملاحظة: يجب أن يحتوي البرومبت على {user_message} في المكان الذي تريد إدراج رسالة المستخدم فيه.\n\n"
        "مثال:\n"
        "رسالة المستخدم: {user_message}\n"
        "أجب بأسلوب ودود.\n\n"
        "للإلغاء، أرسل /cancel",
        reply_markup=InlineKeyboardMarkup([[
            InlineKeyboardButton("❌ إلغاء", callback_data="manage_prompt")
        ]])
    )

async def handle_new_prompt(update: Update, context: ContextTypes.DEFAULT_TYPE, db):
    """Handle the new prompt from admin."""
    new_prompt = update.message.text
    
    # Validate prompt contains {user_message}
    if "{user_message}" not in new_prompt:
        await update.message.reply_text(
            "❌ البرومبت يجب أن يحتوي على {user_message} للإشارة إلى مكان رسالة المستخدم.\n\n"
            "يرجى إعادة المحاولة.",
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("🔙 رجوع", callback_data="manage_prompt")
            ]])
        )
        return
    
    # Save the new custom prompt
    success = db.update_prompt("custom", new_prompt)
    
    if success:
        await update.message.reply_text(
            "✅ تم تحديث البرومبت بنجاح!\n\n"
            "سيتم استخدام البرومبت الجديد في جميع المحادثات من الآن.",
            reply_markup=get_prompt_keyboard()
        )
    else:
        await update.message.reply_text(
            "❌ فشل تحديث البرومبت. يرجى المحاولة مرة أخرى.",
            reply_markup=get_prompt_keyboard()
        )
    
    context.user_data.clear()

async def reset_to_default_prompt(query, db):
    """Reset prompt to default."""
    success = db.reset_to_default_prompt()
    
    if success:
        await query.message.edit_text(
            "✅ تم إعادة البرومبت إلى الإعداد الافتراضي بنجاح!",
            reply_markup=get_prompt_keyboard()
        )
    else:
        await query.message.edit_text(
            "❌ فشلت إعادة البرومبت للإعداد الافتراضي.",
            reply_markup=get_prompt_keyboard()
        )
