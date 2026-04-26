# =============================================================================
#  modules/gemini_engine.py — Gemini API
#  Логика точно по gemini_ru.py + обработка 404 (модель не найдена)
#
#  Поведение по кодам ответа:
#    200  → успех
#    429/RPM → ждём точное время из ответа, один retry, та же модель
#    429/RPD → model_rate_limited, следующая модель
#    404  → модель не существует в API → сразу следующая модель (не долбим прокси)
#    503  → перегруз, пауза RETRY_503_DELAY сек, до RETRY_503_MAX раз
#    др.  → all_rate_limited=False, следующий прокси
# =============================================================================

from __future__ import annotations

import json
import math
import re
import time
import os
import requests

from config import (
    PATHS, GEMINI_MODELS, GEMINI_API_KEYS,
    GEMINI_RPM_LIMIT, GEMINI_MAX_TOKENS,
)
from modules.prompts import SYSTEM_PROMPT, SYSTEM_PROMPT_VISION, build_extraction_prompt
from modules.file_reader import image_to_base64

RETRY_503_MAX   = 3
RETRY_503_DELAY = 30


# =============================================================================
#  Загрузка прокси — формат: ip:port:login:password
# =============================================================================

def _load_proxies() -> list[tuple[str, str]]:
    path = PATHS["proxies"]
    if not os.path.exists(path):
        return []
    out: list[tuple[str, str]] = []
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            parts = line.split(":")
            if len(parts) != 4:
                print(f"  [!] Неверный формат прокси, пропускаю: {line}")
                continue
            host, port, user, password = parts
            url = f"http://{user}:{password}@{host}:{port}"
            out.append((f"{host}:{port}", url))
    return out


# =============================================================================
#  Вспомогательные функции (из gemini_ru.py)
# =============================================================================

def _rate_limit_kind(response_body: str) -> str:
    try:
        j    = json.loads(response_body or "")
        text = ((j.get("error") or {}).get("message") or "").lower()
    except Exception:
        text = (response_body or "").lower()
    minute_markers = ("per minute", "minute", "rpm", "tpm",
                      "requests per minute", "tokens per minute", "retry in")
    day_markers    = ("per day", "per-day", "daily", "rpd",
                      "requests per day", "tokens per day", "quota")
    if any(m in text for m in minute_markers):
        return "minute"
    if any(m in text for m in day_markers) and "day" in text:
        return "day"
    return "unknown"


def _retry_wait(response_body: str) -> int:
    try:
        text = json.loads(response_body or "").get("error", {}).get("message", "")
    except Exception:
        text = response_body or ""
    m = re.search(r"retry in ([\d.]+)\s*s", text, re.IGNORECASE)
    if m:
        return max(5, math.ceil(float(m.group(1))))
    return 65


def _is_safety_block(payload: dict) -> bool:
    pf = payload.get("promptFeedback") or {}
    br = pf.get("blockReason")
    if isinstance(br, str) and br and br != "BLOCK_REASON_UNSPECIFIED":
        return True
    safety_reasons = {"SAFETY", "BLOCKLIST", "PROHIBITED_CONTENT", "SPII"}
    for c in payload.get("candidates") or []:
        if isinstance(c, dict) and c.get("finishReason") in safety_reasons:
            return True
    return False


def _http_suggests_safety(status_code: int, body: str, err_obj: dict) -> bool:
    err = err_obj.get("error") if isinstance(err_obj, dict) else None
    msg = (err.get("message") if isinstance(err, dict) else None) or ""
    combined = f"{msg} {body}".lower()
    markers = ("safety", "blocked", "harm", "content policy",
                "prohibited", "recitation", "personally identifiable")
    return any(m in combined for m in markers)


def _clean_json(text: str) -> str:
    text = text.strip()
    text = re.sub(r"^```(?:json)?\s*", "", text)
    text = re.sub(r"\s*```$", "", text)
    return text.strip()


