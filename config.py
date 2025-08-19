
import os
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
SERVICE_ACCOUNT_FILE = os.getenv("SERVICE_ACCOUNT_FILE")
FIREBASE_DB_URL = os.getenv("FIREBASE_DB_URL")
ADMIN_NOTIFICATION_ID = int(os.getenv("ADMIN_NOTIFICATION_ID"))
ADMIN_USERS = ["WAT4F", "M984D", "A66S6", "HTTHT"]
ADMIN_NOTIFICATION_ID = 5887234832  # Replace with your actual numeric ID

GEMINI_API_URL = "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent"
GEMINI_VISION_API_URL = "https://generativelanguage.googleapis.com/v1beta/models/gemini-pro-vision:generateContent"

# Bot signature
BOT_SIGNATURE = "\n\n━━━━━━━━━━━━━━\n📢 قناة التلجرام: @SyberSc71\n👨‍💻 برمجة:  @WAT4F"



