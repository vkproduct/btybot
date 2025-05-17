import os
import asyncio
import random
import logging
from datetime import datetime, timedelta
from telethon import TelegramClient
from telethon.errors import ChannelInvalidError, FloodWaitError
from dotenv import load_dotenv
import json
from urllib.parse import urlparse

# Настройка логирования
logging.basicConfig(
    filename='telegram_parser.log',
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Загрузка переменных окружения
load_dotenv()
API_ID = os.getenv('API_ID')
API_HASH = os.getenv('API_HASH')
PHONE = os.getenv('PHONE')
PARSE_DAYS = int(os.getenv('PARSE_DAYS', 30))  # Дефолт 30 дней

# Список каналов
CHANNELS = [
    '@baborru', '@mesopharm_official', '@wordtoskin', '@araviaprofessional',
    '@aravialaboratories', '@kpcosm', '@geltek_skincare'
]

# Ключевые слова для фильтрации
KEYWORDS = [
    'акция', 'скидка', 'спецпредложение', 'sale', 'распродажа', 'промокод',
    'предложение', 'дисконт', 'выгода', 'подарок', 'бесплатно', 'снижение',
    'цена', 'оффер', 'бонус', 'пробник', 'новинка', 'лимит', 'коллекция', 'уход'
]

async def main():
    # Инициализация клиента
    client = TelegramClient('session', int(API_ID), API_HASH)
    await client.start(phone=PHONE)
    logger.info("Клиент Telegram успешно авторизован")

    promotions = []
    date_limit = datetime.now() - timedelta(days=PARSE_DAYS)

    for channel in CHANNELS:
        try:
            # Получение информации о канале
            entity = await client.get_entity(channel)
            channel_title = entity.title
            logger.info(f"Парсинг канала: {channel} ({channel_title})")

            async for message in client.iter_messages(channel, limit=1000):
                if message.date.replace(tzinfo=None) < date_limit:
                    break

                if not message.text:
                    # Проверка на наличие текста в изображении
                    if message.media and hasattr(message.media, 'photo'):
                        logger.warning(f"Пост {message.id} в {channel} содержит изображение без текста. Возможен текст на изображении. Рекомендуется OCR (например, pytesseract).")
                    continue

                # Поиск ключевых слов
                found_keywords = [kw for kw in KEYWORDS if kw.lower() in message.text.lower()]
                if not found_keywords:
                    continue

                # Извлечение изображений
                images = []
                if message.media and hasattr(message.media, 'photo'):
                    # Загрузка изображения
                    file_name = f"images/{channel.replace('@', '')}_{message.id}.jpg"
                    os.makedirs('images', exist_ok=True)
                    await client.download_media(message.media, file_name)
                    images.append(file_name)
                    logger.info(f"Изображение сохранено: {file_name}")

                # Формирование записи
                promotion = {
                    "source": "telegram",
                    "channel": channel,
                    "channel_title": channel_title,
                    "post_id": message.id,
                    "date": message.date.strftime('%Y-%m-%dT%H:%M:%S'),
                    "text": message.text,
                    "keywords": found_keywords,
                    "images": images
                }
                promotions.append(promotion)
                logger.info(f"Найдена акция в {channel}, пост {message.id}")

                # Имитация поведения пользователя
                await asyncio.sleep(random.uniform(1, 3))

        except ChannelInvalidError:
            logger.error(f"Канал {channel} недоступен или приватный")
            continue
        except FloodWaitError as e:
            logger.error(f"Ограничение Telegram API, ожидание {e.seconds} секунд")
            await asyncio.sleep(e.seconds)
        except Exception as e:
            logger.error(f"Ошибка при парсинге {channel}: {str(e)}")
            continue

    # Сохранение результатов
    with open('promotions.json', 'w', encoding='utf-8') as f:
        json.dump(promotions, f, ensure_ascii=False, indent=2)
    logger.info(f"Сохранено {len(promotions)} акций в promotions.json")

    await client.disconnect()
    logger.info("Клиент Telegram отключен")

if __name__ == "__main__":
    asyncio.run(main())
    