import os
import asyncio
import logging
from pathlib import Path
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, MenuButtonCommands
from telegram.error import NetworkError, TimedOut
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, ContextTypes
from telegram.request import HTTPXRequest
from config import WORK_MODE, DAILY_CHECK_HOUR, PENDING_CHECK_HOUR, PENDING_NOTIFY_HOUR, PENDING_NOTIFY_MINUTE

TG_BOT_TOKEN      = os.getenv('TG_BOT_TOKEN', '')
TG_NOTIFY_CHAT_ID = os.getenv('TG_NOTIFY_CHAT_ID', '')
_PROXY_USER       = os.getenv('PROXY_USER', '')
_PROXY_PASS       = os.getenv('PROXY_PASS', '')

_PROXY_FILE = str(Path(__file__).parent.parent / 'data' / 'proxies.txt')

logger = logging.getLogger(__name__)

_app: Application | None = None
_loop: asyncio.AbstractEventLoop | None = None

_MODE_NAMES = {
    1: (f"Канал в {DAILY_CHECK_HOUR}:00 / "
        f"apply в {PENDING_CHECK_HOUR}:00 / "
        f"notify в {PENDING_NOTIFY_HOUR}:{PENDING_NOTIFY_MINUTE:02d}"),
    2: "Синхронизация с каналом при старте",
}


def _close_btn() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([[InlineKeyboardButton("✅ ОК", callback_data="ok_msg")]])


async def _send(text: str, markup=None):
    if not _app or not TG_NOTIFY_CHAT_ID:
        return
    try:
        await _app.bot.send_message(
            chat_id=TG_NOTIFY_CHAT_ID,
            text=text,
            reply_markup=markup,
            parse_mode="HTML",
        )
    except Exception as e:
        logger.error(f"Ошибка отправки в Telegram: {e}")


async def cmd_start(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    mode_name = _MODE_NAMES.get(WORK_MODE, "?")
    await update.message.reply_text(
        f"👋 Привет! Я бот мониторинга WB API.\n\n"
        f"📡 Режим: <b>{mode_name}</b>\n"
        f"📂 Канал: @wb_api_notifications",
        parse_mode="HTML",
    )


async def callback_handler(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    try:
        await query.answer()
    except Exception:
        pass
    if query.data == "ok_msg":
        try:
            await query.message.delete()
        except Exception:
            pass


def notify(text: str):
    """Синхронная отправка уведомления с кнопкой ОК. Безопасно вызывать из любого потока."""
    if not _app or not _loop:
        logger.info(f"[УВЕДОМЛЕНИЕ] {text}")
        print(f"\n📄 Документация обновлена:\n{text}\n")
        return

    async def _do():
        await _send(f"📄 <b>WB API обновлён</b>\n\n{text}", markup=_close_btn())

    future = asyncio.run_coroutine_threadsafe(_do(), _loop)
    try:
        future.result(timeout=15)
    except Exception as e:
        logger.error(f"Ошибка уведомления Telegram: {e}")


def _load_proxies() -> list[str]:
    proxies = []
    try:
        with open(_PROXY_FILE, encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith('#'):
                    if _PROXY_USER and _PROXY_PASS and '@' not in line:
                        proxies.append(f"http://{_PROXY_USER}:{_PROXY_PASS}@{line}")
                    else:
                        proxies.append(f"http://{line}")
    except FileNotFoundError:
        pass
    return proxies


async def run_bot():
    global _app, _loop

    if not TG_BOT_TOKEN:
        logger.warning("TG_BOT_TOKEN не задан — бот уведомлений отключён")
        await asyncio.Event().wait()
        return

    _loop = asyncio.get_running_loop()
    proxies = _load_proxies()
    proxy_idx = 0
    first_start = True

    while True:
        proxy_url = proxies[proxy_idx % len(proxies)] if proxies else None

        try:
            builder = Application.builder().token(TG_BOT_TOKEN)
            if proxy_url:
                ip_port = proxy_url.split("@")[-1]
                logger.info(f"Прокси для Telegram бота: {ip_port}")
                builder = (
                    builder
                    .request(HTTPXRequest(proxy=proxy_url))
                    .get_updates_request(HTTPXRequest(proxy=proxy_url))
                )
            _app = builder.build()

            _app.add_handler(CommandHandler("start", cmd_start))
            _app.add_handler(CallbackQueryHandler(callback_handler))

            await _app.initialize()
            await _app.bot.delete_webhook(drop_pending_updates=False)
            await _app.bot.set_my_commands([("start", "Запустить / открыть меню")])
            await _app.bot.set_chat_menu_button(menu_button=MenuButtonCommands())
            await _app.start()
            await _app.updater.start_polling(drop_pending_updates=False)

            if first_start:
                logger.info("Telegram бот запущен")
                first_start = False
            else:
                logger.info("Telegram бот переподключён")

            await asyncio.Event().wait()

        except (KeyboardInterrupt, SystemExit, asyncio.CancelledError):
            raise

        except (NetworkError, TimedOut) as e:
            if proxies:
                proxy_idx = (proxy_idx + 1) % len(proxies)
                next_ip = proxies[proxy_idx].split("@")[-1]
                logger.warning(f"Сеть Telegram ({e.__class__.__name__}): переключаю прокси → {next_ip}")
            else:
                logger.warning(f"Сеть Telegram ({e.__class__.__name__}): повтор через 30 сек...")

        except Exception as e:
            logger.error(f"Бот упал ({e.__class__.__name__}): {e} — перезапуск через 30 сек...")

        finally:
            try:
                if _app:
                    await _app.updater.stop()
                    await _app.stop()
                    await _app.shutdown()
            except Exception:
                pass
            _app = None

        await asyncio.sleep(30)
