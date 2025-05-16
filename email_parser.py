import imaplib
import email
from email.header import decode_header
import json
from datetime import datetime
import os
from dotenv import load_dotenv
from bs4 import BeautifulSoup

# Загрузка конфиденциальных данных из .env
load_dotenv()
EMAIL = os.getenv("EMAIL")
PASSWORD = os.getenv("PASSWORD")

# Диагностика
print(f"Путь к .env: {os.path.abspath('.env')}")
print(f"EMAIL: {'*' * len(EMAIL) if EMAIL else None}")
print(f"PASSWORD: {'*' * len(PASSWORD) if PASSWORD else None}")

# Проверка конфигурации
if not EMAIL or not PASSWORD:
    raise ValueError("EMAIL или PASSWORD не указаны в файле .env")

# Подключение к почтовому серверу Gmail
def connect_to_email():
    try:
        imap_server = "imap.gmail.com"
        imap = imaplib.IMAP4_SSL(imap_server)
        imap.login(EMAIL, PASSWORD)
        return imap
    except Exception as e:
        raise Exception(f"Ошибка подключения к почте: {e}")

# Декодирование заголовков письма
def decode_email_subject(subject):
    if subject is None:
        print("Предупреждение: Заголовок письма отсутствует")
        return "No Subject"
    try:
        decoded_subject = decode_header(subject)[0][0]
        if isinstance(decoded_subject, bytes):
            try:
                return decoded_subject.decode()
            except:
                return decoded_subject.decode("utf-8", errors="ignore")
        return str(decoded_subject)
    except Exception as e:
        print(f"Ошибка декодирования заголовка: {e}")
        return "Invalid Subject"

# Извлечение текста письма
def get_email_body(msg):
    try:
        text_content = ""
        html_content = ""
        if msg.is_multipart():
            for part in msg.walk():
                content_type = part.get_content_type()
                if content_type == "text/plain":
                    try:
                        text_content = part.get_payload(decode=True).decode(errors="ignore") or ""
                    except:
                        text_content = ""
                elif content_type == "text/html":
                    try:
                        html_content = part.get_payload(decode=True).decode(errors="ignore") or ""
                    except:
                        html_content = ""
        else:
            content_type = msg.get_content_type()
            if content_type == "text/plain":
                try:
                    text_content = msg.get_payload(decode=True).decode(errors="ignore") or ""
                except:
                    text_content = ""
            elif content_type == "text/html":
                try:
                    html_content = msg.get_payload(decode=True).decode(errors="ignore") or ""
                except:
                    html_content = ""

        # Если есть HTML, извлечь текст с помощью BeautifulSoup
        if html_content:
            soup = BeautifulSoup(html_content, "html.parser")
            html_text = soup.get_text(separator=" ", strip=True)
            return html_text or text_content
        return text_content
    except Exception as e:
        print(f"Ошибка извлечения тела письма: {e}")
        return ""

# Парсинг писем
def parse_emails():
    imap = connect_to_email()
    try:
        imap.select("INBOX")
    except Exception as e:
        imap.logout()
        raise Exception(f"Ошибка выбора папки INBOX: {e}")

    # Фильтр по ключевым словам (20 терминов)
    keywords = [
        "акция", "скидка", "спецпредложение", "распродажа", "промокод",
        "предложение", "выгода", "бонус", "подарок", "снижение",
        "discount", "sale", "offer", "promo", "deal",
        "coupon", "special", "save", "clearance", "bargain"
    ]
    promotions = []

    # Поиск писем
    try:
        _, message_numbers = imap.search(None, "ALL")
    except Exception as e:
        imap.logout()
        raise Exception(f"Ошибка поиска писем: {e}")

    for num in message_numbers[0].split()[:50]:  # Обрабатываем до 50 писем
        try:
            _, msg_data = imap.fetch(num, "(RFC822)")
            email_body = msg_data[0][1]
            msg = email.message_from_bytes(email_body)

            subject = decode_email_subject(msg["subject"])
            sender = msg["from"] if msg["from"] else "Unknown Sender"
            date = msg["date"] if msg["date"] else "Unknown Date"
            body = get_email_body(msg)

            print(f"Обработка письма {num}: subject={subject}, sender={sender}")

            # Проверка на наличие ключевых слов
            if body and any(keyword.lower() in (subject.lower() + body.lower()) for keyword in keywords):
                promotion = {
                    "subject": subject,
                    "sender": sender,
                    "date": date,
                    "body": body[:500]  # Ограничим длину тела письма
                }
                promotions.append(promotion)
            else:
                print(f"Письмо {num} не содержит ключевых слов или пустое тело")
        except Exception as e:
            print(f"Ошибка при обработке письма {num}: {e}")

    imap.logout()

    # Сохранение в JSON
    try:
        with open("promotions.json", "w", encoding="utf-8") as f:
            json.dump(promotions, f, ensure_ascii=False, indent=4)
    except Exception as e:
        print(f"Ошибка сохранения в JSON: {e}")

    return promotions

if __name__ == "__main__":
    try:
        promotions = parse_emails()
        print(f"Найдено {len(promotions)} акционных писем")
    except Exception as e:
        print(f"Ошибка: {e}")