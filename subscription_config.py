# Конфигурация подписок по уровням
SUBSCRIPTION_LEVELS = [
    {
        "level": 1,
        "name": "Стартовый",
        "months": 1,
        "price": 200,  # цена в рублях
        "description": "1 месяц",
        "features": [
            "✅ Ежедневные персональные задания от ИИ",
            "✅ Отслеживание прогресса и статистики",
            "✅ Система уровней и рангов",
            "✅ Игровая карточка персонажа",
            "✅ Базовые призы за достижения",
            "✅ Поддержка через бота"
        ]
    },
    {
        "level": 2,
        "name": "Продвинутый",
        "months": 3,
        "price": 1200,  # цена в рублях (400₽/мес)
        "description": "3 месяца",
        "features": [
            "✅ Все преимущества Стартового уровня",
            "✅ Приоритетная поддержка",
            "✅ Расширенные призы и награды",
            "✅ Эксклюзивные задания повышенной сложности",
            "✅ Детальная аналитика прогресса",
            "✅ Участие в рейтингах и соревнованиях"
        ]
    },
    {
        "level": 3,
        "name": "Мастер",
        "months": 12,
        "price": 4000,  # цена в рублях (333₽/мес)
        "description": "12 месяцев",
        "features": [
            "✅ Все преимущества Продвинутого уровня",
            "✅ Персональные рекомендации от ИИ",
            "✅ Премиум призы и эксклюзивные награды",
            "✅ Ранний доступ к новым функциям",
            "✅ VIP статус в сообществе",
            "✅ Пожизненная приоритетная поддержка"
        ]
    },
]

# Для обратной совместимости (используется в других местах кода)
SUBSCRIPTION_PLANS = {
    level["months"]: {
        "months": level["months"],
        "price": level["price"],
        "description": level["description"]
    }
    for level in SUBSCRIPTION_LEVELS
}



# WATA API Configuration
import os
from dotenv import load_dotenv

load_dotenv()

WATA_TOKEN = os.getenv("WATA_TOKEN") or "your_wata_bearer_token_here"
#WATA_NEW_PAYMENT_LINK = "https://api.wata.pro/api/h2h/links"
WATA_NEW_PAYMENT_LINK = "https://api-sandbox.wata.pro/api/h2h/links"
#WATA_PAYMENT_LINK = "https://api.wata.pro/api/h2h/transactions/?orderId={}"
WATA_PAYMENT_LINK = "https://api-sandbox.wata.pro/api/h2h/transactions/?orderId={}"
