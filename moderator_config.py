# Конфигурация для модераторского бота
import os
from dotenv import load_dotenv

load_dotenv()

# Токен модераторского бота (нужно получить отдельный токен от @BotFather)
MODERATOR_BOT_TOKEN = os.getenv("MODERATOR_BOT_TOKEN")

# Функция для парсинга списка ID из строки
def parse_telegram_ids(id_string: str) -> list[int]:
    """Парсит строку с Telegram ID в список целых чисел"""
    if not id_string or id_string.strip() == "":
        return []

    try:
        # Разделяем по запятой, убираем пробелы и конвертируем в int
        return [int(id.strip()) for id in id_string.split(",") if id.strip()]
    except ValueError:
        print(f"Ошибка парсинга Telegram ID: {id_string}")
        return []

# Белый список Telegram ID (читаем из переменных окружения)
ADMIN_TELEGRAM_IDS = parse_telegram_ids(os.getenv("ADMIN_TELEGRAM_IDS", ""))
BLOGGER_TELEGRAM_IDS = parse_telegram_ids(os.getenv("BLOGGER_TELEGRAM_IDS", ""))
MODERATOR_TELEGRAM_IDS = parse_telegram_ids(os.getenv("MODERATOR_TELEGRAM_IDS", ""))

# Проверки
if not MODERATOR_BOT_TOKEN:
    raise ValueError("MODERATOR_BOT_TOKEN не найден в переменных окружения")

if not ADMIN_TELEGRAM_IDS:
    print("⚠️  Внимание: ADMIN_TELEGRAM_IDS не настроен. Добавьте его в .env файл")
    ADMIN_TELEGRAM_IDS = []  # Пустой список по умолчанию

# Настройки базы данных (используем ту же базу данных)
DATABASE_PATH = "bot_database.db"

# Настройки логирования
LOG_LEVEL = "INFO"
LOG_FILE = "moderator_bot.log"
