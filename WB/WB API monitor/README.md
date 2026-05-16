# WB API Monitor

Мониторит Telegram-канал `@wb_api_notifications` и автоматически обновляет документацию WB API при выходе изменений.

## Что делает

1. Подключается к Telegram через Telethon (MTProto прокси через локальный relay → ProxyLine SOCKS5)
2. Слушает новые сообщения в канале
3. При каждом новом сообщении:
   - Определяет нужный YAML-файл по хэштегам (`#items`, `#fbs` и т.д.)
   - Извлекает русскую часть текста (обрезает английский перевод и футер)
   - Находит упомянутые API endpoints
   - Отправляет в Gemini: текст изменения + раздел YAML
   - Gemini возвращает JSON с заменами → применяет в YAML
   - Уведомляет в Telegram

## Структура

```
WB API monitor/
├── main.py                    ← Точка входа: relay-серверы, два режима работы
├── config.py                  ← Настройки: WORK_MODE, канал, сессия, часы проверки
├── requirements.txt
├── data/
│   ├── .env                   ← Секреты (не коммитить)
│   ├── .env.example           ← Шаблон
│   ├── proxies.txt            ← HTTP прокси ip:port — для Bot API и Gemini
│   └── mtproto_proxies.txt    ← MTProto прокси server:port:secret — для Telethon
└── modules/
    ├── telegram_bot.py        ← Telegram бот: /start, кнопка OK, notify()
    ├── message_parser.py      ← Парсинг: хэштеги, русский текст, endpoints
    ├── gemini_client.py       ← Gemini API: ключи, модели, прокси
    ├── yaml_updater.py        ← Обновление YAML, маппинг хэштегов, pending-изменения
    └── notifier.py            ← Re-export из telegram_bot.notify
```

## Установка

```bash
cd "WB/WB API monitor"
python -m venv env
env\Scripts\pip install -r requirements.txt
```

## Настройка

Скопировать `data/.env.example` → `data/.env` и заполнить:

```
TG_PHONE=+7XXXXXXXXXX        # номер телефона для Telethon
TG_BOT_TOKEN=                # токен от @BotFather
TG_NOTIFY_CHAT_ID=           # ваш Telegram user ID
PROXY_USER=                  # логин ProxyLine
PROXY_PASS=                  # пароль ProxyLine
GEMINI_KEY_1=                # ключи Gemini API (до 8 штук: GEMINI_KEY_1 ... GEMINI_KEY_8)
```

**`data/proxies.txt`** — HTTP прокси, по одному `ip:port` на строку (credentials в .env).

**`data/mtproto_proxies.txt`** — MTProto прокси с `dd`-секретом, формат `server:port:secret` или ссылка `t.me/proxy?...`. `ee`-секреты не поддерживаются (Telethon 1.36.0).

## Первый запуск (авторизация)

При первом запуске Telethon отправит код в Telegram-приложение на телефоне. Запускать **интерактивно**:

```bash
env\Scripts\python main.py
```

После ввода кода (и пароля 2FA если включён) создаётся `wb_monitor_session.session` — последующие запуски не требуют кода.

## Режимы работы

Задаётся в `config.py`, поле `WORK_MODE`:

| Режим | Что делает |
|-------|-----------|
| 1 | Постоянный мониторинг: читает канал в 23:00, применяет отложенные в 06:00, уведомляет в 08:10 |
| 2 | Одноразовая синхронизация за последние `SYNC_LOOKBACK_DAYS` дней |

## Архитектура прокси

Трёхзвенная цепочка для Telethon:
```
Telethon → local relay (127.0.0.1:12345+) → ProxyLine SOCKS5 → MTProto proxy → Telegram
```

Telegram Bot API и Gemini используют обычные HTTP прокси из `proxies.txt`.

## Логи

- `monitor.log` — ротация: макс. 2 МБ, 3 архива
- `data/messages.log` — сообщения из канала, очистка старше 14 дней при каждом старте
