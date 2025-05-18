import os
import asyncio
import random
import logging
import re
from datetime import datetime, timedelta
from telethon import TelegramClient
from telethon.errors import ChannelInvalidError, FloodWaitError
from dotenv import load_dotenv
import json
from urllib.parse import urlparse

# Настройка логирования
logging.basicConfig(
    filename='telegram_parser.log',
    level=logging.DEBUG,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Загрузка переменных окружения
env_loaded = load_dotenv()
logger.info(f"Файл .env загружен: {env_loaded}")
if not env_loaded:
    raise FileNotFoundError("Файл .env не найден или не удалось загрузить")

# Чтение переменных
API_ID = os.getenv('API_ID')
API_HASH = os.getenv('API_HASH')
PHONE = os.getenv('PHONE')
PARSE_DAYS = os.getenv('PARSE_DAYS', '30')  # Дефолт 30 дней

# Проверка переменных окружения
required_vars = {'API_ID': API_ID, 'API_HASH': API_HASH, 'PHONE': PHONE}
for var_name, var_value in required_vars.items():
    if not var_value:
        logger.error(f"Переменная окружения {var_name} не найдена или пуста в .env")
        raise ValueError(f"Переменная окружения {var_name} не найдена или пуста. Проверьте файл .env")

# Список каналов
CHANNELS = [
    '@baborru', '@mesopharm_official', '@wordtoskin', '@araviaprofessional',
    '@aravialaboratories', '@kpcosm', '@geltek_skincare'
]

# Ключевые слова для фильтрации
KEYWORDS = [
    'акция', 'скидка', 'спецпредложение', 'sale', 'распродажа', 'промокод',
    'предложение', 'дисконт', 'выгода', 'подарок', 'бесплатно', 'снижение',
    'цена', 'оффер', 'бонус', 'пробник', 'новинка', 'лимит', 'коллекция', 'уход',
    'косметика', 'покупка'
]

def generate_description(text, keywords, channel, max_length=100):
    """Генерирует краткое описание акции на основе текста и ключевых слов."""
    description = ""
    source_text = text or ""
    
    for kw in keywords:
        if kw in source_text.lower():
            match = re.search(r'(\d+%)\s*(?:скидка|sale|распродажа)?\s*на\s*([\w\s]+?)(?:\s*до\s*([\w\s]+))?', source_text, re.IGNORECASE)
            if match:
                discount, product, deadline = match.groups()
                description = f"{discount} на {product.strip()}"
                if deadline:
                    description += f" до {deadline.strip()}"
                break
            else:
                description = f"{kw.capitalize()} от {channel}"
                break

    if not description:
        description = source_text[:max_length].strip()

    if len(description) > max_length:
        description = description[:max_length-3].strip() + "..."
    return description

async def save_promotions(promotions, filename='telegram_promotions.json'):
    """Сохраняет результаты в указанный файл."""
    logger.info(f"Попытка сохранить {len(promotions)} акций в {filename}")
    try:
        with open(filename, 'w', encoding='utf-8') as f:
            json.dump(promotions, f, ensure_ascii=False, indent=2)
        logger.info(f"Успешно сохранено {len(promotions)} акций в {filename}")
    except Exception as e:
        logger.error(f"Ошибка при сохранении {filename}: {str(e)}")
        raise

async def main():
    # Инициализация клиента
    client = TelegramClient('session', int(API_ID), API_HASH)
    await client.start(phone=PHONE)
    logger.info("Клиент Telegram успешно авторизован")

    promotions = []
    date_limit = (datetime.now() - timedelta(days=int(PARSE_DAYS))).date()

    for channel in CHANNELS:
        try:
            # Получение информации о канале
            entity = await client.get_entity(channel)
            channel_title = entity.title
            logger.info(f"Парсинг канала: {channel} ({channel_title})")

            async for message in client.iter_messages(channel, limit=100):
                message_date = message.date.replace(tzinfo=None).date()
                if message_date < date_limit:
                    logger.info(f"Достигнута дата {message.date} в {channel}, старше {date_limit}")
                    break

                # Инициализация текста и ключевых слов
                text = message.text or ""
                found_keywords = []

                # Извлечение изображения
                images = []
                if message.media and hasattr(message.media, 'photo'):
                    file_name = f"images/{channel.replace('@', '')}_{message.id}.jpg"
                    os.makedirs('images', exist_ok=True)
                    try:
                        await client.download_media(message.media, file_name)
                        images.append(file_name)
                        logger.info(f"Изображение сохранено: {file_name}")
                    except Exception as e:
                        logger.error(f"Ошибка загрузки изображения в посте {message.id} в {channel}: {str(e)}")

                # Поиск ключевых слов
                found_keywords = [kw for kw in KEYWORDS if kw.lower() in text.lower()]
                if not found_keywords:
                    logger.debug(f"Пост {message.id} в {channel} не содержит ключевых слов: {text[:100]}...")
                    continue

                # Извлечение ссылок
                links = []
                url_pattern = r'https?://[^\s<>"]+|www\.[^\s<>"]+'
                urls = re.findall(url_pattern, text)
                for url in urls:
                    parsed = urlparse(url)
                    if parsed.scheme and parsed.netloc:
                        links.append(url)
                if links:
                    logger.info(f"Найдены ссылки в посте {message.id} в {channel}: {links}")

                # Генерация описания
                description = generate_description(text, found_keywords, channel)

                # Формирование записи
                promotion = {
                    "source": "telegram",
                    "channel": channel,
                    "channel_title": channel_title,
                    "post_id": message.id,
                    "date": message.date.strftime('%Y-%m-%dT%H:%M:%S'),
                    "text": text,
                    "keywords": found_keywords,
                    "images": images,
                    "links": links,
                    "description": description
                }
                promotions.append(promotion)
                logger.info(f"Добавлена акция: канал={channel}, пост={message.id}, дата={promotion['date']}, ключевые слова={found_keywords}")

                # Промежуточное сохранение
                await save_promotions(promotions, 'telegram_promotions.json')

            # Сохранение после канала
            await save_promotions(promotions, 'telegram_promotions.json')

        except ChannelInvalidError:
            logger.error(f"Канал {channel} недоступен или приватный")
            continue
        except FloodWaitError as e:
            logger.error(f"Ограничение Telegram API, ожидание {e.seconds} секунд")
            await asyncio.sleep(e.seconds)
        except Exception as e:
            logger.error(f"Ошибка при парсинге {channel}: {str(e)}")
            continue

    # Финальное сохранение
    await save_promotions(promotions, 'telegram_promotions.json')

    await client.disconnect()
    logger.info("Клиент Telegram отключен")

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except Exception as e:
        logger.error(f"Скрипт завершился с ошибкой: {str(e)}")
        raise