# =============================================================================
#  Payload (text или multimodal Vision)
# =============================================================================

def _build_payload(system_prompt: str, user_text: str,
                   images: list[tuple[bytes, str]] | None = None) -> dict:
    user_parts: list[dict] = []
    if images:
        for img_bytes, mime_type in images:
            user_parts.append({
                "inlineData": {"mimeType": mime_type, "data": image_to_base64(img_bytes)}
            })
    if user_text.strip():
        user_parts.append({"text": user_text})
    return {
        "systemInstruction": {"parts": [{"text": system_prompt}]},
        "contents":          [{"parts": user_parts}],
        "generationConfig":  {"maxOutputTokens": GEMINI_MAX_TOKENS, "temperature": 0.0},
    }


# =============================================================================
#  Основной вызов — логика gemini_ru.py + обработка 404
# =============================================================================

def _call_gemini(
    api_key:       str,
    system_prompt: str,
    user_text:     str,
    images:        list[tuple[bytes, str]] | None = None,
) -> str | None:
    if not user_text.strip() and not images:
        return None

    entries = _load_proxies()
    if not entries:
        entries = [("direct", None)]

    headers = {
        "Content-Type":   "application/json",
        "x-goog-api-key": api_key,
    }
    payload = _build_payload(system_prompt, user_text, images)

    all_rate_limited = True
    last_err         = ""

    for model_idx, model in enumerate(GEMINI_MODELS):
        url = (
            "https://generativelanguage.googleapis.com/v1beta/models/"
            f"{model}:generateContent"
        )
        model_rate_limited  = False
        model_not_found     = False   # ← флаг 404
        minute_retry_done   = False

        for _label, proxy_url in entries:
            proxies     = {"http": proxy_url, "https": proxy_url} if proxy_url else None
            retries_503 = 0

            while True:
                try:
                    r = requests.post(
                        url, headers=headers, json=payload,
                        proxies=proxies, timeout=120, verify=False,
                    )
                except requests.RequestException as e:
                    last_err         = str(e)
                    all_rate_limited = False
                    print(f"  [!] Сетевая ошибка ({_label}): {e}")
                    break

                # 200 — успех
                if r.status_code == 200:
                    try:
                        data = r.json()
                    except json.JSONDecodeError:
                        return (r.text or "")[:8000] or None
                    if _is_safety_block(data):
                        print("  [!] Gemini: блок по безопасности.")
                        all_rate_limited = False
                        return None
                    try:
                        text = data["candidates"][0]["content"]["parts"][0]["text"]
                        if isinstance(text, str) and text.strip():
                            return text.strip()
                    except (KeyError, IndexError, TypeError):
                        pass
                    return None

                # 429 — Rate Limit
                if r.status_code == 429:
                    model_rate_limited = True
                    kind = _rate_limit_kind(r.text or "")
                    if kind == "minute" and not minute_retry_done:
                        wait = _retry_wait(r.text or "")
                        print(f"  [~] {model}: RPM-лимит. Жду {wait} сек...")
                        time.sleep(wait)
                        minute_retry_done  = True
                        model_rate_limited = False
                        continue
                    # Дневной лимит → следующая модель
                    next_m = GEMINI_MODELS[model_idx + 1] if model_idx + 1 < len(GEMINI_MODELS) else None
                    if next_m:
                        print(f"  [!] {model} исчерпана → {next_m}...")
                    model_rate_limited = True
                    break

                # 404 — модель не существует в API
                # НЕ долбим остальные прокси — они дадут тот же 404
                if r.status_code == 404:
                    all_rate_limited = False
                    model_not_found  = True
                    next_m = GEMINI_MODELS[model_idx + 1] if model_idx + 1 < len(GEMINI_MODELS) else None
                    if next_m:
                        print(f"  [!] {model}: не найдена в API (404) → {next_m}...")
                    else:
                        print(f"  [!] {model}: не найдена в API (404). Больше моделей нет.")
                    break  # выходим из while → break из for прокси → break из for модели

                # 503 — перегруз Google, retry
                if r.status_code == 503:
                    all_rate_limited = False
                    retries_503 += 1
                    if retries_503 <= RETRY_503_MAX:
                        print(f"  [~] {model}: 503 перегруз. "
                              f"Попытка {retries_503}/{RETRY_503_MAX}. Жду {RETRY_503_DELAY} сек...")
                        time.sleep(RETRY_503_DELAY)
                        continue
                    else:
                        print(f"  [!] {model}: 503 после {RETRY_503_MAX} попыток → следующий прокси")
                        last_err = (r.text or "")[:300]
                        break

                # Другие ошибки
                all_rate_limited = False
                try:
                    err_json = r.json()
                except json.JSONDecodeError:
                    err_json = {}
                if _http_suggests_safety(r.status_code, r.text or "",
                                         err_json if isinstance(err_json, dict) else {}):
                    print("  [!] Gemini: ответ заблокирован по безопасности.")
                    return None
                last_err = (r.text or "")[:300]
                print(f"  [!] HTTP {r.status_code}: {last_err[:150]}")
                break

            # Если модель 404 — сразу прерываем цикл по прокси
            if model_not_found or model_rate_limited:
                break

        if not model_rate_limited and not model_not_found:
            all_rate_limited = False

    if all_rate_limited:
        print("  [✗] Все модели Gemini исчерпали лимиты (429).")
    else:
        print(f"  [✗] Запрос не удался. Последняя ошибка: {last_err[:200]}")
    return None


