# Конфигурация подписок по уровням
SUBSCRIPTION_LEVELS = [
    {
        "level": 1,
        "name": "BASIC",
        "months": 1,
        "price": 1111,
        "description": "1 месяц",
        "features": [
            "✅ Ежедневные персональные задания от ИИ",
            "✅ Отслеживание прогресса и статистики",
            "✅ Система уровней и рангов",
            "✅ Игровая карточка персонажа",
            "✅ Базовые призы за достижения",
            "✅ 1 пропуск без вылета"
        ]
    },
    {
        "level": 2,
        "name": "PRIME",
        "months": 1,
        "price": 1990,
        "description": "1 месяц",
        "features": [
            "✅ Все преимущества Стартового уровня",
            "✅ Приоритетная поддержка",
            "✅ Расширенные призы и награды",
            "✅ Приоритетная проверка отчётов",
            "✅ Доступ к закрытым заметкам и гайдам от Must_Rise",
            "✅ Дополнительные подарки и бонусы внутри PRIME-группы в конце сезона",
            "✅ 2 пропуск без вылета"
        ]
    },
    {
        "level": 3,
        "name": "BASIC + PRIME",
        "months": 1,
        "price": 3500,
        "description": "1 месяц",
        "features": [
            "✅ Все преимущества Продвинутого уровня",
            "✅ Персональные рекомендации от ИИ",
            "✅ Премиум призы и эксклюзивные награды",
            "✅ Ранний доступ к новым функциям",
            "✅ VIP статус в сообществе",
            "✅ Пожизненная приоритетная поддержка",
            "✅ 3 пропуск без вылета"
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