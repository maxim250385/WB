# Sklad — мониторинг остатков WB

Скрипт парсит данные об остатках товаров на Wildberries и отправляет отчёт в Telegram и на email.

## Технологии

- Python 3.11+
- Telegram Bot API (pyTelegramBotAPI)
- SMTP / Яндекс Почта
- pandas, XlsxWriter

## Установка

```bash
pip install -r requirements.txt
```

## Настройка

1. Скопируй `.env.example` в `.env`:
   ```bash
   cp .env.example .env
   ```

2. Заполни `.env` своими данными:
   ```
   TG_TOKEN=       # токен от @BotFather
   TG_CHAT_ID=     # твой числовой chat_id
   EMAIL_SENDER=   # логин Яндекс-почты
   EMAIL_PASSWORD= # пароль приложения (16 символов, не основной пароль)
   ```

   > Пароль приложения Яндекса: Настройки → Безопасность → Пароли приложений

## Запуск

```bash
python main.py
```
