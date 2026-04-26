# modules/reader.py — чтение и парсинг файлов маркетплейсов

import sys
import pandas as pd
from pathlib import Path
from datetime import datetime

# Добавляем корневую папку в путь чтобы импортировать config
sys.path.insert(0, str(Path(__file__).parent.parent))
from config import COLUMNS_MAP, MARKETPLACE_LABELS


def определить_маркетплейс(имя_файла: str) -> str | None:
    """
    Определяет маркетплейс по префиксу имени файла.
    Пример: 'ozon_june2025.xlsx' → 'ozon'
    """
    имя = имя_файла.lower()
    for префикс in COLUMNS_MAP:
        if имя.startswith(префикс + "_") or имя.startswith(префикс + "-"):
            return префикс
    return None


def найти_файлы(папка: str) -> list[Path]:
    """
    Возвращает список всех поддерживаемых файлов в папке.
    Поддерживаемые расширения: .xlsx, .xls, .csv, .tsv
    """
    путь = Path(папка)
    путь.mkdir(exist_ok=True)
    return (
        list(путь.glob("*.xlsx")) +
        list(путь.glob("*.xls"))  +
        list(путь.glob("*.csv"))  +
        list(путь.glob("*.tsv"))
    )


def прочитать_файл(путь: Path, маркетплейс: str) -> pd.DataFrame | None:
    """
    Читает файл отчёта маркетплейса и возвращает
    DataFrame с унифицированными столбцами.

    Возвращает None если файл не удалось прочитать
    или нужные столбцы не найдены.
    """
    cfg = COLUMNS_MAP[маркетплейс]
    тип = cfg["тип"]

    print(f"  📂 Читаю: {путь.name}")

    try:
        if тип == "xlsx":
            df = pd.read_excel(путь, skiprows=cfg.get("skiprows", 0), dtype=str)
        elif тип in ("csv", "tsv"):
            df = pd.read_csv(
                путь,
                sep=cfg.get("sep", ","),
                encoding=cfg.get("encoding", "utf-8"),
                dtype=str,
            )
        else:
            print(f"  ❌ Неизвестный тип файла: {тип}")
            return None
    except Exception as e:
        print(f"  ❌ Ошибка чтения файла: {e}")
        return None

    df.columns = df.columns.str.strip()

    # Проверяем наличие нужных столбцов
    нужные = cfg["столбцы"]
    отсутствующие = [c for c in нужные if c not in df.columns]
    if отсутствующие:
        print(f"  ⚠️  Не найдены столбцы: {отсутствующие}")
        print(f"  ℹ️  Все столбцы в файле:")
        for col in df.columns:
            print(f"       • {col}")
        print(f"  ➡️  Обнови COLUMNS_MAP в config.py под реальные названия.")
        return None

    df = df[нужные].copy()

    # Группировка если нужна (Lamoda — строки по размерам)
    if "группировать_по" in cfg:
        группы = cfg["группировать_по"]
        суммы  = cfg["суммировать"]
        for col in суммы:
            df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0)
        df = df.groupby(группы, as_index=False)[суммы].sum()

    df.rename(columns=cfg["переименовать"], inplace=True)

    # Числовые столбцы
    for col in ["Продано, шт.", "Выручка, руб.", "К перечислению, руб."]:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0)

    # Убираем строки с пустым артикулом или итоговые строки маркетплейса
    # (Ozon добавляет строку «ИТОГО» в конец файла)
    if "Артикул" in df.columns:
        df = df[df["Артикул"].notna() & (df["Артикул"].str.strip() != "")]
        СЛУЖЕБНЫЕ = {"итого", "total", "итог", "всего"}
        df = df[~df["Артикул"].str.strip().str.lower().isin(СЛУЖЕБНЫЕ)]

    # Служебные столбцы
    df.insert(0, "Маркетплейс",   MARKETPLACE_LABELS[маркетплейс])
    df.insert(1, "Файл",          путь.name)
    df.insert(2, "Дата загрузки", datetime.now().strftime("%d.%m.%Y %H:%M"))

    print(f"  ✅ Прочитано строк: {len(df)}")
    return df
