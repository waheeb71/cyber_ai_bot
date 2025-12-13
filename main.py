import logging
import json
import asyncio
import os
from functools import partial

from threading import Thread
from flask import Flask, request as flask_request
from telegram import Update
from telegram.ext import (
    Application,
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    filters,
    CallbackQueryHandler,
    ContextTypes,
    ChatMemberHandler,
)

# --- Local Imports ---
from src.config import TELEGRAM_TOKEN, WEBHOOK_URL, POSTGRES_URL
from src.database_postgres import Database
from src.handlers import (
    start,
    handle_message,
    handle_photo,
    check_subscription_callback,
    admin_panel,
    handle_admin_callback,
    GroupHandler,
    error_handler,
)

# --- Logging Setup ---
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
logger = logging.getLogger(__name__)

# --- Global Variables & Initialization ---
flask_app = Flask(__name__)
db = Database(POSTGRES_URL)

ptb_application: Application = None
main_event_loop: asyncio.AbstractEventLoop = None


# --- PTB Handlers Setup ---
def setup_handlers(app: Application):
    """Set up all the handlers for the bot."""
    # Create a partial function for handlers that need the db object
    start_handler = partial(start, db=db)
    handle_message_handler = partial(handle_message, db=db)
    handle_photo_handler = partial(handle_photo, db=db)
    check_subscription_handler = partial(check_subscription_callback, db=db)
    admin_callback_handler = partial(handle_admin_callback, db=db)

    group_handler_instance = GroupHandler(db)

    # --- Command Handlers ---
    app.add_handler(CommandHandler("start", start_handler))
    app.add_handler(CommandHandler("admin", admin_panel))

    # --- Message Handlers ---
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND & filters.ChatType.PRIVATE, handle_message_handler))
    app.add_handler(MessageHandler(filters.PHOTO & filters.ChatType.PRIVATE, handle_photo_handler))

    # --- Callback Query Handlers ---
    app.add_handler(CallbackQueryHandler(check_subscription_handler, pattern="^check_subscription$"))
    app.add_handler(CallbackQueryHandler(admin_callback_handler))

    # --- Group Handlers ---
    app.add_handler(CommandHandler('cyber', group_handler_instance.cyber_command))
    app.add_handler(CommandHandler('help', group_handler_instance.help_command))
    app.add_handler(CommandHandler('setprompt', group_handler_instance.set_prompt_command))
    app.add_handler(CommandHandler('resetprompt', group_handler_instance.reset_prompt_command))
    app.add_handler(CommandHandler('getprompt', group_handler_instance.get_prompt_command))
    app.add_handler(ChatMemberHandler(group_handler_instance.handle_my_chat_member, ChatMemberHandler.MY_CHAT_MEMBER))
    app.add_handler(MessageHandler(filters.ChatType.GROUPS & (filters.TEXT | filters.PHOTO) & ~filters.COMMAND, group_handler_instance.handle_message))

    # --- Error Handler ---
    app.add_error_handler(error_handler)

    logger.info("All PTB handlers have been set up.")

# --- Flask Webhook Routes ---
@flask_app.route(f"/{TELEGRAM_TOKEN}", methods=["POST"])
def telegram_webhook_sync():
    """Handle incoming Telegram updates via webhook."""
    if not ptb_application or not main_event_loop or not main_event_loop.is_running():
        logger.error("PTB Application or its event loop is not ready for webhook.")
        return "Internal Server Error: Bot not ready", 500

    try:
        update = Update.de_json(json.loads(flask_request.get_data()), ptb_application.bot)
        asyncio.run_coroutine_threadsafe(ptb_application.process_update(update), main_event_loop)
    except (json.JSONDecodeError, Exception) as e:
        logger.error(f"Error processing update in webhook: {e}", exc_info=True)
        return "Internal Server Error", 500
    return "ok", 200

@flask_app.route("/", methods=["GET"])
def home():
    """A simple route to check if the bot is alive."""
    return "✅ Bot is alive and webhook is configured!", 200

# --- PTB and Flask Execution ---
async def ptb_async_setup_and_run(app: Application, loop: asyncio.AbstractEventLoop):
    """Initialize and set up the PTB application."""
    asyncio.set_event_loop(loop)
    
    await app.initialize()
    logger.info("PTB Application initialized.")

    if WEBHOOK_URL:
        full_webhook_url = f"{WEBHOOK_URL}/{TELEGRAM_TOKEN}"
        try:
            current_webhook = await app.bot.get_webhook_info()
            if not current_webhook or current_webhook.url != full_webhook_url:
                await app.bot.set_webhook(url=full_webhook_url, allowed_updates=Update.ALL_TYPES)
                logger.info(f"Webhook set to {full_webhook_url}")
            else:
                logger.info(f"Webhook already set to {full_webhook_url}")
        except Exception as e:
            logger.error(f"Failed to set webhook: {e}", exc_info=True)
            os._exit(1)
    else:
        logger.warning("WEBHOOK_URL not set. Running in polling mode.")
        await app.run_polling(allowed_updates=Update.ALL_TYPES)

def run_ptb_in_thread(app: Application, loop: asyncio.AbstractEventLoop):
    """Run the PTB application in a separate thread."""
    global main_event_loop
    main_event_loop = loop

    asyncio.set_event_loop(loop)
    try:
        loop.run_until_complete(ptb_async_setup_and_run(app, loop))
        if WEBHOOK_URL:
            loop.run_forever()
    finally:
        if loop.is_running():
            loop.run_until_complete(app.shutdown())
        loop.close()

if __name__ == "__main__":
    # Build the PTB application
    ptb_app = ApplicationBuilder().token(TELEGRAM_TOKEN).build()

    # Set up all handlers
    setup_handlers(ptb_app)

    # Assign to global variable for webhook access
    ptb_application = ptb_app

    # Set up and run PTB in a separate thread
    ptb_event_loop = asyncio.new_event_loop()
    ptb_thread = Thread(target=run_ptb_in_thread, args=(ptb_application, ptb_event_loop), name="PTBThread")
    ptb_thread.daemon = True
    ptb_thread.start()
    logger.info("PTB thread started.")

    # Start the Flask app if using webhooks
    if WEBHOOK_URL:
        port = int(os.environ.get("PORT", 10000))
        logger.info(f"Starting Flask app on port {port}")
        flask_app.run(host="0.0.0.0", port=port, debug=False, use_reloader=False)

    # Clean shutdown
    if ptb_event_loop.is_running():
        ptb_event_loop.call_soon_threadsafe(ptb_event_loop.stop)
    ptb_thread.join()
    
    # Close database connections
    if db:
        db.close()
    
    logger.info("Application shutdown complete.")
