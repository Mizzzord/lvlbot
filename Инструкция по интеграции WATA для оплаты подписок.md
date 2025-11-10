<img src="https://r2cdn.perplexity.ai/pplx-full-logo-primary-dark%402x.png" style="height:64px;margin-right:32px"/>

# Инструкция по интеграции WATA для оплаты подписок в Telegram-боте

## Архитектура решения

Ваш текущий код уже реализует основную логику работы с WATA API. Система работает следующим образом:

**Создание платежа** → **Отправка ссылки пользователю** → **Периодическая проверка статуса** → **Активация подписки**

## Основные эндпоинты API

### 1. Создание платежной ссылки

**Endpoint:** `POST https://api.wata.pro/api/h2h/links`[^1]

**Заголовки:**[^1]

```python
headers = {
    'Authorization': f'Bearer {WATA_TOKEN}',
    'Content-Type': 'application/json'
}
```

**Тело запроса:**[^1]

```json
{
    "type": "OneTime",
    "amount": 1188.00,
    "currency": "RUB",
    "description": "string",
    "orderId": "string",
    "successRedirectUrl": "string",
    "failRedirectUrl": "string",
    "expirationDateTime": "2024-15-03T12:09:33.390Z"
}
```

**Ответ:**[^1]

```json
{
    "id": "3fa85f64-5717-4562-b3fc-2c963f66afa6",
    "type": "OneTime",
    "amount": 1188.00,
    "currency": "RUB",
    "status": "Opened",
    "url": "string",
    "terminalName": "string",
    "terminalPublicId": "3fa85f22-2108-1749-a7gj-9c134g55hkl0",
    "creationTime": "2024-12-03T12:09:33.390Z",
    "orderId": "string",
    "description": "string"
}
```


### 2. Проверка транзакций по orderId

**Endpoint:** `GET https://api.wata.pro/api/h2h/transactions/?orderId={orderId}`[^1]

**Параметры запроса:**[^1]

- `orderId` — уникальный идентификатор заказа
- `statuses` — фильтр по статусу (опционально)
- `skipCount` — пагинация (опционально)
- `maxResultCount` — количество результатов (опционально)

**Ответ:**[^1]

```json
{
    "totalCount": 1,
    "items": [
        {
            "terminalName": "string",
            "terminalPublicId": "3a16a4dd-8c83-fa4d-897a-3b334ed0ebed",
            "type": "CardCrypto",
            "amount": 1188.00,
            "currency": "RUB",
            "status": "Paid",
            "errorCode": null,
            "errorDescription": null,
            "orderId": "string",
            "orderDescription": "string",
            "creationTime": "2024-12-05T10:32:07.739314Z",
            "paymentTime": "2024-12-05T10:32:07.739314Z",
            "totalCommission": 10,
            "id": "3a16a4f0-27b0-09d1-16da-ba8d5c63eae3"
        }
    ]
}
```


## Полный код интеграции

### Шаг 1: Конфигурация

```python
import aiohttp
import json
import datetime
from enum import Enum

class PaymentGateway(Enum):
    Wata = "wata"

# config.py
WATA_TOKEN = "your_wata_bearer_token"
WATA_NEW_PAYMENT_LINK = "https://api.wata.pro/api/h2h/links"
WATA_PAYMENT_LINK = "https://api.wata.pro/api/h2h/transactions/?orderId={}"
```


### Шаг 2: Функция создания платежа

```python
async def wata_create_payment(user_mid, money, months, bot_name, created_at):
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
    async with aiohttp.ClientSession() as session:
        # Формируем уникальный orderId
        order_id = f"{user_mid}{created_at}"
        
        # Генерируем короткое имя сервиса из имени бота
        service_short = f"{bot_name[^0]}{bot_name[^4]}{bot_name[^5]}{bot_name[^3]}"
        
        # Подготавливаем данные платежа
        payment_json = {
            "type": "OneTime",  # Одноразовая ссылка
            "amount": f"{money}.00",  # Сумма в формате float
            "currency": "RUB",
            "description": f"Order for {months} months of VPN for telegram user {user_mid} and service {service_short}",
            "orderId": order_id,  # ВАЖНО: уникальный ID для поиска
            "successRedirectUrl": "",  # URL редиректа после успешной оплаты
            "failRedirectUrl": "",  # URL редиректа при ошибке
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
                data=json.dumps(payment_json)
            ) as resp:
                if resp.ok:
                    payment_res = await resp.json()
                    payment_link = payment_res["url"]  # Ссылка для оплаты
                    payment_id = payment_res["id"]  # ID платежной ссылки
                    return (payment_id, payment_link)
                else:
                    error_text = await resp.text()
                    print(f"[wata_create_payment] HTTP {resp.status}: {error_text}")
                    return None
                    
        except Exception as e:
            print(f"[wata_create_payment] Error {e} creating wata payment for {user_mid}")
            return None
```


