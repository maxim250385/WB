import smtplib
import os
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.base import MIMEBase
from email import encoders
import config

def get_emails_from_file():
    """Читает список почт из файла Data/emails.txt"""
    emails_list = []
    # Путь к файлу с почтами
    emails_path = os.path.join(config.DATA_DIR, "emails.txt")
    
    # Если файла нет, используем почту отправителя как запасной вариант
    if not os.path.exists(emails_path):
        print(f"[!] Файл {emails_path} не найден. Использую {config.EMAIL_SENDER} как адрес по умолчанию.")
        return [config.EMAIL_SENDER]
    
    with open(emails_path, "r", encoding="utf-8") as f:
        for line in f:
            email = line.strip()
            # Простая проверка, что строка похожа на email
            if email and "@" in email: 
                emails_list.append(email)
                
    # Если файл был пустой, тоже возвращаем адрес отправителя
    return emails_list if emails_list else [config.EMAIL_SENDER]

def send_email_report(subject, body, filename=None):
    """Отправка отчета на все адреса из списка"""
    receivers = get_emails_from_file()
    
    try:
        # Подключение к серверу Яндекса
        with smtplib.SMTP_SSL(config.SMTP_SERVER, config.SMTP_PORT) as server:
            server.login(config.EMAIL_SENDER, config.EMAIL_PASSWORD)
            
            for receiver in receivers:
                msg = MIMEMultipart()
                msg['From'] = config.EMAIL_SENDER
                msg['To'] = receiver
                msg['Subject'] = subject
                msg.attach(MIMEText(body, 'plain'))

                # Прикрепляем Excel файл, если он передан
                if filename and os.path.exists(filename):
                    with open(filename, "rb") as attachment:
                        part = MIMEBase("application", "octet-stream")
                        part.set_payload(attachment.read())
                    encoders.encode_base64(part)
                    part.add_header(
                        "Content-Disposition", 
                        f"attachment; filename= {os.path.basename(filename)}"
                    )
                    msg.attach(part)

                server.send_message(msg)
                print(f"[📧] Отчет успешно отправлен на {receiver}")
                
        return True
    except Exception as e:
        print(f"[❌] Ошибка отправки Email: {e}")
        return False