import os
from dotenv import load_dotenv
import logging

# Load environment variables from .env file
load_dotenv()

# --- Logging Setup ---
logger = logging.getLogger(__name__)

# --- Telegram Configuration ---
TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN")
if not TELEGRAM_TOKEN:
    logger.critical("TELEGRAM_TOKEN is not set. Please check your .env file or environment variables.")
    exit(1)

# --- API Keys ---
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY") # Optional

if not GEMINI_API_KEY:
    logger.warning("GEMINI_API_KEY is not set. AI features will be limited.")

# --- Gemini API Configuration ---

GEMINI_API_URL = "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent"
GEMINI_VISION_API_URL = "https://generativelanguage.googleapis.com/v1beta/models/gemini-pro-vision:generateContent"
# --- Firebase Configuration ---
SERVICE_ACCOUNT_FILE = os.environ.get("SERVICE_ACCOUNT_FILE", "serviceAccountKey.json")
FIREBASE_DB_URL = os.environ.get("FIREBASE_DB_URL")

if not FIREBASE_DB_URL:
    logger.warning("FIREBASE_DB_URL is not set. Database features will not work.")

# --- Admin Configuration ---
ADMIN_USERS_STR = os.environ.get("ADMIN_USERS", "")
ADMIN_USERS = [user.strip() for user in ADMIN_USERS_STR.split(',') if user.strip()]
ADMIN_NOTIFICATION_ID_STR = os.environ.get("ADMIN_NOTIFICATION_ID")
ADMIN_NOTIFICATION_ID = int(ADMIN_NOTIFICATION_ID_STR) if ADMIN_NOTIFICATION_ID_STR and ADMIN_NOTIFICATION_ID_STR.isdigit() else None

if not ADMIN_USERS:
    logger.warning("ADMIN_USERS list is not set.")
if not ADMIN_NOTIFICATION_ID:
    logger.warning("ADMIN_NOTIFICATION_ID is not set. Admin notifications will not be sent.")

# --- Bot Customization ---
BOT_SIGNATURE = "\n\n━━━━━━━━━━━━━━\n📢 قناة التلجرام: @SyberSc71\n👨‍💻 برمجة:  @WAT4F"
PROMPT_PREFIX = """\
ملاحظة مرفقة مع الرسالة: كن إنسانيًا في تواصلك مع المستخدمين،
وتحدث بأسلوب طبيعي يشعرهم بالود والحب. اجعل ردودك محببة وتصرفاتك مميزة.
لا تذكر اسمي إلا إذا طُلب منك ذلك.
اسمك على تليجرام هو ابو راس ، وتم ربطك عبر بوت تليجرام من قِبل وهيب الشرعبي من اليمن.
تذكّر أن جنسيتك يمنية.
وفي حال طُلب منك تقديم معلومة، كن عاقلًا وواقعيًا في ردك.
استخدم الإيموجيات التفاعلية لجعل تواصلك أكثر مرحًا وجاذبية 😊✨.
مهم :لو سالك حد عن غيابك قل له  ضروف مادية مادفعت لسيرفر حقة
"""
