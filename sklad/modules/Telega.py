import telebot
from telebot import apihelper
import os
import time
import config

TOKEN = config.TG_TOKEN
CHAT_ID = config.TG_CHAT_ID

def get_proxies_from_file():
    proxies_list = []
    proxy_path = os.path.join(config.DATA_DIR, "proxies.txt")
    if not os.path.exists(proxy_path):
        return [None]
    with open(proxy_path, "r") as f:
        for line in f:
            line = line.strip()
            if not line: continue
            parts = line.split(':')
            if len(parts) == 4:
                ip, port, user, pw = parts
                proxies_list.append(f'http://{user}:{pw}@{ip}:{port}')
    return proxies_list if proxies_list else [None]

def send_text_message(text):
    """Отправка простого текстового сообщения"""
    proxies = get_proxies_from_file()
    for proxy in proxies:
        try:
            if proxy: apihelper.proxy = {'https': proxy}
            bot = telebot.TeleBot(TOKEN)
            bot.send_message(CHAT_ID, text, parse_mode='Markdown')
            print("[🚀] Текстовое уведомление отправлено!")
            return True
        except Exception as e:
            print(f"[!] Ошибка отправки текста: {e}")
            continue
    return False

def send_report(filename, caption_text=None):
    proxies = get_proxies_from_file()
    for proxy in proxies:
        try:
            if proxy: apihelper.proxy = {'https': proxy}
            bot = telebot.TeleBot(TOKEN)
            
            if os.path.exists(filename):
                with open(filename, 'rb') as f:
                    bot.send_document(
                        CHAT_ID, 
                        f, 
                        caption=caption_text, # Здесь будет наш короткий текст
                        parse_mode='Markdown',
                        timeout=40
                    )
                print(f"[🚀] Отчет отправлен!")
                return True
        except Exception as e:
            print(f"[!] Ошибка: {e}")
            continue
    return False