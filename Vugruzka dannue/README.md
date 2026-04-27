# Vugruzka Dannue — загрузка отчётов маркетплейсов в Google Sheets

Читает выгрузки продаж с Ozon, Lamoda и Яндекс.Маркета, нормализует данные и загружает на отдельные листы Google Таблицы. Автоматически формирует сводный дашборд с топ-10 товаров и итогами по маркетплейсам.

## Технологии

- Python 3.11+
- Google Sheets API (gspread, OAuth2)
- pandas, openpyxl — парсинг xlsx/csv/tsv

## Установка

```bash
pip install -r requirements.txt
```

## Настройка

1. Скопируй `.env.example` в `.env`:
   ```bash
   cp .env.example .env
   ```

2. Заполни `.env` своими данными:
   ```
   SPREADSHEET_ID=  # ID таблицы из URL: .../spreadsheets/d/ЗДЕСЬ/edit
   ```

3. Положи файлы авторизации Google в папку `json/`:
   - `credentials.json` — скачать в Google Cloud Console → APIs → Credentials
   - `authorized_user.json` — создаётся автоматически при первом запуске

## Запуск

Положи файлы отчётов в папку `reports/`. Названия файлов должны начинаться с:
- `ozon_` — отчёт Ozon (xlsx)
- `lamoda_` — отчёт Lamoda (csv)
- `ym_` — отчёт Яндекс.Маркет (tsv)

Затем:
```bash
python main.py
```
