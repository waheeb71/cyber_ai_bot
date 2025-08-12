import logging
import json
import asyncio
import os
from threading import Thread
from functools import partial

from telegram import Update
from telegram.ext import (
    Application, ApplicationBuilder, CommandHandler, MessageHandler,
    CallbackQueryHandler, filters
)
from flask import Flask, request as flask_request

# --- Local Imports ---
from config import TELEGRAM_TOKEN
from database import Database
from group_handler import GroupHandler
from admin_panel import admin_panel
from handlers.command_handlers import start, clear_messages
from handlers.message_handlers import handle_message, handle_photo
from handlers.callback_handlers import check_subscription_callback, admin_callback_wrapper

# --- Logging Setup ---
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# --- Global Variables & Initialization ---
flask_app = Flask(__name__)
db = Database()

# To be initialized in main
ptb_application: Application = None
main_event_loop: asyncio.AbstractEventLoop = None
WEBHOOK_URL = os.environ.get("RENDER_EXTERNAL_URL")

# --- Flask Webhook Routes ---
@flask_app.route(f"/{TELEGRAM_TOKEN}", methods=["POST"])
def telegram_webhook_sync():
    """Handle webhook updates from Telegram."""
    if not ptb_application or not main_event_loop or not main_event_loop.is_running():
        logger.error("PTB Application or its event loop is not ready for webhook.")
        return "Internal Server Error: Bot not ready", 500

    try:
        update = Update.de_json(flask_request.get_json(force=True), ptb_application.bot)
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
    """A simple route to confirm the bot is alive."""
    return "✅ Bot is alive and webhook is configured!", 200

# --- PTB Handlers Setup ---
def setup_handlers(app: Application):
    """Register all the bot's handlers."""
    # Create handlers with dependencies pre-filled using functools.partial
    start_handler = partial(start, db=db)
    message_handler = partial(handle_message, db=db)
    photo_handler = partial(handle_photo, db=db)
    admin_callback_handler = partial(admin_callback_wrapper, db=db)

    group_handler_instance = GroupHandler(db)

    # Command Handlers
    app.add_handler(CommandHandler("start", start_handler))
    app.add_handler(CommandHandler("admin", admin_panel))
    app.add_handler(CommandHandler("clear", clear_messages))

    # Message Handlers
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND & filters.ChatType.PRIVATE, message_handler))
    app.add_handler(MessageHandler(filters.PHOTO & filters.ChatType.PRIVATE, photo_handler))
    
    # Callback Query Handlers
    app.add_handler(CallbackQueryHandler(check_subscription_callback, pattern="^check_subscription$"))
    app.add_handler(CallbackQueryHandler(admin_callback_handler))

    # Group Handlers
    app.add_handler(CommandHandler('cyber', group_handler_instance.cyber_command))
    app.add_handler(CommandHandler('help', group_handler_instance.help_command))
    app.add_handler(MessageHandler(filters.ChatType.GROUPS, group_handler_instance.handle_message))

    logger.info("All PTB handlers have been added.")

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
                    drop_pending_updates=True
                )
                logger.info(f"Webhook set/updated to {webhook_full_url} successfully!")
            else:
                logger.info(f"Webhook already correctly set to {webhook_full_url}.")
            
            webhook_info = await app_instance.bot.get_webhook_info()
            logger.info(f"Current webhook_info: {webhook_info}")

        except Exception as e:
            logger.error(f"Failed to set webhook: {e}", exc_info=True)
            os._exit(1)
    else:
        logger.warning("WEBHOOK_URL not defined. Webhook not set.")

def run_ptb_thread_target(app_inst: Application, loop: asyncio.AbstractEventLoop):
    global main_event_loop
    main_event_loop = loop
    
    asyncio.set_event_loop(loop)
    try:
        loop.run_until_complete(ptb_async_setup_and_run(app_inst, loop))
        loop.run_forever()
    except KeyboardInterrupt:
        pass
    finally:
        logger.info("PTB event loop is stopping.")
        if loop.is_running():
            loop.run_until_complete(app_inst.shutdown())
        loop.close()

if __name__ == "__main__":
    if not TELEGRAM_TOKEN:
        logger.critical("TELEGRAM_TOKEN is not configured. Bot cannot start.")
    else:
        ptb_application_instance = ApplicationBuilder().token(TELEGRAM_TOKEN).build()
        setup_handlers(ptb_application_instance)

        ptb_application = ptb_application_instance
        ptb_event_loop = asyncio.new_event_loop()

        ptb_thread = Thread(target=run_ptb_thread_target, args=(ptb_application, ptb_event_loop), name="PTBThread")
        ptb_thread.daemon = True
        ptb_thread.start()

        port = int(os.environ.get("PORT", 10000))
        logger.info(f"Starting Flask app on host 0.0.0.0 and port {port}")
        
        try:
            flask_app.run(host="0.0.0.0", port=port, debug=False, use_reloader=False)
        except KeyboardInterrupt:
            logger.info("Flask app interrupted.")
        finally:
            logger.info("Flask app is shutting down.")
            if ptb_event_loop and ptb_event_loop.is_running():
                ptb_event_loop.call_soon_threadsafe(ptb_event_loop.stop)
            ptb_thread.join(timeout=10)
