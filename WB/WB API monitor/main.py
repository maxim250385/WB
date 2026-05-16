import os
import re
import base64
import socks
import asyncio
import json
import logging
import random
from pathlib import Path
from datetime import datetime, timedelta, timezone
from logging.handlers import RotatingFileHandler
from urllib.parse import urlparse, parse_qs
from dotenv import load_dotenv

_BASE_DIR = Path(__file__).parent
load_dotenv(_BASE_DIR / 'data' / '.env')

from telethon import TelegramClient
from telethon.errors import FloodWaitError
from telethon.network import ConnectionTcpMTProxyRandomizedIntermediate
from config import (
    CHANNEL, SESSION_NAME,
    WORK_MODE, DAILY_CHECK_HOUR, PENDING_CHECK_HOUR,
    PENDING_NOTIFY_HOUR, PENDING_NOTIFY_MINUTE, SYNC_LOOKBACK_DAYS,
)
from modules.message_parser import extract_hashtags, extract_russian_text, extract_endpoints
from modules.yaml_updater import (
    process_message_for_yaml, HASHTAG_TO_YAML,
    get_due_pending, mark_pending_applied,
    get_applied_unnotified, mark_pending_notified,
)
from modules.telegram_bot import run_bot, notify

_PROXY_FILE         = str(_BASE_DIR / 'data' / 'proxies.txt')
_MTPROTO_PROXY_FILE = str(_BASE_DIR / 'data' / 'mtproto_proxies.txt')
_LOG_FILE           = str(_BASE_DIR / 'data' / 'messages.log')
_STATE_FILE = str(_BASE_DIR / 'data' / 'state.json')

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    handlers=[
        RotatingFileHandler(
            _BASE_DIR / 'monitor.log',
            maxBytes=2 * 1024 * 1024,  # 2 МБ
            backupCount=3,
            encoding='utf-8',
        ),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)


def _trim_messages_log():
    """Удаляет записи старше 14 дней из messages.log."""
    if not Path(_LOG_FILE).exists():
        return
    with open(_LOG_FILE, 'r', encoding='utf-8') as f:
        content = f.read()
    cutoff = datetime.now() - timedelta(days=14)
    blocks = content.split('\n' + '='*60)
    kept = []
    for block in blocks:
        if not block.strip():
            continue
        for line in block.splitlines():
            if line.startswith('Дата: '):
                try:
                    date_str = line.removeprefix('Дата: ').strip()
                    msg_date = datetime.fromisoformat(date_str.replace('+00:00', ''))
                    if msg_date.replace(tzinfo=None) >= cutoff:
                        kept.append(block)
                except Exception:
                    kept.append(block)
                break
    with open(_LOG_FILE, 'w', encoding='utf-8') as f:
        f.write(('\n' + '='*60).join(kept))

_MODE_LABEL = {
    1: (f"Канал в {DAILY_CHECK_HOUR}:00 / "
        f"pending-apply в {PENDING_CHECK_HOUR}:00 / "
        f"pending-notify в {PENDING_NOTIFY_HOUR}:{PENDING_NOTIFY_MINUTE:02d}"),
    2: "Синхронизация с каналом при старте",
}


# ── State ────────────────────────────────────────────────────────

def load_state() -> dict:
    try:
        with open(_STATE_FILE, encoding='utf-8') as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return {}


def save_state(updates: dict):
    state = load_state()
    state.update(updates)
    with open(_STATE_FILE, 'w', encoding='utf-8') as f:
        json.dump(state, f, indent=2, ensure_ascii=False)


# ── Local relay (ProxyLine SOCKS5 → MTProto proxy) ───────────────

_LOCAL_RELAY_BASE_PORT = 12345


