# WB Sklad

Скрипт для сбора отчётов об остатках товаров на Wildberries и отправки их в Telegram и на email.

## Что делает

- Читает список артикулов из `Data/articles.txt`
- Собирает данные об остатках с WB
- Формирует Excel-отчёт (сводка + остатки по складам)
- Отправляет отчёт в Telegram и/или на email

## Установка

```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

## Настройка

Скопируй `.env.example` в `.env` и заполни значения:

```bash
cp .env.example .env
nano .env
```

Переменные:
- `TG_TOKEN` — токен Telegram-бота
- `TG_CHAT_ID` — ID чата для отправки отчёта
- `EMAIL_SENDER` — адрес отправителя (Яндекс)
- `EMAIL_PASSWORD` — пароль приложения Яндекс (16 символов)

Дополнительные файлы в папке `Data/`:
- `articles.txt` — артикулы WB, по одному на строку
- `emails.txt` — список адресов для рассылки (опционально)
- `proxies.txt` — прокси в формате `ip:port:user:password` (опционально)

## Запуск

```bash
source venv/bin/activate
python main.py
```
