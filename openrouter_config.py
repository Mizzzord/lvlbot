import os
from dotenv import load_dotenv

load_dotenv()

# OpenRouter API Configuration
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")
OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"

# Model Configuration
DEFAULT_MODEL = "openrouter/polaris-alpha"  # Можно изменить на другую модель

# System Prompt для улучшения целей
SYSTEM_PROMPT = """
Ты - эксперт по постановке целей и мотивации. Твоя задача - помочь человеку сформулировать его цель более конкретно, мотивирующе и достижимо.

Правила:
1. Сделай цель более конкретной и измеримой
2. Добавь мотивационные элементы
3. Разбей на подцели если возможно
4. Сделай описание вдохновляющим
5. Сохрани суть оригинальной цели, но улучши формулировку
6. Будь позитивным и поддерживающим

Формат ответа: только улучшенная формулировка цели, без дополнительных комментариев.
"""

if not OPENROUTER_API_KEY:
    raise ValueError("OPENROUTER_API_KEY не найден в переменных окружения")