def _load_socks5_list() -> list:
    """Возвращает [(host, http_port), ...] из proxies.txt."""
    result = []
    try:
        with open(_PROXY_FILE, encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith('#') and ':' in line:
                    host, port = line.split(':')
                    result.append((host, int(port)))
    except FileNotFoundError:
        pass
    return result


async def _relay_pipe(reader: asyncio.StreamReader, writer: asyncio.StreamWriter):
    try:
        while True:
            data = await reader.read(4096)
            if not data:
                break
            writer.write(data)
            await writer.drain()
    except Exception:
        pass
    finally:
        try:
            writer.close()
        except Exception:
            pass


async def _handle_relay(reader, writer, target_host, target_port, socks5_list):
    """Принимает соединение от Telethon, туннелирует через ProxyLine SOCKS5 к MTProto прокси."""
    proxy_user = os.getenv('PROXY_USER', '')
    proxy_pass = os.getenv('PROXY_PASS', '')
    loop = asyncio.get_event_loop()

    sock = None
    for proxy_host, http_port in socks5_list:
        s = socks.socksocket()
        s.settimeout(10)
        try:
            s.set_proxy(socks.SOCKS5, proxy_host, http_port + 1, True,
                        proxy_user or None, proxy_pass or None)
            await loop.run_in_executor(None, s.connect, (target_host, target_port))
            s.setblocking(False)
            sock = s
            break
        except Exception:
            s.close()

    if sock is None:
        logger.warning(f"Relay: не удалось подключиться к {target_host}:{target_port} через SOCKS5")
        writer.close()
        return

    remote_reader, remote_writer = await asyncio.open_connection(sock=sock)
    await asyncio.gather(
        _relay_pipe(reader, remote_writer),
        _relay_pipe(remote_reader, writer),
    )


async def start_relay_servers(mtproto_proxies: list, socks5_list: list):
    """Запускает локальные relay-серверы. Возвращает (relay_proxies, servers)."""
    relay_proxies = []
    servers = []
    for i, (server, port, secret) in enumerate(mtproto_proxies):
        local_port = _LOCAL_RELAY_BASE_PORT + i

        async def handler(r, w, s=server, p=port, sl=socks5_list):
            await _handle_relay(r, w, s, p, sl)

        srv = await asyncio.start_server(handler, '127.0.0.1', local_port)
        servers.append(srv)
        relay_proxies.append(('127.0.0.1', local_port, secret))
        logger.info(f"Relay {i+1}: 127.0.0.1:{local_port} → {server}:{port} (через ProxyLine SOCKS5)")

    return relay_proxies, servers


# ── Proxy / Client ───────────────────────────────────────────────

class ProxyPool:
    def __init__(self, proxies: list):
        self._all = list(proxies)
        self._available = list(proxies)

    def get(self):
        if not self._available:
            return None
        proxy = random.choice(self._available)
        self._available.remove(proxy)
        return proxy

    def reset(self):
        self._available = list(self._all)

    @property
    def exhausted(self):
        return not self._available


def load_mtproto_proxies(filename: str) -> list:
    proxies = []
    try:
        with open(filename, 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith('#'):
                    proxies.append(line)
        logger.info(f"Загружено {len(proxies)} MTProto прокси из {filename}")
    except FileNotFoundError:
        logger.warning(f"Файл {filename} не найден, работаем без прокси")
    return proxies


def parse_mtproto_proxy(proxy_str: str):
    """Парсит t.me/proxy?server=...&port=...&secret=... или server:port:secret"""
    try:
        if 't.me' in proxy_str or proxy_str.startswith('http'):
            params = parse_qs(urlparse(proxy_str).query)
            server = params['server'][0]
            port   = int(params['port'][0])
            secret = params['secret'][0]
        else:
            parts  = proxy_str.split(':')
            server, port, secret = parts[0], int(parts[1]), parts[2]

        # base64url → hex (если не чистый hex)
        if not re.match(r'^[0-9a-fA-F]+$', secret):
            pad = (4 - len(secret) % 4) % 4
            secret = base64.urlsafe_b64decode(secret + '=' * pad).hex()

        if secret.lower().startswith('ee'):
            logger.warning(f"Прокси {server}:{port} — ee-секрет (fake TLS), Telethon не поддерживает, пропускаем")
            return None

        return (server, port, secret)
    except Exception as e:
        logger.warning(f"Не удалось распарсить MTProto прокси: {proxy_str} — {e}")
        return None


def create_client(proxy=None):
    api_id   = 2040
    api_hash = 'b18441a1ff607e10a989891a5462e627'
    if proxy:
        server, port, secret = proxy
        logger.info(f"Подключение через MTProto прокси: {server}:{port}")
        return TelegramClient(
            SESSION_NAME, api_id, api_hash,
            connection=ConnectionTcpMTProxyRandomizedIntermediate,
            proxy=(server, port, secret),
        )
    logger.info("Подключение без прокси")
    return TelegramClient(SESSION_NAME, api_id, api_hash)


async def connect_with_pool(pool: ProxyPool):
    phone = os.getenv('TG_PHONE', '')
    while True:
        if pool.exhausted:
            logger.warning("Все прокси перебраны, начинаем новый круг")
            pool.reset()

        proxy = pool.get()
        client = create_client(proxy)
        try:
            await client.start(
                phone=phone if phone else None,
                password=lambda: input('Пароль 2FA (виден на экране): '),
            )
            logger.info("Успешно подключились к Telegram!")
            pool.reset()
            return client
        except FloodWaitError as e:
            logger.warning(f"FloodWait {e.seconds}с — ждём и повторяем через тот же прокси")
            await client.disconnect()
            await asyncio.sleep(e.seconds)
            pool._available.append(proxy)
        except KeyboardInterrupt:
            await client.disconnect()
            raise
        except Exception as e:
            proxy_label = f"{proxy[0]}:{proxy[1]}" if proxy else "no-proxy"  # proxy = (server, port, secret)
            logger.warning(f"Прокси {proxy_label} недоступен ({e}), следующий")
            await client.disconnect()


# ── Processing ───────────────────────────────────────────────────

def save_message(message):
    with open(_LOG_FILE, 'a', encoding='utf-8') as f:
        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        f.write(f"\n{'='*60}\n")
        f.write(f"Дата: {message.date}\n")
        f.write(f"Записано: {timestamp}\n")
        f.write(f"ID сообщения: {message.id}\n")
        f.write(f"Текст:\n{message.text}\n")


async def process_api_update(message_text: str):
    russian_text = extract_russian_text(message_text)
    hashtags = extract_hashtags(message_text)
    endpoints = extract_endpoints(russian_text)

    if not hashtags:
        return

    logger.info(f"API update: хэштеги={hashtags}, endpoints={[f'{m} {p}' for m, p in endpoints]}")

    summaries = []
    failed_yaml = []
    seen_yaml = set()
    for hashtag in hashtags:
        yaml_file = HASHTAG_TO_YAML.get(hashtag)
        if not yaml_file or yaml_file in seen_yaml:
            continue
        seen_yaml.add(yaml_file)
        summary = await asyncio.to_thread(
            process_message_for_yaml, russian_text, hashtag, endpoints
        )
        if summary == '!error':
            failed_yaml.append(yaml_file)
        elif summary:
            summaries.append(summary)

    if summaries:
        await asyncio.to_thread(notify, '\n'.join(summaries))
    if failed_yaml:
        files = '\n'.join(f'• {f}' for f in failed_yaml)
        await asyncio.to_thread(notify, f'⚠️ Gemini не смог обработать — проверь вручную:\n{files}')


async def check_new_messages(client) -> int:
    """
    Обрабатывает все сообщения канала после last_processed_id.
    Для первого запуска (id=0) в режиме 2 — ограничивает глубину SYNC_LOOKBACK_DAYS.
    Возвращает количество обработанных сообщений.
    """
    state = load_state()
    last_id = state.get('last_processed_id', 0)

    new_msgs = []

    if last_id > 0:
        async for msg in client.iter_messages(CHANNEL, min_id=last_id):
            if msg.text:
                new_msgs.append(msg)
    else:
        cutoff = datetime.now(timezone.utc) - timedelta(days=SYNC_LOOKBACK_DAYS)
        async for msg in client.iter_messages(CHANNEL):
            if msg.date < cutoff:
                break
            if msg.text:
                new_msgs.append(msg)

    if not new_msgs:
        return 0

    logger.info(f"Найдено {len(new_msgs)} новых сообщений в @{CHANNEL}")

    for msg in reversed(new_msgs):  # от старых к новым
        logger.info(f"Обрабатываю сообщение #{msg.id} от {msg.date.date()}")
        save_message(msg)
        await process_api_update(msg.text)
        save_state({'last_processed_id': msg.id})

    return len(new_msgs)


# ── Work modes ───────────────────────────────────────────────────

async def daily_check_loop(client):
    """Режим 1: ежедневная проверка в DAILY_CHECK_HOUR:00."""

    # На первом запуске без истории — устанавливаем точку отсчёта на текущее состояние канала
    state = load_state()
    if 'last_processed_id' not in state:
        async for msg in client.iter_messages(CHANNEL, limit=1):
            save_state({'last_processed_id': msg.id})
            logger.info(f"Первый запуск, точка отсчёта: ID={msg.id}")

    while True:
        now = datetime.now()
        target = now.replace(hour=DAILY_CHECK_HOUR, minute=0, second=0, microsecond=0)
        if now >= target:
            target += timedelta(days=1)
        wait_sec = (target - now).total_seconds()

        logger.info(f"Режим 1: следующая проверка через {wait_sec / 3600:.1f}ч (в {DAILY_CHECK_HOUR}:00)")
        await asyncio.sleep(wait_sec)

        logger.info("Режим 1: запускаю ежедневную проверку WB API")
        count = await check_new_messages(client)
        if count == 0:
            logger.info("Новых изменений в WB API не было")
        else:
            logger.info(f"Обработано {count} сообщений")


async def sync_check(client):
    """Режим 2: синхронизация при старте — обработать всё пропущенное."""
    logger.info("Режим 2: синхронизация с каналом @wb_api_notifications...")

    count = await check_new_messages(client)

    if count == 0:
        logger.info("База данных API актуальна, новых сообщений нет")
        await asyncio.sleep(3)  # даём боту время стартовать
        await asyncio.to_thread(notify, "✅ База данных WB API актуальна, новых изменений в канале нет")
    else:
        logger.info(f"Синхронизация завершена, обработано {count} сообщений")


# ── Pending changes ──────────────────────────────────────────────

async def apply_pending_changes():
    """06:00 — применяет отложенные изменения молча (уведомление придёт в 08:10)."""
    due = get_due_pending()
    if not due:
        logger.info("Нет отложенных изменений к применению")
        return

    logger.info(f"Применяю {len(due)} отложенных изменений")
    for record in due:
        hashtag = record['hashtag']
        message_text = record['message']
        endpoints = [tuple(e) for e in record['endpoints']]
        summary = await asyncio.to_thread(
            process_message_for_yaml, message_text, hashtag, endpoints, True
        )
        if summary and summary != '!error':
            mark_pending_applied(record)  # notified=False — уведомление пришлёт pending_notify_loop
            logger.info(f"Применено и ожидает уведомления: {record.get('summary', '')}")
        else:
            logger.warning(f"Не удалось применить: {record.get('summary', '')}")


async def notify_pending_changes():
    """08:10 — отправляет уведомления о том, что было применено в 06:00."""
    unnotified = get_applied_unnotified()
    if not unnotified:
        logger.info("Нет неотправленных уведомлений о pending-изменениях")
        return

    lines = ['📅 Применены отложенные изменения:']
    for record in unnotified:
        lines.append(f"• [{record['apply_date']}] {record['yaml_file']}: {record['summary']}")
        mark_pending_notified(record)

    await asyncio.to_thread(notify, '\n'.join(lines))


async def pending_check_loop():
    """Режим 1: применение в PENDING_CHECK_HOUR:00, уведомление в PENDING_NOTIFY_HOUR:PENDING_NOTIFY_MINUTE."""
    while True:
        now = datetime.now()
        target = now.replace(hour=PENDING_CHECK_HOUR, minute=0, second=0, microsecond=0)
        if now >= target:
            target += timedelta(days=1)
        wait_sec = (target - now).total_seconds()
        logger.info(f"Pending: применение через {wait_sec / 3600:.1f}ч (в {PENDING_CHECK_HOUR}:00)")
        await asyncio.sleep(wait_sec)
        logger.info("Pending: применяю отложенные изменения")
        await apply_pending_changes()


async def pending_notify_loop():
    """Режим 1: уведомления о применённых pending-изменениях в PENDING_NOTIFY_HOUR:PENDING_NOTIFY_MINUTE."""
    while True:
        now = datetime.now()
        target = now.replace(
            hour=PENDING_NOTIFY_HOUR, minute=PENDING_NOTIFY_MINUTE,
            second=0, microsecond=0,
        )
        if now >= target:
            target += timedelta(days=1)
        wait_sec = (target - now).total_seconds()
        logger.info(f"PendingNotify: уведомление через {wait_sec / 3600:.1f}ч "
                    f"(в {PENDING_NOTIFY_HOUR}:{PENDING_NOTIFY_MINUTE:02d})")
        await asyncio.sleep(wait_sec)
        logger.info("PendingNotify: отправляю уведомления")
        await notify_pending_changes()


# ── Main ─────────────────────────────────────────────────────────

async def run(pool: ProxyPool):
    client = None
    bot_task = asyncio.create_task(run_bot())  # бот стартует сразу, не ждёт Telethon
    try:
        client = await connect_with_pool(pool)

        if WORK_MODE == 1:
            await asyncio.gather(
                bot_task,
                daily_check_loop(client),
                pending_check_loop(),
                pending_notify_loop(),
            )
        else:
            await asyncio.gather(bot_task, sync_check(client))

    except asyncio.CancelledError:
        raise
    finally:
        bot_task.cancel()
        try:
            await bot_task
        except (asyncio.CancelledError, Exception):
            pass
        if client:
            await client.disconnect()
            logger.info("Telethon клиент отключён")


async def main():
    _trim_messages_log()
    mode_label = _MODE_LABEL.get(WORK_MODE, f"Режим {WORK_MODE}")
    logger.info(f"WB API Monitor запущен. {mode_label}")

    raw_proxies   = [parse_mtproto_proxy(p) for p in load_mtproto_proxies(_MTPROTO_PROXY_FILE)]
    valid_mtproto = [p for p in raw_proxies if p]

    socks5_list = _load_socks5_list()
    relay_servers = []

    if valid_mtproto and socks5_list:
        relay_proxies, relay_servers = await start_relay_servers(valid_mtproto, socks5_list)
        pool = ProxyPool(relay_proxies)
        logger.info(f"Режим: MTProto через ProxyLine SOCKS5 relay ({len(relay_proxies)} прокси)")
    elif valid_mtproto:
        pool = ProxyPool(valid_mtproto)
        logger.info("Режим: MTProto напрямую")
    else:
        pool = ProxyPool([None])
        logger.info("Режим: без прокси")

    while True:
        try:
            await run(pool)
        except KeyboardInterrupt:
            logger.info("Остановлено пользователем")
            for srv in relay_servers:
                srv.close()
            break
        except Exception as e:
            logger.error(f"Ошибка: {e}. Перезапуск через 30с...")
            await asyncio.sleep(30)


if __name__ == '__main__':
    asyncio.run(main())
