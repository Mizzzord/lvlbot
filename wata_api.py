import aiohttp
import asyncio
import json
import datetime
import logging
import ssl
import certifi
from typing import Optional, Tuple

from subscription_config import WATA_TOKEN, WATA_NEW_PAYMENT_LINK, WATA_PAYMENT_LINK

logger = logging.getLogger(__name__)

async def wata_create_payment(
    user_mid: int,
    money: float,
    months: int,
    bot_name: str,
    created_at: int
) -> Optional[Tuple[str, str]]:
    """
    Создает платежную ссылку в WATA

    Args:
        user_mid: ID пользователя Telegram
        money: Сумма платежа
        months: Количество месяцев подписки
        bot_name: Имя бота
        created_at: Timestamp создания заказа

    Returns:
        tuple: (payment_id, payment_link) или None в случае ошибки
    """
    # Проверяем токен
    if WATA_TOKEN == "your_wata_bearer_token_here":
        logger.error("[WATA] WATA_TOKEN не настроен! Используется значение по умолчанию.")
        return None

    logger.info(f"[WATA] Создание платежа для пользователя {user_mid}, сумма {money} ₽")

    # Создаем SSL-контекст с сертификатами certifi
    ssl_context = ssl.create_default_context(cafile=certifi.where())
    connector = aiohttp.TCPConnector(ssl=ssl_context)

    async with aiohttp.ClientSession(connector=connector) as session:
        # Формируем уникальный orderId
        order_id = f"{user_mid}{created_at}"

        # Генерируем короткое имя сервиса из имени бота
        service_short = f"{bot_name[:4]}{bot_name[-4:]}" if len(bot_name) >= 4 else bot_name

        # Подготавливаем данные платежа
        payment_json = {
            "type": "OneTime",  # Одноразовая ссылка
            "amount": float(money),  # Сумма в формате float
            "currency": "RUB",
            "description": f"Подписка на {months} месяцев для пользователя {user_mid}",
            "orderId": order_id,  # ВАЖНО: уникальный ID для поиска
            "successRedirectUrl": "",
            "failRedirectUrl": "",
            "expirationDateTime": (
                datetime.datetime.now(datetime.timezone.utc) +
                datetime.timedelta(hours=1)
            ).strftime('%Y-%m-%dT%H:%M:%S.000Z')  # Ссылка истекает через 1 час
        }

        try:
            async with session.post(
                WATA_NEW_PAYMENT_LINK,
                headers={
                    'Authorization': f"Bearer {WATA_TOKEN}",
                    'Content-Type': 'application/json'
                },
                data=json.dumps(payment_json),
                timeout=aiohttp.ClientTimeout(total=10)
            ) as resp:
                response_text = await resp.text()
                logger.info(f"[WATA] Request to {WATA_NEW_PAYMENT_LINK} with data: {json.dumps(payment_json, indent=2)}")
                logger.info(f"[WATA] Response status: {resp.status}")
                logger.info(f"[WATA] Response text: {response_text}")

                if resp.ok:
                    payment_res = json.loads(response_text)
                    payment_link = payment_res["url"]  # Ссылка для оплаты
                    payment_id = payment_res["id"]  # ID платежной ссылки
                    logger.info(f"Платежная ссылка создана для пользователя {user_mid}: {payment_link}")
                    return (payment_id, payment_link)
                else:
                    try:
                        error_data = json.loads(response_text)
                        error_msg = error_data.get("error", {}).get("message", "Unknown error")
                        logger.error(f"[WATA] API Error: {error_msg}")
                    except:
                        logger.error(f"[WATA] HTTP {resp.status}: {response_text}")
                    return None

        except asyncio.TimeoutError:
            logger.error(f"[WATA] Timeout creating payment for {user_mid}")
            return None
        except Exception as e:
            logger.error(f"[WATA] Exception: {e}")
            return None

async def wata_check_payment(payment_mid: int, created_at: int) -> bool:
    """
    Проверяет статус платежа по orderId

    Args:
        payment_mid: ID пользователя (первая часть orderId)
        created_at: Timestamp (вторая часть orderId)

    Returns:
        bool: True если платеж оплачен, False в остальных случаях
    """
    # Создаем SSL-контекст с сертификатами certifi
    ssl_context = ssl.create_default_context(cafile=certifi.where())
    connector = aiohttp.TCPConnector(ssl=ssl_context)

    async with aiohttp.ClientSession(connector=connector) as session:
        # Формируем тот же orderId, что и при создании
        order_id = f"{payment_mid}{created_at}"
        check_payment_link = WATA_PAYMENT_LINK.format(order_id)

        try:
            resp = await session.get(
                check_payment_link,
                headers={
                    'Authorization': f"Bearer {WATA_TOKEN}",
                    'Content-Type': 'application/json'
                },
                timeout=aiohttp.ClientTimeout(total=10)
            )

            if resp.ok:
                transactions = await resp.json()

                # Проверяем наличие оплаченных транзакций
                for item in transactions.get("items", []):
                    if item["status"] == "Paid":
                        logger.info(f"Платеж {order_id} оплачен")
                        return True

            return False

        except Exception as e:
            logger.error(f"[wata_check_payment] Error {e} checking payment for order {order_id}")
            return False
