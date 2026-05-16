import os
import re
import json
import time
import random
import requests
from pathlib import Path

_PROXY_FILE  = str(Path(__file__).parent.parent / 'data' / 'proxies.txt')
_PROXY_USER  = os.getenv('PROXY_USER', '')
_PROXY_PASS  = os.getenv('PROXY_PASS', '')

# ─── Настройки Gemini ─────────────────────────────────────
GEMINI_KEYS: list[str] = [k for k in [
    os.getenv('GEMINI_KEY_1'),
    os.getenv('GEMINI_KEY_2'),
    os.getenv('GEMINI_KEY_3'),
    os.getenv('GEMINI_KEY_4'),
    os.getenv('GEMINI_KEY_5'),
    os.getenv('GEMINI_KEY_6'),
    os.getenv('GEMINI_KEY_7'),
    os.getenv('GEMINI_KEY_8'),
] if k]

GEMINI_MODELS: list[str] = [
    'gemini-2.5-flash-lite',
    'gemini-2.5-flash',
    'gemini-2.0-flash',
]

PAUSE_AFTER_RATE_LIMIT   = 6    # сек после 429/503
PAUSE_BETWEEN_KEYS       = 3    # сек между ключами
PAUSE_ALL_KEYS_EXHAUSTED = 60   # сек ожидания когда все ключи исчерпаны


def _load_proxies() -> list[dict]:
    proxies = []
    try:
        with open(_PROXY_FILE, 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith('#'):
                    if _PROXY_USER and _PROXY_PASS and '@' not in line:
                        url = f'http://{_PROXY_USER}:{_PROXY_PASS}@{line}'
                    else:
                        url = f'http://{line}'
                    proxies.append({'http': url, 'https': url})
    except FileNotFoundError:
        pass
    return proxies


_proxies = _load_proxies()


def _get_proxy_for_key(key_index: int) -> dict | None:
    """Каждый ключ получает свой кусок пула прокси — меньше шансов получить бан по IP."""
    if not _proxies:
        return None
    chunk_size = max(1, len(_proxies) // max(len(GEMINI_KEYS), 1))
    start = key_index * chunk_size
    chunk = _proxies[start:start + chunk_size] or _proxies
    return random.choice(chunk)


def _call_gemini(prompt: str, key: str, proxy: dict | None) -> str | None:
    """Один запрос к Gemini. Перебирает все модели для данного ключа."""
    for model in GEMINI_MODELS:
        url = (
            f'https://generativelanguage.googleapis.com/v1beta/models/'
            f'{model}:generateContent?key={key}'
        )
        payload = {
            'contents': [{'parts': [{'text': prompt}]}],
            'generationConfig': {
                'temperature': 0.1,
                'maxOutputTokens': 4096,
                'response_mime_type': 'application/json',
            },
        }
        try:
            resp = requests.post(url, json=payload, proxies=proxy, timeout=60)
            if resp.status_code == 200:
                data = resp.json()
                return data['candidates'][0]['content']['parts'][0]['text'].strip()
            elif resp.status_code in (429, 503):
                print(f'  [~] {model} — лимит/перегруз, следующая модель')
                time.sleep(PAUSE_AFTER_RATE_LIMIT)
                continue
            else:
                print(f'  [!] {model} — ошибка {resp.status_code}: {resp.text[:150]}')
                continue
        except Exception as e:
            print(f'  [!] {model} — исключение: {e}')
            continue
    return None


def _parse_json(raw: str) -> dict | None:
    raw = raw.strip()
    if raw.startswith('```'):
        raw = raw.split('```')[1]
        if raw.startswith('json'):
            raw = raw[4:]
        raw = raw.strip()
    brace = raw.find('{')
    if brace > 0:
        raw = raw[brace:]
    end = raw.rfind('}')
    if end != -1:
        raw = raw[:end + 1]
    try:
        return json.loads(raw)
    except json.JSONDecodeError as e:
        if 'escape' in str(e).lower():
            # Gemini иногда вставляет YAML-контент с голыми \ в JSON — фиксим
            fixed = re.sub(r'\\(?!["\\/bfnrtu])', r'\\\\', raw)
            try:
                return json.loads(fixed)
            except json.JSONDecodeError:
                pass
        print(f'  [!] JSON parse error: {e}\n  Ответ: {raw[:300]}')
        return None


def ask_gemini_json(prompt: str, max_retries: int = 3) -> dict | None:
    """
    Отправляет промт в Gemini, возвращает распарсенный JSON.
    Перебирает ключи и модели при ошибках. При исчерпании всех ключей — ждёт и повторяет.
    """
    for attempt in range(max_retries):
        for key_index, key in enumerate(GEMINI_KEYS):
            proxy = _get_proxy_for_key(key_index)
            raw = _call_gemini(prompt, key, proxy)
            if raw:
                result = _parse_json(raw)
                if result:
                    return result
                print(f'  [!] Битый JSON от ключа {key_index + 1}, повтор...')
            else:
                print(f'  [~] Ключ {key_index + 1} не сработал')
            time.sleep(PAUSE_BETWEEN_KEYS)

        print(f'  [!] Все ключи исчерпаны (попытка {attempt + 1}/{max_retries}) '
              f'— жду {PAUSE_ALL_KEYS_EXHAUSTED}с...')
        time.sleep(PAUSE_ALL_KEYS_EXHAUSTED)

    print('  [✗] Gemini недоступен после всех попыток')
    return None