### Шаг 3: Функция проверки статуса платежа

```python
async def wata_check_payment(payment_mid, created_at):
    """
    Проверяет статус платежа по orderId
    
    Args:
        payment_mid: ID пользователя (первая часть orderId)
        created_at: Timestamp (вторая часть orderId)
    
    Returns:
        bool: True если платеж оплачен, False в остальных случаях
    """
    async with aiohttp.ClientSession() as session:
        # Формируем тот же orderId, что и при создании
        order_id = f"{payment_mid}{created_at}"
        check_payment_link = WATA_PAYMENT_LINK.format(order_id)
        
        try:
            resp = await session.get(
                check_payment_link,
                headers={
                    'Authorization': f"Bearer {WATA_TOKEN}",
                    'Content-Type': 'application/json'
                }
            )
            
            if resp.ok:
                transactions = await resp.json()
                
                # Проверяем наличие оплаченных транзакций
                for item in transactions.get("items", []):
                    if item["status"] == "Paid":
                        return True
                        
            return False
            
        except Exception as e:
            print(f"[wata_check_payment] Error {e} checking payment for order {order_id}")
            return False
```


### Шаг 4: Интеграция в обработчик платежей

```python
async def check_payment_status(payment):
    """
    Универсальная функция проверки статуса платежа
    
    Args:
        payment: объект платежа с полями:
            - gateway: платежный шлюз
            - mid: ID пользователя
            - created_at: timestamp создания
    
    Returns:
        bool: статус оплаты
    """
    payment_success = False
    
    if payment.gateway == PaymentGateway.Wata.value:
        payment_success = await wata_check_payment(
            payment.mid,
            payment.created_at
        )
    
    return payment_success
```


### Шаг 5: Использование в Telegram-боте

```python
from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command

# Обработчик команды покупки подписки
@dp.message(Command("buy"))
async def buy_subscription_handler(message: types.Message):
    user_id = message.chat.id
    months = 1  # Количество месяцев
    price = 500  # Цена в рублях
    
    # Создаем timestamp
    now = int(datetime.datetime.now(datetime.timezone.utc).timestamp())
    
    # Создаем платеж
    result = await wata_create_payment(
        user_mid=user_id,
        money=price,
        months=months,
        bot_name=bot.user.username,
        created_at=now
    )
    
    if result:
        payment_id, payment_link = result
        
        # Сохраняем информацию о платеже в БД
        await save_payment_to_db(
            user_id=user_id,
            payment_id=payment_id,
            amount=price,
            gateway=PaymentGateway.Wata.value,
            created_at=now,
            months=months
        )
        
        # Отправляем ссылку пользователю
        await message.answer(
            f"💳 Оплатите подписку на {months} мес.\n"
            f"Сумма: {price} ₽\n\n"
            f"Ссылка для оплаты: {payment_link}\n\n"
            f"⏰ Ссылка действительна 1 час",
            reply_markup=types.InlineKeyboardMarkup(inline_keyboard=[
                [types.InlineKeyboardButton(text="Оплатить", url=payment_link)],
                [types.InlineKeyboardButton(text="Проверить оплату", callback_data=f"check_{payment_id}")]
            ])
        )
    else:
        await message.answer("❌ Ошибка создания платежа. Попробуйте позже.")


# Обработчик проверки платежа
@dp.callback_query(lambda c: c.data.startswith("check_"))
async def check_payment_handler(callback: types.CallbackQuery):
    payment_id = callback.data.replace("check_", "")
    
    # Получаем данные платежа из БД
    payment = await get_payment_from_db(payment_id)
    
    if payment:
        is_paid = await wata_check_payment(payment.mid, payment.created_at)
        
        if is_paid:
            # Активируем подписку
            await activate_subscription(payment.mid, payment.months)
            await callback.answer("✅ Оплата подтверждена! Подписка активирована.", show_alert=True)
            await callback.message.edit_text("✅ Подписка успешно активирована!")
        else:
            await callback.answer("⏳ Оплата не найдена. Попробуйте позже.", show_alert=True)
    else:
        await callback.answer("❌ Платеж не найден", show_alert=True)
```


