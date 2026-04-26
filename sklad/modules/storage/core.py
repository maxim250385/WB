"""Регионы WB, HTTP-сессия и чтение входных файлов из Data/."""

import os
import random
import time
import requests

# --- Регионы (dest) для карточки и поиска ---
REGIONS = [
    {"name": "Москва и МО",           "id": "-1257786"},
    {"name": "Санкт-Петербург",        "id": "-1235832"},
    {"name": "Центральная Россия",     "id": "-1216601"},
    {"name": "Татарстан / Поволжье",   "id": "-2133462"},
    {"name": "Юг России",              "id": "-1113276"},
    {"name": "Урал",                   "id": "-1181034"},
    {"name": "Сибирь",                 "id": "-117547"},
    {"name": "Дальний Восток",         "id": "-1027986"},
    {"name": "Крым",                   "id": "-1104252"},
    {"name": "Беларусь",               "id": "-382745"},
    {"name": "Казахстан",              "id": "-1113741"},
]

DEFAULT_DEST = REGIONS[0]["id"]

# --- HTTP ---
DEFAULT_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "ru-RU,ru;q=0.9",
    "Origin": "https://www.wildberries.ru",
    "Referer": "https://www.wildberries.ru/",
}


def new_session():
    s = requests.Session()
    s.headers.update(DEFAULT_HEADERS)
    return s


def fetch_json(session, url, timeout=15, attempts=3, pause_on_network=(0.5, 1.5)):
    """
    GET JSON с ретраями при Timeout/ConnectionError.
    Успех: (data, None). Ошибка: (None, err).
    """
    last_net = None
    for attempt in range(attempts):
        try:
            r = session.get(url, timeout=timeout)
            if r.status_code == 400:
                return None, "bad_request"
            r.raise_for_status()
            try:
                return r.json(), None
            except ValueError:
                return None, "json"
        except requests.HTTPError as e:
            return None, e
        except (requests.Timeout, requests.ConnectionError) as e:
            last_net = e
            if attempt < attempts - 1:
                time.sleep(random.uniform(*pause_on_network))
        except Exception as e:
            return None, e
    return None, last_net


# --- Входные файлы ---
def load_lines(path):
    """Строки UTF-8; пустые и строки с # в начале пропускаются."""
    if not os.path.exists(path):
        return []
    out = []
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            out.append(line)
    return out


def load_articles(data_dir, filename="articles.txt"):
    return load_lines(os.path.join(data_dir, filename))


def load_search_queries(data_dir, filename="search_queries.txt"):
    return load_lines(os.path.join(data_dir, filename))
