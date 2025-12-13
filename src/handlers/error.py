import logging
import html
import json
import traceback

from telegram import Update
from telegram.constants import ParseMode
from telegram.ext import ContextTypes

logger = logging.getLogger(__name__)

async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Log the error and send a telegram message to notify the developer."""
    # Log the error before we do anything else, so we can see it even if something breaks.
    logger.error("Exception while handling an update:", exc_info=context.error)

    # traceback.format_exception returns the usual python message with an exception, but as a
    # list of strings each ending in a newline and some containing newlines.
    tb_list = traceback.format_exception(None, context.error, context.error.__traceback__)
    tb_string = "".join(tb_list)

    # Build the message with some markup and additional information about what happened.
    # You might need to add some logic to deal with messages longer than the 4096 character limit.
    update_str = update.to_dict() if isinstance(update, Update) else str(update)
    message = (
        f"An exception was raised while handling an update\n"
        f"<pre>update = {html.escape(json.dumps(update_str, indent=2, ensure_ascii=False))}"
        "</pre>\n\n"
        f"<pre>context.chat_data = {html.escape(str(context.chat_data))}</pre>\n\n"
        f"<pre>context.user_data = {html.escape(str(context.user_data))}</pre>\n\n"
        f"<pre>{html.escape(tb_string)}</pre>"
    )

    # Finally, send the message
    try:
        # Send to the user who triggered the error if possible
        if isinstance(update, Update) and update.effective_message:
            await update.effective_message.reply_text(
                "عذراً، حدث خطأ غير متوقع أثناء معالجة طلبك.",
                parse_mode=ParseMode.HTML
            )
            
            # Send full details to developer/admin if configured (optional)
            # You would need an ADMIN_ID constant for this.
            # await context.bot.send_message(chat_id=ADMIN_ID, text=message, parse_mode=ParseMode.HTML)
            
    except Exception as e:
        logger.error(f"Failed to send error notification: {e}")
