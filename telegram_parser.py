import os
import asyncio
import random
import json
from datetime import datetime, timedelta
from dotenv import load_dotenv
from telethon import TelegramClient
from telethon.errors import SessionPasswordNeededError
import logging

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('telegram_parser.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# Загрузка переменных окружения из .env
load_dotenv()

# Получение конфиденциальных данных
API_ID = os.getenv('TELEGRAM_API_ID')
API_HASH = os.getenv('TELEGRAM_API_HASH')
PHONE_NUMBER = os.getenv('TELEGRAM_PHONE_NUMBER')

# Проверка наличия конфиденциальных данных
if not all([API_ID, API_HASH, PHONE_NUMBER]):
    logger.error("Отсутствуют необходимые переменные окружения: TELEGRAM_API_ID, TELEGRAM_API_HASH или TELEGRAM_PHONE_NUMBER")
    raise ValueError("Необходимо настроить .env файл с TELEGRAM_API_ID, TELEGRAM_API_HASH и TELEGRAM_PHONE_NUMBER")

# Инициализация Telegram клиента
client = TelegramClient('butybot_session', int(API_ID), API_HASH)

# Список Telegram-каналов для парсинга
CHANNELS = [
    'baborru',
    'mesopharm_official',
    'wordtoskin',
    'araviaprofessional',
    'aravialaboratories',
    'kpcosm',
    'geltek_skincare'
]

# Ключевые слова для фильтрации
KEYWORDS = [
    "акция", "скидка", "спецпредложение", "распродажа", "промокод",
    "предложение", "выгода", "бонус", "подарок", "снижение",
    "discount", "sale", "offer", "promo", "deal",
    "coupon", "special", "save", "clearance", "bargain"
]

async def authenticate():
    """Авторизация в Telegram с имитацией поведения пользователя."""
    try:
        await client.start(phone=PHONE_NUMBER)
        if not await client.is_user_authorized():
            logger.info("Требуется авторизация. Отправка кода...")
            await client.send_code_request(PHONE_NUMBER)
            code = input("Введите код авторизации, полученный в Telegram: ")
            try:
                await client.sign_in(PHONE_NUMBER, code)
            except SessionPasswordNeededError:
                password = input("Введите пароль двухфакторной аутентификации: ")
                await client.sign_in(password=password)
        logger.info("Авторизация успешно завершена")
        
        # Получение информации о текущем пользователе
        me = await client.get_me()
        logger.info(f"Авторизован как {me.first_name} ({me.phone})")
        
    except Exception as e:
        logger.error(f"Ошибка при авторизации: {str(e)}")
        raise

async def parse_channel(channel):
    """Парсинг постов из указанного канала за последние 30 дней."""
    try:
        promotions = []
        # Вычисляем дату 30 дней назад
        thirty_days_ago = datetime.now().astimezone() - timedelta(days=30)
        
        async for message in client.iter_messages(channel, offset_date=thirty_days_ago):
            if message.text:  # Проверяем, есть ли текст в сообщении
                text = message.text.lower()
                found_keywords = [kw for kw in KEYWORDS if kw in text]
                if found_keywords:
                    promotion = {
                        "source": "telegram",
                        "channel": f"@{channel}",
                        "post_id": message.id,
                        "date": message.date.isoformat(),
                        "text": message.text,
                        "keywords": found_keywords
                    }
                    promotions.append(promotion)
                    logger.info(f"Найден пост в @{channel} с ключевыми словами: {found_keywords}")
            
            # Случайная задержка для имитации пользователя
            await asyncio.sleep(random.uniform(1, 3))
        
        return promotions
    
    except Exception as e:
        logger.error(f"Ошибка при парсинге канала @{channel}: {str(e)}")
        return []

async def save_promotions(promotions, filename='promotions.json'):
    """Сохранение отфильтрованных постов в JSON."""
    try:
        with open(filename, 'w', encoding='utf-8') as f:
            json.dump(promotions, f, ensure_ascii=False, indent=2)
        logger.info(f"Результаты сохранены в {filename}")
    except Exception as e:
        logger.error(f"Ошибка при сохранении в {filename}: {str(e)}")

async def main():
    """Основная функция для запуска парсинга."""
    try:
        await authenticate()
        logger.info("Клиент Telegram успешно запущен")
        
        all_promotions = []
        for channel in CHANNELS:
            logger.info(f"Парсинг канала @{channel} за последние 30 дней")
            promotions = await parse_channel(channel)
            all_promotions.extend(promotions)
            # Задержка между каналами
            await asyncio.sleep(random.uniform(2, 5))
        
        if all_promotions:
            await save_promotions(all_promotions)
        else:
            logger.info("Подходящих постов за последние 30 дней не найдено")
        
    except Exception as e:
        logger.error(f"Ошибка в основной функции: {str(e)}")
    finally:
        await client.disconnect()
        logger.info("Клиент Telegram отключен")

if __name__ == '__main__':
    asyncio.run(main())