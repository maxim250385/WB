"""
=============================================================================
  WB / Ozon Product Extractor v1.1
  Запуск: python main.py

  Структура input/:
    input/
    ├── описание.txt         ← 1 файл = 1 товар
    ├── photo.jpg            ← 1 картинка = 1 товар
    ├── 1/                   ← папка = 1 товар (любое кол-во файлов)
    │   ├── фото.jpg
    │   └── spec.pdf
    └── 2/
        └── описание.docx
=============================================================================
"""

import os
import sys
import warnings
from pathlib import Path

os.environ["CURL_CA_BUNDLE"]    = ""
os.environ["PYTHONHTTPSVERIFY"] = "0"
warnings.filterwarnings("ignore")

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from config import PATHS, GEMINI_API_KEYS, ALL_SUPPORTED
from modules.gemini_engine      import GeminiEngine
from modules.category_detector  import detect_category, build_fields_for_category
from modules.validator           import validate_and_fill
from modules.excel_writer        import save_to_excel
from modules.file_reader         import read_file, read_product_folder


def scan_input_dir(input_dir: str) -> list[dict]:
    """
    Возвращает список задач:
      {"source": str, "folder": str|None, "files": [str], "is_folder": bool}
    """
    tasks: list[dict] = []
    if not os.path.exists(input_dir):
        os.makedirs(input_dir)
        return tasks

    for entry in sorted(os.listdir(input_dir)):
        full_path = os.path.join(input_dir, entry)

        if os.path.isdir(full_path):
            files = [
                os.path.join(full_path, f)
                for f in sorted(os.listdir(full_path))
                if os.path.isfile(os.path.join(full_path, f))
                and Path(f).suffix.lower() in ALL_SUPPORTED
            ]
            if files:
                tasks.append({"source": entry, "folder": full_path,
                              "files": files, "is_folder": True})
            else:
                print(f"  [!] Папка '{entry}' пуста.")

        elif os.path.isfile(full_path):
            if Path(entry).suffix.lower() in ALL_SUPPORTED:
                tasks.append({"source": entry, "folder": None,
                              "files": [full_path], "is_folder": False})
    return tasks


def process_product(task: dict, engine: GeminiEngine) -> dict | None:
    source = task["source"]
    files  = task["files"]

    print(f"\n  {'─'*50}")
    print(f"  [►] Товар: {source}  ({len(files)} файл(ов))")

    all_texts : list[str]               = []
    all_images: list[tuple[bytes, str]] = []

    if task["is_folder"]:
        combined_text, all_images = read_product_folder(task["folder"])
        if combined_text:
            all_texts.append(combined_text)
    else:
        for fpath in files:
            fname = os.path.basename(fpath)
            print(f"    [→] Читаю: {fname}")
            text, image_list = read_file(fpath)
            if text:
                all_texts.append(f"--- {fname} ---\n{text}")
            all_images.extend(image_list)

    raw_text = "\n\n".join(all_texts).strip()

    if not raw_text and not all_images:
        print(f"  [!] Нет данных для '{source}', пропускаю.")
        return None

    print(f"    [i] Текста: {len(raw_text)} симв. | Изображений: {len(all_images)}")

    # Определяем категорию
    preliminary_category = detect_category(raw_text)
    print(f"    [i] Предварительная категория: {preliminary_category}")

    fields = build_fields_for_category(preliminary_category)
    print(f"    [i] Полей для извлечения: {len(fields)}")

    # Gemini
    extracted = engine.extract(
        raw_text = raw_text,
        fields   = fields,
        images   = all_images if all_images else None,
    )

    # Уточняем категорию по ответу Gemini
    gemini_category = extracted.get("category")
    if gemini_category:
        refined = detect_category(raw_text, gemini_category)
        if refined != preliminary_category:
            print(f"    [i] Категория уточнена Gemini: {refined}")
            new_fields = build_fields_for_category(refined)
            missing    = [f for f in new_fields if f not in extracted]
            if missing:
                print(f"    [i] Дозапрашиваю {len(missing)} доп. полей...")
                extra = engine.extract(raw_text, missing, all_images or None)
                extracted.update(extra)
            extracted["category"] = refined

    extracted["_source"] = source

    validated, warnings = validate_and_fill(extracted)
    if warnings:
        print(f"    [!] Обязательные поля не найдены: {', '.join(warnings)}")
    else:
        print(f"    [✓] Все обязательные поля заполнены.")
    return validated


def main():
    print("""
╔══════════════════════════════════════════════╗
║   WB / Ozon Product Extractor  v1.1          ║
║   txt · pdf · docx · jpg · png · xlsx · csv  ║
╚══════════════════════════════════════════════╝""")

    valid_keys = [k for k in GEMINI_API_KEYS if k and "ВСТАВЬ" not in k]
    if not valid_keys:
        print("""
[✗] Нет ключей Gemini!
    Открой config.py и вставь ключи в GEMINI_API_KEYS:
    GEMINI_API_KEYS = [
        "AIzaSy_ВАШ_КЛЮЧ_1",
        "AIzaSy_ВАШ_КЛЮЧ_2",
    ]
""")
        sys.exit(1)

    print(f"\n[✓] Ключей Gemini: {len(valid_keys)}")

    tasks = scan_input_dir(PATHS["input"])

    if not tasks:
        print(f"""
[!] Папка input/ пуста или нет поддерживаемых файлов.

Поддерживаемые форматы: .txt .md .pdf .docx .doc .jpg .jpeg .png .webp .xlsx .xls .csv

Структура input/:
  input/
  ├── описание.txt       ← 1 файл = 1 товар
  ├── фото.jpg           ← 1 файл = 1 товар
  ├── 1/                 ← 1 папка = 1 товар
  │   ├── front.jpg
  │   └── spec.pdf
  └── 2/
      └── description.docx
""")
        return

    print(f"\n[✓] Найдено товаров: {len(tasks)}")
    for t in tasks:
        marker = "[папка]" if t["is_folder"] else "[файл] "
        print(f"  {marker} {t['source']}  ({len(t['files'])} файл(ов))")

    print()
    confirm = input("Начать обработку? (Enter = да, n = нет): ").strip().lower()
    if confirm == "n":
        print("Отменено.")
        return

    engine  = GeminiEngine()
    records = []

    for idx, task in enumerate(tasks, 1):
        print(f"\n[{idx}/{len(tasks)}]", end="")
        try:
            record = process_product(task, engine)
            if record:
                records.append(record)
        except KeyboardInterrupt:
            print("\n\n[!] Прервано пользователем.")
            break
        except Exception as e:
            print(f"\n  [✗] Ошибка при обработке '{task['source']}': {e}")

    if not records:
        print("\n[!] Нет данных для сохранения.")
        return

    print(f"\n\n[►] Сохраняю {len(records)} товар(ов) в Excel...")
    try:
        output_path = save_to_excel(records)
        print(f"[✓] Файл сохранён: {output_path}")
    except Exception as e:
        print(f"[✗] Ошибка при сохранении: {e}")
        return

    print("""
╔══════════════════════════════════════════════╗
║                  ГОТОВО!                     ║
║  Проверьте ячейки «Уточнить у поставщика»    ║
║  — они выделены оранжевым в Excel.           ║
╚══════════════════════════════════════════════╝""")


if __name__ == "__main__":
    main()
