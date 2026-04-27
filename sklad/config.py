import os
from dotenv import load_dotenv

load_dotenv()

# --- НАСТРОЙКИ УВЕДОМЛЕНИЙ ---
SEND_TELEGRAM = True
SEND_EMAIL = True
SEND_EXCEL_FILE = True

# --- Telegram ---
TG_TOKEN = os.getenv("TG_TOKEN")
TG_CHAT_ID = int(os.getenv("TG_CHAT_ID", "0"))

# --- Email (Yandex) ---
SMTP_SERVER = "smtp.yandex.ru"
SMTP_PORT = 465
EMAIL_SENDER = os.getenv("EMAIL_SENDER")
EMAIL_PASSWORD = os.getenv("EMAIL_PASSWORD")

# --- Папки ---
DATA_DIR = "Data"
EXCEL_DIR = "Excel"

for d in [DATA_DIR, EXCEL_DIR]:
    if not os.path.exists(d): 
        os.makedirs(d)