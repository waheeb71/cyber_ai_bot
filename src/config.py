import os
import logging

logger = logging.getLogger(__name__)

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

# PostgreSQL Database URL
POSTGRES_URL = os.getenv("POSTGRES_URL")

if not POSTGRES_URL:
    logger.warning("POSTGRES_URL not found in environment variables. Database will not function properly.")


# Admin Notification ID - try to get from env, otherwise use fallback
admin_notification_id_env = os.getenv("ADMIN_NOTIFICATION_ID")
if admin_notification_id_env:
    ADMIN_NOTIFICATION_ID = int(admin_notification_id_env)
else:
    ADMIN_NOTIFICATION_ID = 5887234832  # Fallback ID
    logger.warning(f"ADMIN_NOTIFICATION_ID not found in environment variables. Using fallback value: {ADMIN_NOTIFICATION_ID}")

ADMIN_USERS = ["WAT4F", "M984D", "A66S6", "HTTHT"]


GEMINI_API_URL = "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent"
GEMINI_VISION_API_URL = "https://generativelanguage.googleapis.com/v1beta/models/gemini-pro-vision:generateContent"
# Bot signature
BOT_SIGNATURE = "\n\n━━━━━━━━━━━━━━\n📢 قناة التلجرام: @SyberSc71\n👨‍💻 برمجة:  @WAT4F"

# Webhook URL for Render deployment
WEBHOOK_URL = os.environ.get("RENDER_EXTERNAL_URL")