# =============================================================================
#  Публичный класс
# =============================================================================

class GeminiEngine:
    def __init__(self):
        self.api_keys           = [k for k in GEMINI_API_KEYS if k and "ВСТАВЬ" not in k]
        self.key_idx            = 0
        self._request_times: list[float] = []

    def _enforce_rpm(self):
        now = time.time()
        self._request_times = [t for t in self._request_times if now - t < 60]
        if len(self._request_times) >= GEMINI_RPM_LIMIT:
            wait = 61 - (now - self._request_times[0])
            if wait > 0:
                print(f"\r  [~] RPM-лимит: жду {wait:.0f} сек...", end="", flush=True)
                time.sleep(wait)
                print()
        self._request_times.append(time.time())

    def extract(
        self,
        raw_text: str,
        fields:   list[str],
        images:   list[tuple[bytes, str]] | None = None,
    ) -> dict:
        if not self.api_keys:
            print("  [✗] Нет ключей Gemini. Вставь в config.py")
            return {f: None for f in fields}

        has_images    = bool(images)
        system_prompt = SYSTEM_PROMPT_VISION if has_images else SYSTEM_PROMPT
        user_prompt   = build_extraction_prompt(raw_text, fields)

        while self.key_idx < len(self.api_keys):
            key = self.api_keys[self.key_idx]
            self._enforce_rpm()
            raw_result = _call_gemini(key, system_prompt, user_prompt, images)
            if raw_result is not None:
                return self._parse_json(raw_result, fields)
            self.key_idx += 1
            if self.key_idx < len(self.api_keys):
                print(f"  [!] Переключаюсь на ключ #{self.key_idx + 1}...")

        print("  [✗] Все ключи исчерпаны.")
        return {f: None for f in fields}

    def _parse_json(self, raw: str, fields: list[str]) -> dict:
        clean = _clean_json(raw)
        try:
            data = json.loads(clean)
            if not isinstance(data, dict):
                raise ValueError("Не JSON-объект")
            return {field: data.get(field, None) for field in fields}
        except (json.JSONDecodeError, ValueError) as e:
            print(f"  [!] Не удалось распарсить JSON: {e}")
            print(f"  [!] Ответ: {raw[:300]}")
            return {f: None for f in fields}
