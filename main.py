import os
import config
from datetime import datetime
from modules.storage import load_articles
from modules.report_pipeline import collect_report
from modules.excel_generator import save_competitor_excel
from modules.Telega import send_report, send_text_message
from modules.EmailSender import send_email_report


def run_parser():
    articles_path = os.path.join(config.DATA_DIR, "articles.txt")
    if not os.path.exists(articles_path):
        print(f"[!] Ошибка: Создай файл {articles_path}")
        return

    articles = load_articles(config.DATA_DIR)
    if not articles:
        print("[!] В articles.txt нет артикулов.")
        return

    summary_rows, stock_rows = collect_report(articles, config.DATA_DIR)

    if not summary_rows and not stock_rows:
        print("[!] Данные не собраны, отправлять нечего.")
        return

    now = datetime.now()
    date_display = now.strftime("%d.%m.%Y %H:%M")
    file_name = f"WB_Report_{now.strftime('%d-%m-%Y_%H-%M')}.xlsx"
    report_path = os.path.join(config.EXCEL_DIR, file_name)

    if save_competitor_excel(summary_rows, stock_rows, report_path) is None:
        print("[!] Не удалось сохранить отчёт, уведомления не отправляются.")
        return

    short_caption = f"✅ **Отчет WB готов!**\n📅 Дата: {date_display}"

    if getattr(config, "SEND_TELEGRAM", True):
        try:
            if config.SEND_EXCEL_FILE:
                send_report(report_path, caption_text=short_caption)
            else:
                send_text_message(short_caption)
        except Exception as e:
            print(f"[!] Ошибка Telegram: {e}")

    if getattr(config, "SEND_EMAIL", True):
        try:
            email_subject = f"WB Остатки: Отчет от {date_display}"
            email_body = (
                f"Скрипт завершил работу.\n"
                f"В файле: лист «Сводка» (конкуренты) и «Остатки».\n"
                f"Дата: {date_display}"
            )
            file_to_attach = report_path if config.SEND_EXCEL_FILE else None
            send_email_report(email_subject, email_body, file_to_attach)
        except Exception as e:
            print(f"[!] Ошибка Email: {e}")


if __name__ == "__main__":
    run_parser()
