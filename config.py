import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

BASE_DIR = Path(__file__).parent
DATA_DIR = BASE_DIR / "data"
DATA_DIR.mkdir(exist_ok=True)

DB_PATH = DATA_DIR / "bot.db"
SESSION_PATH = DATA_DIR / "userbot"

API_ID = int(os.getenv("API_ID", "0"))
API_HASH = os.getenv("API_HASH", "")
PHONE = os.getenv("PHONE", "")

ADMIN_BOT_TOKEN = os.getenv("ADMIN_BOT_TOKEN", "")
ADMIN_TELEGRAM_ID = int(os.getenv("ADMIN_TELEGRAM_ID", "0"))

TIMEZONE = os.getenv("TIMEZONE", "Asia/Tashkent")

SEND_DELAY_SECONDS = 3

DEFAULT_MESSAGE = "Salom {ism}, bugungi hisobotingizni yuboring 🙏"
DEFAULT_TIME = "17:00"
DEFAULT_WORKDAYS = "mon,tue,wed,thu,fri"


def validate():
    missing = []
    if not API_ID:
        missing.append("API_ID")
    if not API_HASH:
        missing.append("API_HASH")
    if not PHONE:
        missing.append("PHONE")
    if not ADMIN_BOT_TOKEN:
        missing.append("ADMIN_BOT_TOKEN")
    if not ADMIN_TELEGRAM_ID:
        missing.append("ADMIN_TELEGRAM_ID")
    if missing:
        raise RuntimeError(
            f".env faylida quyidagilar yo'q yoki bo'sh: {', '.join(missing)}"
        )
