# Конфигурация подписок
SUBSCRIPTION_PLANS = {
    1: {
        "months": 1,
        "price": 200,  # цена в рублях
        "description": "1 месяц"
    },
    3: {
        "months": 3,
        "price": 1200,  # цена в рублях
        "description": "3 месяца"
    },
    6: {
        "months": 6,
        "price": 3000,  # цена в рублях
        "description": "6 месяцев"
    },
    12: {
        "months": 12,
        "price": 4000,  # цена в рублях
        "description": "12 месяцев"
    },
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
