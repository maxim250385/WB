import os

# --- НАСТРОЙКИ УВЕДОМЛЕНИЙ ---
SEND_TELEGRAM = True       # Оставляем Телегу
SEND_EMAIL = True          # Добавляем Почту
SEND_EXCEL_FILE = True     # Отправлять файл в обоих случаях

# --- Telegram ---
TG_TOKEN = ''
TG_CHAT_ID = 

# --- Email (Yandex) ---
SMTP_SERVER = "smtp.yandex.ru"
SMTP_PORT = 465
EMAIL_SENDER = ""    # Ваш логин
EMAIL_PASSWORD = ""     # 16 символов от Яндекса

# --- Папки ---
DATA_DIR = "Data"
EXCEL_DIR = "Excel"

for d in [DATA_DIR, EXCEL_DIR]:
    if not os.path.exists(d): 
        os.makedirs(d)