### Шаг 6: Фоновая проверка платежей (polling)

```python
import asyncio

async def payment_polling_task():
    """
    Фоновая задача для периодической проверки неоплаченных платежей
    """
    while True:
        try:
            # Получаем все неоплаченные платежи из БД
            pending_payments = await get_pending_payments()
            
            for payment in pending_payments:
                # Проверяем статус
                is_paid = await wata_check_payment(payment.mid, payment.created_at)
                
                if is_paid:
                    # Активируем подписку
                    await activate_subscription(payment.mid, payment.months)
                    
                    # Обновляем статус в БД
                    await update_payment_status(payment.id, "paid")
                    
                    # Уведомляем пользователя
                    await bot.send_message(
                        payment.mid,
                        f"✅ Оплата на {payment.amount} ₽ подтверждена!\n"
                        f"Подписка активирована на {payment.months} мес."
                    )
                    
            # Проверяем каждые 30 секунд
            await asyncio.sleep(30)
            
        except Exception as e:
            print(f"[payment_polling_task] Error: {e}")
            await asyncio.sleep(60)

# Запуск polling при старте бота
async def on_startup():
    asyncio.create_task(payment_polling_task())
```


## Обработка ошибок

### Типичные ошибки API

**Ошибка валидации:**[^1]

```json
{
    "error": {
        "code": null,
        "message": "Ваш запрос недействителен!",
        "details": "При проверке были обнаружены следующие ошибки - 'Amount' должно быть заполнено.",
        "validationErrors": [
            {
                "message": "'Amount' должно быть заполнено.",
                "members": ["amount"]
            }
        ]
    }
}
```


### Рекомендации по обработке

```python
async def wata_create_payment_safe(user_mid, money, months, bot_name, created_at):
    """Версия с детальной обработкой ошибок"""
    
    # Валидация входных данных
    if not money or money <= 0:
        raise ValueError("Amount must be positive")
    
    if not user_mid or not created_at:
        raise ValueError("user_mid and created_at are required")
    
    async with aiohttp.ClientSession() as session:
        order_id = f"{user_mid}{created_at}"
        service_short = f"{bot_name[^0]}{bot_name[^4]}{bot_name[^5]}{bot_name[^3]}"
        
        payment_json = {
            "type": "OneTime",
            "amount": float(money),  # Убедимся что это float
            "currency": "RUB",
            "description": f"Order for {months} months of VPN for telegram user {user_mid} and service {service_short}",
            "orderId": order_id,
            "successRedirectUrl": "",
            "failRedirectUrl": "",
            "expirationDateTime": (
                datetime.datetime.now(datetime.timezone.utc) + 
                datetime.timedelta(hours=1)
            ).strftime('%Y-%m-%dT%H:%M:%S.000Z')
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
                
                if resp.ok:
                    payment_res = json.loads(response_text)
                    return (payment_res["id"], payment_res["url"])
                else:
                    try:
                        error_data = json.loads(response_text)
                        error_msg = error_data.get("error", {}).get("message", "Unknown error")
                        print(f"[WATA] API Error: {error_msg}")
                    except:
                        print(f"[WATA] HTTP {resp.status}: {response_text}")
                    return None
                    
        except asyncio.TimeoutError:
            print(f"[WATA] Timeout creating payment for {user_mid}")
            return None
        except Exception as e:
            print(f"[WATA] Exception: {e}")
            return None
```


## Важные моменты

### Формирование orderId

Ваш текущий подход `orderId = f"{user_mid}{created_at}"` работает корректно. Главное:

- **Уникальность**: каждый платеж имеет уникальный timestamp
- **Поиск**: легко найти платеж по комбинации user_id + timestamp
- **Длина**: убедитесь что строка не превышает лимиты API (обычно 255 символов)


### Статусы платежей

Возможные значения поля `status`:[^1]

