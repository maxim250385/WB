# =============================================================================
#  config.py — Все настройки WB/Ozon Product Extractor
# =============================================================================

import os

# ---------------------------------------------------------------------------
# GEMINI API — вставь свои ключи сюда
# ---------------------------------------------------------------------------
GEMINI_API_KEYS: list[str] = [
    "",
    "",
]

# ---------------------------------------------------------------------------
# GEMINI — каскад моделей по приоритету
# Список сверен с gemini_ru.py — только рабочие модели в v1beta
# ---------------------------------------------------------------------------
GEMINI_MODELS: list[str] = [
    "gemini-3.1-flash-lite-preview",  # Основная (500 RPD бесплатно)
    "gemini-3-flash-preview",         # Запас №1  (~20 RPD)
    "gemini-2.5-flash-lite",          # Запас №2  (~20 RPD)
    "gemini-2.5-flash",               # Последний шанс
]

GEMINI_RPM_LIMIT  = 15
GEMINI_MAX_TOKENS = 8192

# ---------------------------------------------------------------------------
# ПУТИ
# ---------------------------------------------------------------------------
BASE_DIR     = os.path.dirname(os.path.abspath(__file__))
INPUT_DIR    = os.path.join(BASE_DIR, "input")
OUTPUT_DIR   = os.path.join(BASE_DIR, "output")
PROXIES_FILE = os.path.join(BASE_DIR, "proxies.txt")

PATHS = {
    "base":    BASE_DIR,
    "input":   INPUT_DIR,
    "output":  OUTPUT_DIR,
    "proxies": PROXIES_FILE,
}

# ---------------------------------------------------------------------------
# EXCEL
# ---------------------------------------------------------------------------
SHEET_NAME = "Товары"

# ---------------------------------------------------------------------------
# ПОДДЕРЖИВАЕМЫЕ ФОРМАТЫ
# ---------------------------------------------------------------------------
TEXT_EXTENSIONS   = {".txt", ".md"}
OFFICE_EXTENSIONS = {".docx", ".doc"}
PDF_EXTENSIONS    = {".pdf"}
IMAGE_EXTENSIONS  = {".jpg", ".jpeg", ".png", ".webp", ".bmp"}
TABLE_EXTENSIONS  = {".xlsx", ".xls", ".csv"}

ALL_SUPPORTED = (
    TEXT_EXTENSIONS | OFFICE_EXTENSIONS |
    PDF_EXTENSIONS  | IMAGE_EXTENSIONS  | TABLE_EXTENSIONS
)
