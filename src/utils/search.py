import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, CallbackQueryHandler

from exa_py import Exa


EXA_API_KEY = "f0436406-9a26-4c46-abf7-8db007467703"

exa = Exa(api_key=EXA_API_KEY)


async def search_exa(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.message.text
    searching_message = f"🔍 | جارِ البحث عن: *{query}* ..."
    await update.message.reply_text(searching_message, parse_mode="Markdown")

    try:
        result = exa.search_and_contents(query, text={"max_characters": 500})

        if hasattr(result, "results") and result.results:
            # إنشاء رسالة مجمعة للنتائج
            response = " إليك النتائج:\n\n"
            
            for doc in result.results[:5]:
                title = doc.title if hasattr(doc, "title") else "عنوان غير متوفر ❓"
                url = doc.url if hasattr(doc, "url") else "رابط غير متوفر 🔗"
                text = doc.text if hasattr(doc, "text") else "لا يوجد ملخص 📝"
                
              
                summary = f"{text[:600]}..." if len(text) > 600 else text
                read_more = f"\n[📖 اقرأ المزيد]({url})" if url else ""
                
                response += (
                    f"\n{'─'*20}\n"
                    f"📌 *{title}*\n"
                    f"🔗 {url}\n"
                    f"📝 {summary}{read_more}"
                )
            
       
            response += (
                f"\n\n{'─'*20}\n"
                f"📢 قناة التلجرام: @SyberSc71 | 👨‍💻 المطور: @WAT4F"
            )
            
            # إرسال النتائج المجمعة
            await update.message.reply_text(
                response,
                parse_mode="Markdown",
                disable_web_page_preview=True
            )
            
            # إشعار إضافي
            await update.message.reply_text(
                "💡 هل تريد نتائج أكثر؟ يمكنك تحسين البحث باستخدام كلمات مفتاحية أدق!",
                parse_mode="Markdown"
            )
            
        else:
            await update.message.reply_text(" عذراً، لا توجد نتائج لبحثك. حاول صياغة سؤال مختلف.")

    except Exception as e:
        logging.error(f"שגיאת חיפוש: {e}")
        await update.message.reply_text(" حدث خطأ تقني، يرجى المحاولة لاحقاً.")
