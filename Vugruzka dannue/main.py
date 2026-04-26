# main.py — точка входа, только управление процессом

import pandas as pd

from config import REPORTS_FOLDER
from modules.reader import найти_файлы, определить_маркетплейс, прочитать_файл
from modules.uploader import авторизация, загрузить, обновить_сводку


def main():
    print("=" * 58)
    print("  Загрузка отчётов маркетплейсов → Google Таблицы")
    print("=" * 58)

    файлы = найти_файлы(REPORTS_FOLDER)

    if not файлы:
        print(f"\n⚠️  В папке «{REPORTS_FOLDER}/» нет файлов.")
        print("   Положи туда файлы с именами:")
        print("   ozon_....xlsx   lamoda_....csv   ym_....tsv")
        return

    print(f"\n📁 Найдено файлов: {len(файлы)}")

    client = авторизация()

    по_маркетплейсам: dict[str, list[pd.DataFrame]] = {}

    for файл in файлы:
        маркетплейс = определить_маркетплейс(файл.name)

        if маркетплейс is None:
            print(f"\n⚠️  Пропускаю «{файл.name}» — маркетплейс не определён.")
            print("   Переименуй файл: ozon_..., lamoda_..., ym_...")
            continue

        print(f"\n[{маркетплейс.upper()}] {файл.name}")
        df = прочитать_файл(файл, маркетплейс)

        if df is not None:
            по_маркетплейсам.setdefault(маркетплейс, []).append(df)

    if not по_маркетплейсам:
        print("\n❌ Ни один файл не прочитан. Проверь настройки в config.py")
        return

    print("\n" + "-" * 58)
    for маркетплейс, датафреймы in по_маркетплейсам.items():
        общий_df = pd.concat(датафреймы, ignore_index=True)
        print(f"\n[{маркетплейс.upper()}] Итого строк: {len(общий_df)}")
        
        # ВАЖНО: передаем в правильном порядке (client, маркетплейс, данные, имя_файла)
        загрузить(client, маркетплейс, общий_df, "Сводный отчет")

    print("\n" + "-" * 58)
    # ВАЖНО: передаем по_маркетплейсам
    обновить_сводку(client, по_маркетплейсам)

    print("\n" + "=" * 58)
    print("   ✅ Готово! Данные загружены в Google Таблицу.")
    print("=" * 58)


if __name__ == "__main__":
    main()
