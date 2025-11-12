import os
from dotenv import load_dotenv

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")
if not BOT_TOKEN:
    raise ValueError("BOT_TOKEN не найден в переменных окружения")

# Дополнительные проверки для других токенов (опционально)
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")
WATA_TOKEN = os.getenv("WATA_TOKEN")

# Настройки базы данных
USE_POSTGRES = os.getenv("USE_POSTGRES", "false").lower() == "true"
DATABASE_PATH = os.getenv("DATABASE_PATH", "bot_database.db")
