# modules/uploader.py — загрузка данных и формирование сводки в Google Sheets

import sys
import gspread
import pandas as pd
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
from config import SPREADSHEET_ID, SHEET_NAMES, SUMMARY_SHEET_NAME, MARKETPLACE_LABELS

def авторизация() -> gspread.Client:
    """Авторизация в Google через OAuth."""
    print("🔑 Авторизация в Google Sheets...")
    корень = Path(__file__).parent.parent
    json_папка = корень / "json"
    client = gspread.oauth(
        credentials_filename=str(json_папка / "credentials.json"),
        authorized_user_filename=str(json_папка / "authorized_user.json"),
    )
    print("✅ Авторизация успешна\n")
    return client

def _получить_или_создать_лист(таблица, имя):
    """Возвращает лист по имени, создаёт если не существует."""
    try:
        return таблица.worksheet(имя)
    except gspread.exceptions.WorksheetNotFound:
        print(f"  ➕ Лист «{имя}» не найден — создаю...")
        return таблица.add_worksheet(title=имя, rows=1000, cols=20)

def загрузить(client, маркетплейс, df, имя_файла):
    """Загружает данные маркетплейса на отдельный лист."""
    таблица = client.open_by_key(SPREADSHEET_ID)
    имя_листа = SHEET_NAMES[маркетплейс]
    лист = _получить_или_создать_лист(таблица, имя_листа)

    # Заменяем NaN/inf на пустую строку — иначе JSON упадёт
    df_upload = df.copy()
    df_upload = df_upload.fillna("").replace([float("inf"), float("-inf")], "")

    # Конвертируем numpy-типы в обычные Python-типы
    данные = [df_upload.columns.tolist()] + [
        [v if not hasattr(v, "item") else v.item() for v in row]
        for row in df_upload.values.tolist()
    ]

    лист.clear()
    лист.update(values=данные, range_name="A1", value_input_option="USER_ENTERED")
    print(f"  ✅ [ {имя_листа} ] Загружено строк: {len(df_upload)}")

def обновить_сводку(client, по_маркетплейсам):
    """Формирует финальный отчет на листе Сводка."""
    print(f"  📊 Обновляю сводный лист «{SUMMARY_SHEET_NAME}»...")
    таблица = client.open_by_key(SPREADSHEET_ID)
    лист = _получить_или_создать_лист(таблица, SUMMARY_SHEET_NAME)

    oz = SHEET_NAMES["ozon"]    # "Ozon"
    lm = SHEET_NAMES["lamoda"]  # "Lamoda"
    ym = SHEET_NAMES["ym"]      # "Яндекс.Маркет"

    # Столбцы листов маркетплейсов:
    # A=Маркетплейс B=Файл C=Дата D=Артикул E=Товар F=Категория
    # G=Продано шт. H=Выручка руб. I=К перечислению руб.

    # ВАЖНО: разделитель ";" и русские названия функций — для русской локали Google Sheets
    def s(sheet_name, col):
        return f"=ЕСЛИОШИБКА(СУММ('{sheet_name}'!{col}2:{col}10000);0)"

    data = [
        ["СВОДНЫЙ ОТЧЁТ ПО ПРОДАЖАМ", "", "", "", ""],
        ["", "", "", "", ""],
        ["ПО МАРКЕТПЛЕЙСАМ", "", "", "", ""],
        ["Маркетплейс", "Продано, шт.", "Выручка, руб.", "К перечислению, руб.", "Доля расходов, %"],
        ["Ozon",          s(oz, "G"), s(oz, "H"), s(oz, "I"), "=ЕСЛИОШИБКА(ЕСЛИ(C5=0;0;(C5-D5)/C5);0)"],
        ["Lamoda",        s(lm, "G"), s(lm, "H"), s(lm, "I"), "=ЕСЛИОШИБКА(ЕСЛИ(C6=0;0;(C6-D6)/C6);0)"],
        ["Яндекс.Маркет", s(ym, "G"), s(ym, "H"), s(ym, "I"), "=ЕСЛИОШИБКА(ЕСЛИ(C7=0;0;(C7-D7)/C7);0)"],
        ["ИТОГО", "=СУММ(B5:B7)", "=СУММ(C5:C7)", "=СУММ(D5:D7)", "=ЕСЛИОШИБКА(ЕСЛИ(C8=0;0;(C8-D8)/C8);0)"],
        ["", "", "", "", ""],
        ["Топ-10 прибыльных товаров", "", "", "", "", ""],
        ["Маркетплейс", "Артикул", "Товар", "Продано, шт.", "Выручка, руб.", "К перечислению, руб."],
        [
            (
                "=ЕСЛИОШИБКА(ЗАПРОС({"
                f"'{oz}'!A2:I10000;"
                f"'{lm}'!A2:I10000;"
                f"'{ym}'!A2:I10000"
                "}; \"SELECT Col1, Col4, Col5, Col7, Col8, Col9 WHERE Col8 > 0 ORDER BY Col8 DESC LIMIT 10\"; 0); \"Нет данных\")"
            ),
            "", "", "", "", ""
        ],
    ]

    лист.clear()
    лист.update(values=data, range_name="A1", value_input_option="USER_ENTERED")
    print(f"  ✅ Сводка обновлена")