- `Opened` — ссылка создана, ожидает оплаты
- `Paid` — оплачен успешно
- `Closed` — закрыт (истек срок или отменен)


### Типы платежных ссылок

- `OneTime` — одноразовая ссылка (удаляется после первой оплаты)[^1]
- `ManyTime` — многоразовая ссылка[^1]

Для подписок используйте `OneTime`.

### Время жизни ссылки

Текущая настройка — 1 час:[^1]

```python
"expirationDateTime": (datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(hours=1)).strftime('%Y-%m-%dT%H:%M:%S.000Z')
```

Можно увеличить до 24 часов для удобства пользователей:

```python
datetime.timedelta(hours=24)
```


## Webhook альтернатива

Вместо polling можно настроить webhook для получения уведомлений о платежах:[^1]

```python
from aiogram import types
import base64
from cryptography.hazmat.primitives import serialization, hashes
from cryptography.hazmat.primitives.asymmetric import padding

# Получение публичного ключа WATA
async def get_wata_public_key():
    """Получает публичный ключ для верификации webhook"""
    async with aiohttp.ClientSession() as session:
        async with session.get(
            "https://api.wata.pro/api/h2h/public-key",
            headers={'Content-Type': 'application/json'}
        ) as resp:
            if resp.ok:
                data = await resp.json()
                return data["value"]
    return None

# Верификация подписи webhook
def verify_webhook_signature(raw_json: str, signature: str, public_key_pem: str) -> bool:
    """Проверяет подпись webhook от WATA"""
    try:
        from cryptography.hazmat.backends import default_backend
        from cryptography.hazmat.primitives.serialization import load_pem_public_key
        
        # Загружаем публичный ключ
        public_key = load_pem_public_key(
            public_key_pem.encode(),
            backend=default_backend()
        )
        
        # Декодируем подпись
        signature_bytes = base64.b64decode(signature)
        
        # Проверяем подпись
        public_key.verify(
            signature_bytes,
            raw_json.encode('utf-8'),
            padding.PKCS1v15(),
            hashes.SHA512()
        )
        return True
    except Exception as e:
        print(f"Signature verification failed: {e}")
        return False

# Webhook endpoint
from aiohttp import web

async def wata_webhook_handler(request):
    """Обработчик webhook от WATA"""
    try:
        # Получаем сырые данные
        raw_body = await request.text()
        signature = request.headers.get('X-Signature')
        
        if not signature:
            return web.Response(status=400, text="Missing signature")
        
        # Получаем публичный ключ (кешируйте его!)
        public_key = await get_wata_public_key()
        
        # Проверяем подпись
        if not verify_webhook_signature(raw_body, signature, public_key):
            return web.Response(status=401, text="Invalid signature")
        
        # Парсим данные
        data = json.loads(raw_body)
        
        # Обрабатываем платеж
        if data["transactionStatus"] == "Paid":
            order_id = data["orderId"]
            
            # Находим платеж в БД
            payment = await get_payment_by_order_id(order_id)
            
            if payment and not payment.is_paid:
                # Активируем подписку
                await activate_subscription(payment.mid, payment.months)
                await update_payment_status(payment.id, "paid")
                
                # Уведомляем пользователя
                await bot.send_message(
                    payment.mid,
                    f"✅ Оплата получена! Подписка активирована на {payment.months} мес."
                )
        
        return web.Response(status=200, text="OK")
        
    except Exception as e:
        print(f"Webhook error: {e}")
        return web.Response(status=500, text="Internal error")
```


## Резюме

Ваша текущая реализация уже содержит основную логику интеграции. Для полноценной работы необходимо:

**Обязательно:**

- Сохранять информацию о платежах в базе данных
- Реализовать фоновую проверку (polling) неоплаченных платежей
- Добавить обработку ошибок и таймаутов

**Рекомендуется:**

- Настроить webhook для мгновенных уведомлений[^1]
- Добавить логирование всех запросов к API
- Реализовать повторные попытки при сетевых ошибках
- Кешировать публичный ключ для верификации webhook[^1]

**Для пользователей:**

- Отправлять уведомления о статусе платежа
- Добавить кнопку "Проверить оплату" для ручной проверки
- Показывать оставшееся время действия ссылки

<div align="center">⁂</div>

[^1]: https://wata.pro/api

