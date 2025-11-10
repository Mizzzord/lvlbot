import asyncio
import logging
import aiohttp
import aiosqlite
import datetime
import os
from datetime import date
from PIL import Image, ImageDraw, ImageFont
import textwrap
from typing import Optional

from aiogram import Bot, Dispatcher, Router, F
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.filters import Command, CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import Message, ReplyKeyboardMarkup, KeyboardButton, ReplyKeyboardRemove, InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery, FSInputFile

from config import BOT_TOKEN
from database import Database
from models import User, Payment, PaymentStatus, Subscription, SubscriptionStatus, PlayerStats, Rank, DailyTask, UserStats, TaskStatus, Prize, PrizeType
from openrouter_config import (
    OPENROUTER_API_KEY, OPENROUTER_BASE_URL, DEFAULT_MODEL, SYSTEM_PROMPT,
    PHOTO_ANALYSIS_PROMPT, TASK_GENERATION_TEMPLATE
)
from subscription_config import SUBSCRIPTION_PLANS
from wata_api import wata_create_payment, wata_check_payment

# Настройка логирования
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Определение состояний FSM
class UserRegistration(StatesGroup):
    waiting_for_language = State()
    waiting_for_name = State()
    waiting_for_birth_date = State()
    waiting_for_height = State()
    waiting_for_weight = State()
    waiting_for_city = State()
    waiting_for_referral = State()
    waiting_for_goal = State()
    waiting_for_goal_confirmation = State()
    waiting_for_subscription = State()
    waiting_for_payment = State()
    waiting_for_player_photo = State()
    main_menu = State()
    changing_goal = State()

# Инициализация бота и диспетчера
bot = Bot(token=BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
dp = Dispatcher()
db = Database()

# Создание роутера для обработки сообщений
router = Router()

def create_cancel_keyboard() -> ReplyKeyboardMarkup:
    """Создание клавиатуры с кнопкой отмены"""
    return ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text="Отмена")]],
        resize_keyboard=True,
        one_time_keyboard=True
    )

def create_main_menu_keyboard() -> ReplyKeyboardMarkup:
    """Создание клавиатуры главного меню"""
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="🎯 Получить задание")],
            [KeyboardButton(text="📋 Активные задания")],
            [KeyboardButton(text="👤 Профиль")],
            [KeyboardButton(text="🎁 Призы")],
            [KeyboardButton(text="💬 Поддержка")]
        ],
        resize_keyboard=True,
        one_time_keyboard=False
    )

def create_language_keyboard() -> ReplyKeyboardMarkup:
    """Создание клавиатуры выбора языка"""
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="🇷🇺 Русский")],
            [KeyboardButton(text="🇺🇿 O'zbek")],
            [KeyboardButton(text="🇰🇿 Қазақ")],
            [KeyboardButton(text="🇰🇬 Кыргыз")],
            [KeyboardButton(text="🇹🇯 Тоҷики")],
            [KeyboardButton(text="🇹🇲 Türkmen")],
            [KeyboardButton(text="🇺🇦 Українська")],
            [KeyboardButton(text="🇧🇾 Беларуская")],
            [KeyboardButton(text="🇲🇩 Молдавська")],
            [KeyboardButton(text="🇦🇿 Azərbaycan")],
            [KeyboardButton(text="🇬🇪 ქართული")],
            [KeyboardButton(text="🇦🇲 Հայերեն")],
            [KeyboardButton(text="🇺🇸 English")],
            [KeyboardButton(text="Отмена")]
        ],
        resize_keyboard=True,
        one_time_keyboard=True
    )

def get_language_code(language_text: str) -> Optional[str]:
    """Преобразование текста выбора языка в код языка"""
    language_map = {
        "🇷🇺 Русский": "ru",
        "🇺🇿 O'zbek": "uz",
        "🇰🇿 Қазақ": "kk",
        "🇰🇬 Кыргыз": "ky",
        "🇹🇯 Тоҷики": "tg",
        "🇹🇲 Türkmen": "tk",
        "🇺🇦 Українська": "uk",
        "🇧🇾 Беларуская": "be",
        "🇲🇩 Молдавська": "mo",
        "🇦🇿 Azərbaycan": "az",
        "🇬🇪 ქართული": "ka",
        "🇦🇲 Հայերեն": "hy",
        "🇺🇸 English": "en"
    }
    return language_map.get(language_text)

def get_language_emoji(language_code: str) -> str:
    """Преобразование кода языка в эмодзи"""
    emoji_map = {
        "ru": "🇷🇺 Русский",
        "uz": "🇺🇿 O'zbek",
        "kk": "🇰🇿 Қазақ",
        "ky": "🇰🇬 Кыргыз",
        "tg": "🇹🇯 Тоҷики",
        "tk": "🇹🇲 Türkmen",
        "uk": "🇺🇦 Українська",
        "be": "🇧🇾 Беларуская",
        "mo": "🇲🇩 Молдавська",
        "az": "🇦🇿 Azərbaycan",
        "ka": "🇬🇪 ქართული",
        "hy": "🇦🇲 Հայերեն",
        "en": "🇺🇸 English"
    }
    return emoji_map.get(language_code, language_code)

async def improve_goal_with_ai(goal: str) -> str:
    """Улучшает формулировку цели с помощью OpenRouter API"""
    try:
        import ssl
        import certifi

        # Создаем SSL-контекст с сертификатами certifi
        ssl_context = ssl.create_default_context(cafile=certifi.where())
        connector = aiohttp.TCPConnector(ssl=ssl_context)

        async with aiohttp.ClientSession(connector=connector) as session:
            payload = {
                "model": DEFAULT_MODEL,
                "messages": [
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": f"Улучши формулировку этой цели: {goal}"}
                ],
                "max_tokens": 500,
                "temperature": 0.7
            }

            headers = {
                "Authorization": f"Bearer {OPENROUTER_API_KEY}",
                "Content-Type": "application/json",
                "HTTP-Referer": "https://t.me/motivation_bot",
                "X-Title": "Motivation Bot"
            }

            async with session.post(
                f"{OPENROUTER_BASE_URL}/chat/completions",
                json=payload,
                headers=headers
            ) as response:
                if response.status == 200:
                    data = await response.json()
                    improved_goal = data["choices"][0]["message"]["content"].strip()
                    return improved_goal
                else:
                    logger.error(f"OpenRouter API error: {response.status}")
                    return goal  # Возвращаем оригинальную цель в случае ошибки

    except Exception as e:
        logger.error(f"Error calling OpenRouter API: {e}")
        return goal  # Возвращаем оригинальную цель в случае ошибки

async def skip_payment_process(callback: CallbackQuery, state: FSMContext):
    """Обработка пропуска оплаты (тестовый режим)"""
    user_id = callback.from_user.id

    # Создаем тестовую подписку на 30 дней
    current_time = int(datetime.datetime.now().timestamp())
    test_subscription_end = current_time + (30 * 24 * 60 * 60)  # 30 дней

    # Создаем тестовый платеж в базе данных
    test_payment = Payment(
        user_id=user_id,
        payment_id="test_payment_skip",
        order_id=f"test_{user_id}_{current_time}",
        amount=0.0,
        months=1,
        status=PaymentStatus.PAID,
        created_at=current_time,
        paid_at=current_time,
        currency="RUB",
        payment_method="TEST",
        subscription_type="standard"
    )

    payment_id = await db.save_payment(test_payment)

    # Создаем подписку
    test_subscription = Subscription(
        user_id=user_id,
        payment_id=payment_id,
        start_date=current_time,
        end_date=test_subscription_end,
        months=1,
        status=SubscriptionStatus.ACTIVE,
        auto_renew=False,
        created_at=current_time,
        updated_at=current_time
    )

    subscription_id = await db.save_subscription(test_subscription)

    # Активируем подписку пользователя
    await db.activate_user_subscription(user_id, current_time, test_subscription_end)

    logger.info(f"Тестовая подписка создана для пользователя {user_id}, subscription_id: {subscription_id}")

    # Переходим к созданию карточки игрока
    await state.set_state(UserRegistration.waiting_for_player_photo)

    await callback.message.edit_text(
        f"🧪 <b>Тестовый режим активирован!</b>\n\n"
        f"✅ Бесплатная подписка на 30 дней активирована!\n\n"
        f"📅 Дата окончания: {datetime.datetime.fromtimestamp(test_subscription_end).strftime('%d.%m.%Y')}\n\n"
        f"🎮 <b>Обязательный этап: Создание карточки игрока</b>\n\n"
        f"📸 Пожалуйста, загрузите ваше фото для создания игровой карточки.\n"
        f"ИИ проанализирует ваше фото и определит стартовые характеристики:\n"
        f"• 💪 Сила\n"
        f"• 🤸 Ловкость\n"
        f"• 🏃 Выносливость\n"
        f"• 🧠 Интеллект (базовый: 50/100)\n"
        f"• ✨ Харизма (базовый: 50/100)\n\n"
        f"После анализа будет создана ваша уникальная игровая карточка!",
        parse_mode="HTML",
        reply_markup=None
    )

async def show_main_menu(message: Message):
    """Показать главное меню пользователя"""
    keyboard = create_main_menu_keyboard()

    await message.answer(
        "🎮 <b>Главное меню</b>\n\n"
        "Выберите действие:",
        parse_mode="HTML",
        reply_markup=keyboard
    )

async def analyze_player_photo(photo_bytes: bytes) -> dict:
    """
    Анализирует фото игрока и определяет статы: сила, ловкость, выносливость

    Args:
        photo_bytes: Байты изображения

    Returns:
        dict: {'strength': int, 'agility': int, 'endurance': int}
    """
    try:
        import ssl
        import certifi
        import base64

        # Создаем SSL-контекст с сертификатами certifi
        ssl_context = ssl.create_default_context(cafile=certifi.where())
        connector = aiohttp.TCPConnector(ssl=ssl_context)

        # Конвертируем изображение в base64
        image_base64 = base64.b64encode(photo_bytes).decode('utf-8')

        analysis_prompt = PHOTO_ANALYSIS_PROMPT

        async with aiohttp.ClientSession(connector=connector) as session:
            payload = {
                "model": "openrouter/polaris-alpha",  # Используем модель с поддержкой изображений
                "messages": [
                    {"role": "system", "content": analysis_prompt},
                    {
                        "role": "user",
                        "content": [
                            {"type": "text", "text": "Оцени физические характеристики этого человека:"},
                            {
                                "type": "image_url",
                                "image_url": {
                                    "url": f"data:image/jpeg;base64,{image_base64}"
                                }
                            }
                        ]
                    }
                ],
                "max_tokens": 200,
                "temperature": 0.3
            }

            headers = {
                "Authorization": f"Bearer {OPENROUTER_API_KEY}",
                "Content-Type": "application/json",
                "HTTP-Referer": "https://t.me/motivation_bot",
                "X-Title": "Motivation Bot"
            }

            async with session.post(
                f"{OPENROUTER_BASE_URL}/chat/completions",
                json=payload,
                headers=headers
            ) as response:
                if response.status == 200:
                    data = await response.json()
                    result_text = data["choices"][0]["message"]["content"].strip()

                    # Парсим JSON из ответа
                    try:
                        import json
                        stats = json.loads(result_text)

                        # Валидируем и нормализуем значения
                        strength = max(1, min(100, int(stats.get('strength', 50))))
                        agility = max(1, min(100, int(stats.get('agility', 50))))
                        endurance = max(1, min(100, int(stats.get('endurance', 50))))

                        return {
                            'strength': strength,
                            'agility': agility,
                            'endurance': endurance
                        }
                    except (json.JSONDecodeError, KeyError, ValueError) as e:
                        logger.error(f"Ошибка парсинга ответа ИИ: {e}, ответ: {result_text}")
                        # Возвращаем значения по умолчанию
                        return {'strength': 50, 'agility': 50, 'endurance': 50}
                else:
                    logger.error(f"OpenRouter API error: {response.status}")
                    return {'strength': 50, 'agility': 50, 'endurance': 50}

    except Exception as e:
        logger.error(f"Error analyzing player photo: {e}")
        return {'strength': 50, 'agility': 50, 'endurance': 50}

async def create_player_card_image(photo_path: str, nickname: str, experience: int, stats: dict) -> str:
    """
    Создает изображение карточки игрока

    Args:
        photo_path: путь к фото пользователя
        nickname: ник игрока
        experience: опыт игрока
        stats: словарь с характеристиками

    Returns:
        str: путь к созданному изображению карточки
    """
    try:
        # Размеры карточки
        card_width = 800
        card_height = 1200

        # Создаем новое изображение
        card = Image.new('RGB', (card_width, card_height), (30, 30, 46))  # Темно-синий фон
        draw = ImageDraw.Draw(card)

        # Загружаем фото пользователя
        try:
            user_photo = Image.open(photo_path)
            # Изменяем размер фото под аватар (круглый)
            avatar_size = 200
            user_photo = user_photo.resize((avatar_size, avatar_size), Image.Resampling.LANCZOS)

            # Создаем маску для круглого аватара
            mask = Image.new('L', (avatar_size, avatar_size), 0)
            mask_draw = ImageDraw.Draw(mask)
            mask_draw.ellipse((0, 0, avatar_size, avatar_size), fill=255)

            # Создаем круглый аватар
            avatar = Image.new('RGBA', (avatar_size, avatar_size), (0, 0, 0, 0))
            avatar.paste(user_photo, (0, 0), mask)

            # Добавляем аватар на карточку
            avatar_x = (card_width - avatar_size) // 2
            avatar_y = 50
            card.paste(avatar, (avatar_x, avatar_y), avatar)

        except Exception as e:
            logger.warning(f"Не удалось загрузить фото пользователя: {e}")
            # Создаем placeholder для аватара
            avatar_x = (card_width - 200) // 2
            avatar_y = 50
            draw.rectangle([avatar_x, avatar_y, avatar_x + 200, avatar_y + 200],
                         fill=(100, 100, 100), outline=(255, 255, 255), width=3)

        # Цвета для дизайна
        primary_color = (147, 112, 219)  # Medium Purple
        secondary_color = (255, 215, 0)  # Gold
        text_color = (255, 255, 255)     # White
        stat_color = (176, 196, 222)     # Light Steel Blue

        # Заголовок "ИГРОВАЯ КАРТОЧКА"
        title_font_size = 48
        try:
            title_font = ImageFont.truetype("/System/Library/Fonts/Arial.ttf", title_font_size)
        except:
            title_font = ImageFont.load_default()

        title_text = "ИГРОВАЯ КАРТОЧКА"
        title_bbox = draw.textbbox((0, 0), title_text, font=title_font)
        title_width = title_bbox[2] - title_bbox[0]
        title_x = (card_width - title_width) // 2
        title_y = 280

        # Градиентная рамка для заголовка
        draw.rectangle([title_x - 20, title_y - 10, title_x + title_width + 20, title_y + title_font_size + 10],
                     fill=primary_color, outline=secondary_color, width=3)
        draw.text((title_x, title_y), title_text, font=title_font, fill=text_color)

        # Ник игрока
        nick_font_size = 36
        try:
            nick_font = ImageFont.truetype("/System/Library/Fonts/Arial.ttf", nick_font_size)
        except:
            nick_font = ImageFont.load_default()

        nick_y = title_y + 80
        draw.text((card_width // 2, nick_y), nickname, font=nick_font, fill=secondary_color, anchor="mm")

        # Опыт
        exp_font_size = 24
        try:
            exp_font = ImageFont.truetype("/System/Library/Fonts/Arial.ttf", exp_font_size)
        except:
            exp_font = ImageFont.load_default()

        exp_text = f"⭐ Опыт: {experience}"
        exp_bbox = draw.textbbox((0, 0), exp_text, font=exp_font)
        exp_width = exp_bbox[2] - exp_bbox[0]
        exp_x = (card_width - exp_width) // 2
        exp_y = nick_y + 50
        draw.text((exp_x, exp_y), exp_text, font=exp_font, fill=text_color)

        # Характеристики
        stat_font_size = 28
        try:
            stat_font = ImageFont.truetype("/System/Library/Fonts/Arial.ttf", stat_font_size)
        except:
            stat_font = ImageFont.load_default()

        stat_names = {
            'strength': '💪 Сила',
            'agility': '🤸 Ловкость',
            'endurance': '🏃 Выносливость',
            'intelligence': '🧠 Интеллект',
            'charisma': '✨ Харизма'
        }

        start_y = exp_y + 80
        bar_width = 300
        bar_height = 25
        spacing = 50

        for i, (stat_key, stat_name) in enumerate(stat_names.items()):
            stat_value = stats[stat_key]

            # Название характеристики
            stat_y = start_y + i * spacing
            draw.text((150, stat_y), f"{stat_name}:", font=stat_font, fill=text_color, anchor="lm")

            # Значение характеристики
            value_text = f"{stat_value}/100"
            draw.text((card_width - 150, stat_y), value_text, font=stat_font, fill=secondary_color, anchor="rm")

            # Полоса прогресса
            bar_x = 150
            bar_y = stat_y + 30

            # Фон полосы
            draw.rectangle([bar_x, bar_y, bar_x + bar_width, bar_y + bar_height],
                         fill=(50, 50, 50), outline=stat_color, width=2)

            # Заполнение полосы
            fill_width = int(bar_width * stat_value / 100)
            if fill_width > 0:
                color_intensity = min(255, int(100 + stat_value * 1.55))  # Более яркий цвет для высоких значений
                fill_color = (color_intensity, 100, 255 - stat_value) if stat_value > 50 else (255 - stat_value * 2, color_intensity, 100)
                draw.rectangle([bar_x + 2, bar_y + 2, bar_x + fill_width - 2, bar_y + bar_height - 2],
                             fill=fill_color)

        # Нижний декор
        footer_y = card_height - 100
        footer_text = "© Motivation Bot"
        footer_font_size = 20
        try:
            footer_font = ImageFont.truetype("/System/Library/Fonts/Arial.ttf", footer_font_size)
        except:
            footer_font = ImageFont.load_default()

        footer_bbox = draw.textbbox((0, 0), footer_text, font=footer_font)
        footer_width = footer_bbox[2] - footer_bbox[0]
        footer_x = (card_width - footer_width) // 2
        draw.text((footer_x, footer_y), footer_text, font=footer_font, fill=(150, 150, 150))

        # Сохраняем карточку
        cards_dir = "player_cards"
        os.makedirs(cards_dir, exist_ok=True)

        card_filename = f"{cards_dir}/card_{nickname}_{int(datetime.datetime.now().timestamp())}.png"
        card.save(card_filename, 'PNG')

        logger.info(f"Карточка игрока создана: {card_filename}")
        return card_filename

    except Exception as e:
        logger.error(f"Ошибка создания карточки игрока: {e}")
        return None

def create_goal_confirmation_keyboard() -> InlineKeyboardMarkup:
    """Создание inline клавиатуры для подтверждения цели"""
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="✅ Я уверен", callback_data="goal_confirm"),
                InlineKeyboardButton(text="🤖 ИИ улучшение", callback_data="goal_improve")
            ],
            [
                InlineKeyboardButton(text="✏️ Изменить", callback_data="goal_edit")
            ]
        ]
    )

def create_subscription_keyboard() -> InlineKeyboardMarkup:
    """Создание inline клавиатуры для выбора подписки"""
    keyboard = []
    for months, plan in SUBSCRIPTION_PLANS.items():
        keyboard.append([
            InlineKeyboardButton(
                text=f"{plan['description']} - {plan['price']} ₽",
                callback_data=f"sub_{months}"
            )
        ])

    # Добавляем кнопку "Пропустить оплату" (для тестирования)
    keyboard.append([
        InlineKeyboardButton(
            text="⏭️ Пропустить оплату (тест)",
            callback_data="skip_payment"
        )
    ])

    return InlineKeyboardMarkup(inline_keyboard=keyboard)

def validate_date(date_str: str) -> Optional[date]:
    """Валидация даты рождения в формате ДД.ММ.ГГГГ"""
    try:
        day, month, year = map(int, date_str.split('.'))
        return date(year, month, day)
    except (ValueError, TypeError):
        return None

def validate_height(height_str: str) -> Optional[float]:
    """Валидация роста (в см)"""
    try:
        height = float(height_str.replace(',', '.'))
        if 50 <= height <= 250:  # разумные пределы
            return height
        return None
    except ValueError:
        return None

def validate_weight(weight_str: str) -> Optional[float]:
    """Валидация веса (в кг)"""
    try:
        weight = float(weight_str.replace(',', '.'))
        if 3 <= weight <= 300:  # разумные пределы
            return weight
        return None
    except ValueError:
        return None

@router.message(CommandStart())
async def cmd_start(message: Message, state: FSMContext):
    """Обработчик команды /start"""
    telegram_id = message.from_user.id

    # Проверяем, есть ли уже пользователь в базе
    existing_user = await db.get_user(telegram_id)

    if existing_user and existing_user.is_complete:
        # Пользователь уже зарегистрирован
        language_emoji = get_language_emoji(existing_user.language)
        referral_text = f"📢 Реферальный код: {existing_user.referral_code}\n" if existing_user.referral_code else ""
        goal_text = f"🎯 Цель: {existing_user.goal}\n" if existing_user.goal else ""

        # Проверяем статус подписки
        subscription_text = ""
        if existing_user.subscription_active and existing_user.subscription_end:
            end_date = datetime.datetime.fromtimestamp(existing_user.subscription_end).strftime('%d.%m.%Y')
            subscription_text = f"💎 Подписка активна до {end_date}\n"
        else:
            subscription_text = "💎 Подписка: Не активна\n"

        # Проверяем, есть ли карточка игрока
        player_stats = await db.get_player_stats(telegram_id)

        if player_stats:
            # У пользователя есть карточка игрока - показываем главное меню
            user_statistics = await db.get_user_stats(telegram_id)
            await message.answer(
                f"С возвращением, {existing_user.name}! 👋\n\n"
                f"🎮 Ваша игровая карточка активна!\n\n"
                f"🏆 Ник: {player_stats.nickname} | ⭐ Опыт: {user_statistics.experience if user_statistics else 0}\n"
                f"📊 Уровень: {user_statistics.level if user_statistics else 1} | 🏅 Ранг: {user_statistics.rank.value if user_statistics else 'F'}\n\n"
                f"Готов продолжить приключения?",
                parse_mode="HTML"
            )
            await state.set_state(UserRegistration.main_menu)
            await show_main_menu(message)
        else:
            # У пользователя нет карточки - показываем обычное приветствие
            stats_text = ""
            if player_stats:
                stats_text = (
                    f"🎮 <b>Карточка игрока: {player_stats.nickname}</b>\n"
                    f"⭐ Опыт: {player_stats.experience}\n\n"
                    f"🏆 <b>Характеристики:</b>\n"
                    f"💪 Сила: {player_stats.strength}/100\n"
                    f"🤸 Ловкость: {player_stats.agility}/100\n"
                    f"🏃 Выносливость: {player_stats.endurance}/100\n"
                    f"🧠 Интеллект: {player_stats.intelligence}/100\n"
                    f"✨ Харизма: {player_stats.charisma}/100\n"
                )

            await message.answer(
                f"С возвращением, {existing_user.name}! 👋\n\n"
                f"Ты уже в нашей команде изменений!\n\n"
                f"🌐 Язык: {language_emoji}\n"
                f"👤 Имя: {existing_user.name}\n"
                f"📅 Дата рождения: {existing_user.birth_date.strftime('%d.%m.%Y') if existing_user.birth_date else 'Не указана'}\n"
                f"📏 Рост: {existing_user.height} см\n"
                f"⚖️ Вес: {existing_user.weight} кг\n"
                f"🏙️ Город: {existing_user.city}\n"
                f"{referral_text}"
                f"{goal_text}"
                f"{subscription_text}"
                f"{stats_text}\n"
                f"Готов продолжить путь к целям? Используй /update для обновления данных.",
                parse_mode="HTML"
            )
    else:
        # Получаем имя пользователя из Telegram
        user_name = message.from_user.first_name or "друг"

        # Отправляем приветственное мотивационное сообщение
        await message.answer(
            f"Привет, {user_name}! 👋 Я — твой личный мотивационный бот, созданный, чтобы помочь достигать целей шаг за шагом. Каждый день я буду предлагать простые, но эффективные задания, адаптированные под твои цели — будь то фитнес, обучение, карьера или хобби. Просто расскажи о своей цели, и мы начнём! Готов к изменениям?"
        )

        # Начинаем регистрацию с выбора языка
        await state.set_state(UserRegistration.waiting_for_language)
        await message.answer(
            "🤖 Для начала давайте настроим бота под вас.\n\n"
            "Выберите удобный язык:",
            reply_markup=create_language_keyboard()
        )

@router.message(UserRegistration.waiting_for_language)
async def process_language(message: Message, state: FSMContext):
    """Обработка выбора языка"""
    language_code = get_language_code(message.text.strip())

    if language_code is None:
        await message.answer(
            "Пожалуйста, выберите язык из предложенных вариантов:",
            reply_markup=create_language_keyboard()
        )
        return

    # Сохраняем язык во временном состоянии
    await state.update_data(language=language_code)

    telegram_id = message.from_user.id
    user = await db.get_user(telegram_id) or User(telegram_id=telegram_id)
    user.language = language_code
    await db.save_user(user)

    await state.set_state(UserRegistration.waiting_for_name)
    await message.answer(
        f"Отлично! Вы выбрали язык: {get_language_emoji(language_code)}\n\n"
        "Теперь введите ваше имя:",
        reply_markup=create_cancel_keyboard()
    )

@router.message(Command("cancel"))
@router.message(F.text.lower() == "отмена")
async def cmd_cancel(message: Message, state: FSMContext):
    """Обработчик отмены"""
    current_state = await state.get_state()
    if current_state is not None:
        await state.clear()
        await message.answer(
            "Регистрация отменена.",
            reply_markup=ReplyKeyboardRemove()
        )
    else:
        await message.answer("Нет активной регистрации для отмены.")

@router.message(Command("update"))
async def cmd_update(message: Message, state: FSMContext):
    """Обработчик команды обновления данных"""
    telegram_id = message.from_user.id
    existing_user = await db.get_user(telegram_id)

    if existing_user:
        # Если язык еще не выбран, начинаем с выбора языка
        if not existing_user.language:
            await state.set_state(UserRegistration.waiting_for_language)
            await message.answer(
                "Давайте обновим ваши данные.\n"
                "Для начала выберите удобный язык:",
                reply_markup=create_language_keyboard()
            )
        else:
            await state.set_state(UserRegistration.waiting_for_name)
            await message.answer(
                "Давайте обновим ваши данные.\n\n"
                "Введите ваше имя:",
                reply_markup=create_cancel_keyboard()
            )
    else:
        await message.answer("Сначала зарегистрируйтесь с помощью /start")

@router.message(UserRegistration.waiting_for_name)
async def process_name(message: Message, state: FSMContext):
    """Обработка имени пользователя"""
    name = message.text.strip()

    if len(name) < 2:
        await message.answer("Имя должно содержать минимум 2 символа. Попробуйте еще раз:")
        return

    # Сохраняем имя во временном состоянии
    await state.update_data(name=name)

    telegram_id = message.from_user.id
    user = await db.get_user(telegram_id) or User(telegram_id=telegram_id)
    user.name = name
    await db.save_user(user)

    await state.set_state(UserRegistration.waiting_for_birth_date)
    await message.answer(
        f"Отлично, {name}!\n\n"
        "Теперь введите вашу дату рождения в формате ДД.ММ.ГГГГ\n"
        "(например: 15.05.1990):",
        reply_markup=create_cancel_keyboard()
    )

@router.message(UserRegistration.waiting_for_birth_date)
async def process_birth_date(message: Message, state: FSMContext):
    """Обработка даты рождения"""
    date_str = message.text.strip()
    birth_date = validate_date(date_str)

    if birth_date is None:
        await message.answer(
            "Неверный формат даты. Используйте формат ДД.ММ.ГГГГ\n"
            "(например: 15.05.1990):"
        )
        return

    # Проверяем, что дата не в будущем и не слишком старая
    today = date.today()
    if birth_date > today:
        await message.answer("Дата рождения не может быть в будущем. Попробуйте еще раз:")
        return

    age = today.year - birth_date.year - ((today.month, today.day) < (birth_date.month, birth_date.day))
    if age < 10 or age > 120:
        await message.answer("Пожалуйста, введите реальную дату рождения. Попробуйте еще раз:")
        return

    # Сохраняем дату рождения
    await state.update_data(birth_date=birth_date)

    telegram_id = message.from_user.id
    user = await db.get_user(telegram_id)
    if user:
        user.birth_date = birth_date
        await db.save_user(user)

    await state.set_state(UserRegistration.waiting_for_height)
    await message.answer(
        f"Дата рождения сохранена: {birth_date.strftime('%d.%m.%Y')}\n\n"
        "Теперь введите ваш рост в сантиметрах (например: 175):",
        reply_markup=create_cancel_keyboard()
    )

@router.message(UserRegistration.waiting_for_height)
async def process_height(message: Message, state: FSMContext):
    """Обработка роста"""
    height_str = message.text.strip()
    height = validate_height(height_str)

    if height is None:
        await message.answer(
            "Неверное значение роста. Введите число от 50 до 250 см\n"
            "(например: 175):"
        )
        return

    # Сохраняем рост
    await state.update_data(height=height)

    telegram_id = message.from_user.id
    user = await db.get_user(telegram_id)
    if user:
        user.height = height
        await db.save_user(user)

    await state.set_state(UserRegistration.waiting_for_weight)
    await message.answer(
        f"Рост сохранен: {height} см\n\n"
        "Теперь введите ваш вес в килограммах (например: 70.5):",
        reply_markup=create_cancel_keyboard()
    )

@router.message(UserRegistration.waiting_for_weight)
async def process_weight(message: Message, state: FSMContext):
    """Обработка веса"""
    weight_str = message.text.strip()
    weight = validate_weight(weight_str)

    if weight is None:
        await message.answer(
            "Неверное значение веса. Введите число от 3 до 300 кг\n"
            "(например: 70.5):"
        )
        return

    # Сохраняем вес
    await state.update_data(weight=weight)

    telegram_id = message.from_user.id
    user = await db.get_user(telegram_id)
    if user:
        user.weight = weight
        await db.save_user(user)

    await state.set_state(UserRegistration.waiting_for_city)
    await message.answer(
        f"Вес сохранен: {weight} кг\n\n"
        "Наконец, введите ваш город:",
        reply_markup=create_cancel_keyboard()
    )

@router.message(UserRegistration.waiting_for_city)
async def process_city(message: Message, state: FSMContext):
    """Обработка города"""
    city = message.text.strip()

    if len(city) < 2:
        await message.answer("Название города должно содержать минимум 2 символа. Попробуйте еще раз:")
        return

    # Сохраняем город
    await state.update_data(city=city)

    telegram_id = message.from_user.id
    user = await db.get_user(telegram_id)
    if user:
        user.city = city
        await db.save_user(user)

    await state.set_state(UserRegistration.waiting_for_referral)
    await message.answer(
        f"Город сохранен: {city}\n\n"
        "📢 Откуда вы узнали о нашем боте? Если у вас есть реферальный код блогера, "
        "введите его. Если нет - просто нажмите 'Пропустить':",
        reply_markup=ReplyKeyboardMarkup(
            keyboard=[[KeyboardButton(text="Пропустить")]],
            resize_keyboard=True,
            one_time_keyboard=True
        )
    )

@router.message(UserRegistration.waiting_for_referral)
async def process_referral(message: Message, state: FSMContext):
    """Обработка реферального кода"""
    referral_code = message.text.strip()

    if referral_code.lower() == "пропустить":
        referral_code = None

    # Сохраняем реферальный код (или None)
    await state.update_data(referral_code=referral_code)

    telegram_id = message.from_user.id
    user = await db.get_user(telegram_id)
    if user:
        user.referral_code = referral_code
        await db.save_user(user)

    await state.set_state(UserRegistration.waiting_for_goal)
    await message.answer(
        "Спасибо за информацию!\n\n"
        "🎯 Теперь расскажите о вашей главной цели! Что вы хотите достичь?\n"
        "(например: накачаться, научиться программированию, похудеть, "
        "научиться английскому, развить уверенность в себе и т.д.)",
        reply_markup=ReplyKeyboardRemove()
    )

@router.message(UserRegistration.waiting_for_goal)
async def process_goal(message: Message, state: FSMContext):
    """Обработка цели пользователя"""
    goal = message.text.strip()
    user_id = message.from_user.id

    if len(goal) < 3:
        await message.answer(
            "Пожалуйста, опишите вашу цель более подробно (минимум 3 символа):"
        )
        return

    logger.info(f"Пользователь {user_id} ввел цель: '{goal}'")

    # Сохраняем цель во временном состоянии
    await state.update_data(goal=goal)
    await state.set_state(UserRegistration.waiting_for_goal_confirmation)

    await message.answer(
        f"🎯 Ваша цель:\n\n<i>{goal}</i>\n\n"
        f"Уверены ли вы в этой формулировке?",
        reply_markup=create_goal_confirmation_keyboard()
    )

@router.callback_query(UserRegistration.waiting_for_goal_confirmation)
async def process_goal_confirmation(callback: CallbackQuery, state: FSMContext):
    """Обработка подтверждения цели"""
    await callback.answer()  # Убираем часики загрузки

    action = callback.data
    user_id = callback.from_user.id
    logger.info(f"process_goal_confirmation: callback.from_user.id = {user_id}, action = {action}")

    if action == "goal_confirm":
        # Пользователь подтвердил цель - завершаем регистрацию
        logger.info(f"Пользователь {user_id} подтвердил цель, завершаем регистрацию")
        await finalize_registration(callback.message, state, user_id)

    elif action == "goal_improve":
        # Улучшаем цель с помощью ИИ
        logger.info(f"Пользователь {user_id} выбрал улучшение цели ИИ")
        data = await state.get_data()
        original_goal = data.get('goal', '')

        # Отправляем сообщение о том, что ИИ работает
        await callback.message.edit_text(
            f"🎯 Ваша цель:\n\n<i>{original_goal}</i>\n\n"
            f"🤖 Улучшаю формулировку с помощью ИИ...",
            reply_markup=None
        )

        # Вызываем OpenRouter API
        improved_goal = await improve_goal_with_ai(original_goal)
        logger.info(f"Цель улучшена ИИ для пользователя {user_id}: '{original_goal}' -> '{improved_goal}'")

        # Сохраняем улучшенную цель
        await state.update_data(goal=improved_goal)

        # Показываем улучшенную цель с той же клавиатурой
        await callback.message.edit_text(
            f"🎯 Улучшенная цель:\n\n<i>{improved_goal}</i>\n\n"
            f"Теперь лучше звучит? Что скажете?",
            reply_markup=create_goal_confirmation_keyboard()
        )

    elif action == "goal_edit":
        # Возвращаемся к вводу цели
        logger.info(f"Пользователь {user_id} выбрал редактирование цели")
        await state.set_state(UserRegistration.waiting_for_goal)
        await callback.message.edit_text(
            "🎯 Хорошо, давайте переформулируем цель.\n\n"
            "Расскажите о вашей главной цели:",
            reply_markup=None
        )

async def finalize_registration(message: Message, state: FSMContext, user_id: int = None):
    """Завершение регистрации пользователя"""
    data = await state.get_data()
    telegram_id = user_id if user_id else message.from_user.id
    logger.info(f"Завершение регистрации пользователя {telegram_id}. Данные состояния: {data}")

    # Сохраняем данные в базу
    user = await db.get_user(telegram_id)
    if user:
        goal = data.get('goal')
        logger.info(f"Извлечена цель из состояния: '{goal}'")
        if goal and len(goal.strip()) > 0:
            user.goal = goal.strip()
            logger.info(f"Сохраняем цель пользователя {telegram_id}: '{user.goal}'")
            await db.save_user(user)

            # Проверяем, что цель действительно сохранилась
            saved_user = await db.get_user(telegram_id)
            if saved_user and saved_user.goal:
                logger.info(f"Цель успешно сохранена в БД: '{saved_user.goal}'")
            else:
                logger.error(f"Ошибка: цель не сохранилась в БД для пользователя {telegram_id}")
        else:
            logger.warning(f"Цель пользователя {telegram_id} пустая или не установлена: '{goal}'")
    else:
        logger.error(f"Пользователь {telegram_id} не найден при завершении регистрации")
        # Попробуем создать пользователя, если он не существует
        logger.info(f"Пытаемся создать пользователя {telegram_id}")
        user = User(telegram_id=telegram_id)
        goal = data.get('goal')
        if goal and len(goal.strip()) > 0:
            user.goal = goal.strip()
        # Заполняем остальные поля из состояния
        user.language = data.get('language')
        user.name = data.get('name')
        user.birth_date = data.get('birth_date')
        user.height = data.get('height')
        user.weight = data.get('weight')
        user.city = data.get('city')
        user.referral_code = data.get('referral_code')
        await db.save_user(user)
        logger.info(f"Пользователь {telegram_id} создан при завершении регистрации")

    # Получаем все данные для финального сообщения
    name = data.get('name', 'Пользователь')
    language = data.get('language', 'ru')
    referral_code = data.get('referral_code')

    # Очищаем состояние
    await state.clear()

    referral_text = f"📢 Реферальный код: {referral_code}\n" if referral_code else ""

    await message.edit_text(
        f"🎉 Отлично! Регистрация завершена!\n\n"
        f"🌐 Язык: {get_language_emoji(language)}\n"
        f"👤 Имя: {name}\n"
        f"📅 Дата рождения: {data.get('birth_date').strftime('%d.%m.%Y') if data.get('birth_date') else 'Не указана'}\n"
        f"📏 Рост: {data.get('height')} см\n"
        f"⚖️ Вес: {data.get('weight')} кг\n"
        f"🏙️ Город: {data.get('city')}\n"
        f"{referral_text}"
        f"🎯 Цель: {data.get('goal')}\n\n"
        f"💳 Теперь выберите период подписки для доступа к персональным заданиям:",
        reply_markup=create_subscription_keyboard()
    )

    # Переходим к выбору подписки
    await state.set_state(UserRegistration.waiting_for_subscription)

@router.callback_query(UserRegistration.waiting_for_subscription)
async def process_subscription_choice(callback: CallbackQuery, state: FSMContext):
    """Обработка выбора периода подписки"""
    await callback.answer()

    # Проверяем, если это пропуск оплаты
    if callback.data == "skip_payment":
        await skip_payment_process(callback, state)
        return

    # Получаем выбранный период из callback_data (sub_1, sub_3, etc.)
    months = int(callback.data.replace("sub_", ""))

    if months not in SUBSCRIPTION_PLANS:
        await callback.answer("Неверный выбор периода подписки", show_alert=True)
        return

    plan = SUBSCRIPTION_PLANS[months]
    user_id = callback.from_user.id

    # Создаем timestamp
    now = int(datetime.datetime.now(datetime.timezone.utc).timestamp())

    # Получаем информацию о боте
    bot_info = await bot.get_me()
    bot_name = bot_info.username or "MotivationBot"

    # Создаем платеж через WATA API
    result = await wata_create_payment(
        user_mid=user_id,
        money=plan['price'],
        months=months,
        bot_name=bot_name,
        created_at=now
    )

    if result:
        payment_id, payment_link = result

        # Сохраняем информацию о платеже в БД
        payment = Payment(
            user_id=user_id,
            payment_id=payment_id,
            order_id=f"{user_id}{now}",
            amount=plan['price'],
            months=months,
            status=PaymentStatus.PENDING,
            created_at=now,
            currency="RUB",
            payment_method="WATA",
            subscription_type="standard"
        )

        payment_db_id = await db.save_payment(payment)

        # Отправляем пользователю ссылку на оплату
        await callback.message.edit_text(
            f"💳 Подписка на {plan['description']}\n"
            f"💰 Стоимость: {plan['price']} ₽\n\n"
            f"Ссылка для оплаты: {payment_link}\n\n"
            f"⏰ Ссылка действительна 1 час",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="💳 Оплатить", url=payment_link)],
                [InlineKeyboardButton(text="🔄 Проверить оплату", callback_data=f"check_payment_{payment_db_id}")]
            ])
        )

        # Переходим к состоянию ожидания оплаты
        await state.set_state(UserRegistration.waiting_for_payment)
        await state.update_data(current_payment_id=payment_db_id)

    else:
        await callback.message.edit_text(
            "❌ Ошибка создания платежа. Попробуйте позже или обратитесь в поддержку.",
            reply_markup=None
        )

@router.callback_query(UserRegistration.waiting_for_payment, lambda c: c.data.startswith("check_payment_"))
async def check_payment_callback(callback: CallbackQuery, state: FSMContext):
    """Обработка проверки оплаты"""
    await callback.answer()

    payment_db_id = int(callback.data.replace("check_payment_", ""))
    logger.info(f"Проверка платежа ID: {payment_db_id} для пользователя {callback.from_user.id}")

    # Получаем платеж из БД по ID
    async with aiosqlite.connect("bot_database.db") as conn:
        conn.row_factory = aiosqlite.Row
        cursor = await conn.execute("SELECT * FROM payments WHERE id = ?", (payment_db_id,))
        row = await cursor.fetchone()

    payment = None
    if row:
        payment = Payment(
            id=row['id'],
            user_id=row['user_id'],
            payment_id=row['payment_id'],
            order_id=row['order_id'],
            amount=row['amount'],
            months=row['months'],
            status=PaymentStatus(row['status']),
            created_at=row['created_at'],
            paid_at=row['paid_at'],
            currency=row['currency'],
            payment_method=row['payment_method'],
            discount_code=row['discount_code'],
            referral_used=row['referral_used'],
            subscription_type=row['subscription_type']
        )
        logger.info(f"Найден платеж: {payment.order_id}, статус: {payment.status}")
    else:
        logger.warning(f"Платеж с ID {payment_db_id} не найден в базе данных")

    if payment:
        # Проверяем статус оплаты через WATA API
        logger.info(f"Проверяем оплату через WATA API для платежа {payment.order_id}")
        is_paid = await wata_check_payment(payment.user_id, payment.created_at)

        if is_paid:
            logger.info(f"Оплата подтверждена для платежа {payment.order_id}")
            # Обновляем статус платежа в БД
            current_time = int(datetime.datetime.now().timestamp())
            await db.update_payment_status(payment.id, "paid", current_time)

            # Создаем подписку
            subscription_start = current_time
            subscription_end = subscription_start + (payment.months * 30 * 24 * 60 * 60)  # Примерно в секундах

            subscription = Subscription(
                user_id=payment.user_id,
                payment_id=payment.id,
                start_date=subscription_start,
                end_date=subscription_end,
                months=payment.months,
                status=SubscriptionStatus.ACTIVE,
                auto_renew=False,
                created_at=current_time,
                updated_at=current_time
            )

            subscription_id = await db.save_subscription(subscription)

            # Активируем подписку пользователя
            await db.activate_user_subscription(payment.user_id, subscription_start, subscription_end)

            logger.info(f"Подписка {subscription_id} активирована для пользователя {payment.user_id}")

            # Переходим к созданию карточки игрока
            await state.set_state(UserRegistration.waiting_for_player_photo)

            await callback.message.edit_text(
                f"✅ Оплата подтверждена!\n\n"
                f"🎉 Подписка на {payment.months} месяцев активирована!\n\n"
                f"📅 Дата окончания: {datetime.datetime.fromtimestamp(subscription_end).strftime('%d.%m.%Y')}\n\n"
                f"🎮 <b>Обязательный этап: Создание карточки игрока</b>\n\n"
                f"📸 Пожалуйста, загрузите ваше фото для создания игровой карточки.\n"
                f"ИИ проанализирует ваше фото и определит стартовые характеристики:\n"
                f"• 💪 Сила\n"
                f"• 🤸 Ловкость\n"
                f"• 🏃 Выносливость\n"
                f"• 🧠 Интеллект (базовый: 50/100)\n"
                f"• ✨ Харизма (базовый: 50/100)\n\n"
                f"После анализа будет создана ваша уникальная игровая карточка!",
                parse_mode="HTML",
                reply_markup=None
            )
        else:
            logger.info(f"Оплата не найдена для платежа {payment.order_id}")
            await callback.answer("⏳ Оплата еще не найдена. Попробуйте через 1-2 минуты.", show_alert=True)
    else:
        logger.warning(f"Платеж с ID {payment_db_id} не найден")
        await callback.answer("❌ Платеж не найден", show_alert=True)


@router.message(UserRegistration.waiting_for_player_photo, F.photo)
async def process_player_photo(message: Message, state: FSMContext):
    """Обработка фото игрока для создания карточки"""
    user_id = message.from_user.id
    logger.info(f"Получено фото от пользователя {user_id}")

    try:
        # Получаем самое большое фото
        photo = message.photo[-1]

        # Скачиваем фото
        photo_file = await bot.download(photo.file_id)

        # Читаем байты фото
        photo_bytes = photo_file.read()

        # Создаем директорию для фото, если её нет
        photos_dir = "player_photos"
        os.makedirs(photos_dir, exist_ok=True)

        # Сохраняем фото на диск
        photo_path = f"{photos_dir}/{user_id}_{int(datetime.datetime.now().timestamp())}.jpg"
        with open(photo_path, 'wb') as f:
            f.write(photo_bytes)

        # Получаем имя пользователя для ника
        user = await db.get_user(user_id)
        nickname = user.name if user and user.name else f"Player_{user_id}"

        # Анализируем фото с помощью ИИ
        await message.answer("🤖 Анализирую ваше фото и определяю характеристики...")

        stats = await analyze_player_photo(photo_bytes)

        # Создаем изображение карточки игрока
        card_image_path = await create_player_card_image(
            photo_path=photo_path,
            nickname=nickname,
            experience=0,
            stats={
                'strength': stats['strength'],
                'agility': stats['agility'],
                'endurance': stats['endurance'],
                'intelligence': 50,
                'charisma': 50
            }
        )

        # Создаем объект статов игрока
        player_stats = PlayerStats(
            user_id=user_id,
            nickname=nickname,
            experience=0,
            strength=stats['strength'],
            agility=stats['agility'],
            endurance=stats['endurance'],
            intelligence=50,  # базовое значение
            charisma=50,      # базовое значение
            photo_path=photo_path,
            card_image_path=card_image_path,
            created_at=int(datetime.datetime.now().timestamp()),
            updated_at=int(datetime.datetime.now().timestamp())
        )

        # Сохраняем статы в базу данных
        await db.save_player_stats(player_stats)

        # Создаем начальную статистику пользователя
        user_statistics = UserStats(
            user_id=user_id,
            level=1,
            experience=0,
            rank=Rank.F,
            current_streak=0,
            best_streak=0,
            total_tasks_completed=0
        )
        await db.save_user_stats(user_statistics)

        # Обновляем рейтинг среди подписчиков блогера
        await db.update_user_referral_rank(user_id)

        # Отправляем изображение карточки
        if card_image_path and os.path.exists(card_image_path):
            try:
                photo = FSInputFile(card_image_path)
                await message.answer_photo(
                    photo,
                    caption="🎮 <b>Ваша игровая карточка создана!</b>",
                    parse_mode="HTML"
                )
            except Exception as e:
                logger.warning(f"Не удалось отправить изображение карточки: {e}")
                await message.answer("⚠️ Карточка создана, но изображение не удалось отправить.")
        else:
            logger.warning(f"Карточка не была создана: card_image_path={card_image_path}")
            await message.answer("⚠️ Произошла ошибка при создании карточки.")

        # Показываем характеристики
        await message.answer(
            f"🏆 <b>Ник:</b> {nickname}\n"
            f"⭐ <b>Опыт:</b> 0 | 📊 <b>Уровень:</b> 1 | 🏅 <b>Ранг:</b> F\n\n"
            f"🏆 <b>Характеристики:</b>\n"
            f"💪 Сила: {stats['strength']}/100\n"
            f"🤸 Ловкость: {stats['agility']}/100\n"
            f"🏃 Выносливость: {stats['endurance']}/100\n"
            f"🧠 Интеллект: 50/100\n"
            f"✨ Харизма: 50/100\n\n"
            f"🎯 <b>Добро пожаловать в игру!</b>\n"
            f"Теперь у вас есть доступ ко всем функциям бота.",
            parse_mode="HTML"
        )

        # Переходим в главное меню
        await state.set_state(UserRegistration.main_menu)
        await show_main_menu(message)

        logger.info(f"Карточка игрока создана для пользователя {user_id}: ник={nickname}, сила={stats['strength']}, ловкость={stats['agility']}, выносливость={stats['endurance']}")

    except Exception as e:
        logger.error(f"Ошибка обработки фото пользователя {user_id}: {e}")
        await message.answer(
            "❌ Произошла ошибка при обработке фото.\n\n"
            "Попробуйте загрузить другое фото или обратитесь в поддержку."
        )

@router.message(UserRegistration.waiting_for_player_photo)
async def process_player_photo_invalid(message: Message):
    """Обработка неправильного ввода в состоянии ожидания фото"""
    await message.answer(
        "📸 Пожалуйста, загрузите ваше фото для создания карточки игрока.\n\n"
        "Отправьте фото в чат."
    )

# Обработчики главного меню

@router.message(F.text == "🎯 Получить задание")
async def handle_get_task(message: Message, state: FSMContext):
    """Обработка получения задания"""
    user_id = message.from_user.id
    logger.info(f"Пользователь {user_id} запросил получение задания")

    # Проверяем, есть ли уже активное задание
    active_task = await db.get_active_daily_task(user_id)
    if active_task:
        logger.info(f"У пользователя {user_id} уже есть активное задание")
        await message.answer(
            "❌ <b>У вас уже есть активное задание!</b>\n\n"
            "Сначала выполните текущее задание или дождитесь его истечения.\n\n"
            "Используйте кнопку '📋 Активные задания' для просмотра.",
            parse_mode="HTML",
            reply_markup=create_main_menu_keyboard()
        )
        return

    # Получаем цель пользователя для генерации задания
    user = await db.get_user(user_id)
    if not user:
        logger.error(f"Пользователь {user_id} не найден в базе данных")
        await message.answer(
            "❌ <b>Ошибка получения данных пользователя!</b>\n\n"
            "Попробуйте позже или обратитесь в поддержку.",
            parse_mode="HTML",
            reply_markup=create_main_menu_keyboard()
        )
        return

    logger.info(f"Пользователь найден. is_complete: {user.is_complete}, goal: '{user.goal}'")

    # Проверяем, завершена ли регистрация
    if not user.is_complete:
        logger.warning(f"Регистрация пользователя {user_id} не завершена")
        await message.answer(
            "❌ <b>Регистрация не завершена!</b>\n\n"
            "Пожалуйста, завершите процесс регистрации.",
            parse_mode="HTML",
            reply_markup=create_main_menu_keyboard()
        )
        return

    # Проверяем наличие цели
    if not user.goal or len(user.goal.strip()) == 0:
        logger.warning(f"Цель пользователя {user_id} пустая или не установлена: '{user.goal}'")
        await message.answer(
            "❌ <b>Цель не установлена!</b>\n\n"
            "Используйте кнопку '👤 Профиль' для просмотра вашего профиля и установки цели.",
            parse_mode="HTML",
            reply_markup=create_main_menu_keyboard()
        )
        return

    logger.info(f"Цель пользователя {user_id} найдена: '{user.goal}'")

    # Генерируем задание через ИИ
    task_description = await generate_daily_task(user.goal)

    # Создаем задание
    current_time = int(datetime.datetime.now().timestamp())
    expires_at = current_time + (24 * 60 * 60)  # 24 часа

    task = DailyTask(
        user_id=user_id,
        task_description=task_description,
        created_at=current_time,
        expires_at=expires_at,
        status=TaskStatus.PENDING
    )

    task_id = await db.save_daily_task(task)

    await message.answer(
        f"🎯 <b>Новое задание получено!</b>\n\n"
        f"📝 <b>Задание:</b>\n{task_description}\n\n"
        f"⏰ <b>Время на выполнение:</b> 24 часа\n\n"
        f"📸 <b>Для сдачи задания:</b> отправьте фото или видео выполнения\n\n"
        f"Удачи в выполнении!",
        parse_mode="HTML",
        reply_markup=create_main_menu_keyboard()
    )

@router.message(F.text == "📋 Активные задания")
async def handle_active_tasks(message: Message, state: FSMContext):
    """Обработка просмотра активных заданий"""
    user_id = message.from_user.id

    # Получаем активное задание
    active_task = await db.get_active_daily_task(user_id)

    if not active_task:
        await message.answer(
            "📋 <b>Активных заданий нет</b>\n\n"
            "У вас нет активных заданий. Получите новое задание!",
            parse_mode="HTML",
            reply_markup=create_main_menu_keyboard()
        )
        return

    # Рассчитываем оставшееся время
    current_time = int(datetime.datetime.now().timestamp())
    time_left = active_task.expires_at - current_time

    if time_left <= 0:
        # Задание истекло
        await message.answer(
            "⏰ <b>Задание истекло!</b>\n\n"
            "К сожалению, время на выполнение задания вышло.\n"
            "Получите новое задание!",
            parse_mode="HTML",
            reply_markup=create_main_menu_keyboard()
        )
        return

    # Форматируем время
    hours = time_left // 3600
    minutes = (time_left % 3600) // 60

    await message.answer(
        f"📋 <b>Ваше активное задание</b>\n\n"
        f"📝 <b>Задание:</b>\n{active_task.task_description}\n\n"
        f"⏰ <b>Осталось времени:</b> {hours}ч {minutes}мин\n"
        f"📸 <b>Статус:</b> Ожидает выполнения\n\n"
        f"Для сдачи задания отправьте фото или видео выполнения в чат!",
        parse_mode="HTML",
        reply_markup=create_main_menu_keyboard()
    )

@router.message(F.text == "👤 Профиль")
async def handle_profile(message: Message, state: FSMContext):
    """Обработка просмотра профиля"""
    user_id = message.from_user.id

    # Получаем данные пользователя
    user = await db.get_user(user_id)
    player_stats = await db.get_player_stats(user_id)
    user_statistics = await db.get_user_stats(user_id)

    if not user or not player_stats or not user_statistics:
        await message.answer(
            "❌ <b>Ошибка загрузки профиля</b>\n\n"
            "Попробуйте позже или обратитесь в поддержку.",
            parse_mode="HTML",
            reply_markup=create_main_menu_keyboard()
        )
        return

    # Показываем профиль с подменю
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📊 Рейтинг", callback_data="rating")],
        [InlineKeyboardButton(text="📸 Заменить фотографию", callback_data="change_photo")],
        [InlineKeyboardButton(text="💳 Оплата", callback_data="payment_info")],
        [InlineKeyboardButton(text="🎯 Сменить цель", callback_data="change_goal")]
    ])

    # Сначала отправляем изображение карточки, если оно существует
    if player_stats.card_image_path and os.path.exists(player_stats.card_image_path):
        try:
            photo = FSInputFile(player_stats.card_image_path)
            await message.answer_photo(
                photo,
                caption="🎮 <b>Ваша игровая карточка</b>",
                parse_mode="HTML"
            )
        except Exception as e:
            logger.warning(f"Не удалось отправить карточку: {e}")

    await message.answer(
        f"👤 <b>Профиль игрока</b>\n\n"
        f"🏆 <b>Ник:</b> {player_stats.nickname}\n"
        f"⭐ <b>Опыт:</b> {user_statistics.experience} | 📊 <b>Уровень:</b> {user_statistics.level}\n"
        f"🏅 <b>Ранг:</b> {user_statistics.rank.value} | 🔥 <b>Стрик:</b> {user_statistics.current_streak} дней\n"
        f"🎯 <b>Лучший стрик:</b> {user_statistics.best_streak} дней\n"
        f"✅ <b>Выполнено заданий:</b> {user_statistics.total_tasks_completed}\n\n"
        f"🏆 <b>Характеристики:</b>\n"
        f"💪 Сила: {player_stats.strength}/100\n"
        f"🤸 Ловкость: {player_stats.agility}/100\n"
        f"🏃 Выносливость: {player_stats.endurance}/100\n"
        f"🧠 Интеллект: {player_stats.intelligence}/100\n"
        f"✨ Харизма: {player_stats.charisma}/100\n\n"
        f"🎯 <b>Цель:</b> {user.goal if user.goal else 'Не установлена'}\n\n"
        f"Выберите действие:",
        parse_mode="HTML",
        reply_markup=keyboard
    )

def get_achievement_description(achievement_type: str, achievement_value: int) -> str:
    """Получение описания достижения"""
    if achievement_type == 'rank':
        rank_names = ['F', 'E', 'D', 'C', 'B', 'A', 'S', 'S+']
        rank_name = rank_names[achievement_value - 1] if 0 <= achievement_value - 1 < len(rank_names) else f"неизвестный ({achievement_value})"
        return f'Достижение ранга {rank_name}'

    descriptions = {
        'streak': f'Стрик {achievement_value} дней подряд',
        'level': f'Достижение уровня {achievement_value}',
        'tasks': f'Выполнение {achievement_value} заданий',
        'experience': f'Набор {achievement_value} опыта'
    }
    return descriptions.get(achievement_type, f'{achievement_type}: {achievement_value}')

def get_profile_text(user, player_stats, user_statistics) -> str:
    """Формирование текста профиля"""
    referral_text = f"🔗 <b>Реферальный код:</b> {user.referral_code}\n" if user.referral_code else ""

    return (
        f"👤 <b>Профиль игрока</b>\n\n"
        f"🏆 <b>Ник:</b> {player_stats.nickname}\n"
        f"⭐ <b>Опыт:</b> {user_statistics.experience} | 📊 <b>Уровень:</b> {user_statistics.level}\n"
        f"🏅 <b>Ранг:</b> {user_statistics.rank.value} | 🔥 <b>Стрик:</b> {user_statistics.current_streak} дней\n"
        f"🎯 <b>Лучший стрик:</b> {user_statistics.best_streak} дней\n"
        f"✅ <b>Выполнено заданий:</b> {user_statistics.total_tasks_completed}\n"
        f"{referral_text}\n"
        f"🏆 <b>Характеристики:</b>\n"
        f"💪 <b>Сила:</b> {player_stats.strength}/100\n"
        f"🤸 <b>Ловкость:</b> {player_stats.agility}/100\n"
        f"🏃 <b>Выносливость:</b> {player_stats.endurance}/100\n"
        f"🧠 <b>Интеллект:</b> {player_stats.intelligence}/100\n"
        f"✨ <b>Харизма:</b> {player_stats.charisma}/100\n\n"
        f"🎮 <b>Выберите действие:</b>"
    )

@router.message(F.text == "🎁 Призы")
async def handle_prizes(message: Message, state: FSMContext):
    """Обработка просмотра призов"""
    user_id = message.from_user.id

    # Получаем данные пользователя
    user = await db.get_user(user_id)

    # Получаем призы от главного модератора
    admin_prizes = await db.get_prizes(prize_type=PrizeType.ADMIN, is_active=True)

    # Получаем призы от блогера (если есть реферальный код)
    blogger_prizes = []
    if user and user.referral_code:
        blogger_prizes = await db.get_prizes(prize_type=PrizeType.BLOGGER, referral_code=user.referral_code, is_active=True)

    prize_text = "🎁 <b>Текущие призы</b>\n\n"

    # Призы от главного модератора
    if admin_prizes:
        prize_text += "👑 <b>Призы от главного модератора:</b>\n"
        for prize in admin_prizes:
            prize_text += f"{prize.emoji} <b>{prize.title}</b>\n"
            if prize.description:
                prize_text += f"   └ {prize.description}\n"
            prize_text += f"   └ Достижение: {get_achievement_description(prize.achievement_type, prize.achievement_value)}\n\n"
    else:
        prize_text += "👑 <b>Призы от главного модератора:</b>\n"
        prize_text += "   └ Пока нет активных призов\n\n"

    # Призы от блогера
    if user and user.referral_code:
        if blogger_prizes:
            prize_text += f"📣 <b>Призы от блогера '{user.referral_code}':</b>\n"
            for prize in blogger_prizes:
                prize_text += f"{prize.emoji} <b>{prize.title}</b>\n"
                if prize.description:
                    prize_text += f"   └ {prize.description}\n"
                prize_text += f"   └ Достижение: {get_achievement_description(prize.achievement_type, prize.achievement_value)}\n\n"
        else:
            prize_text += f"📣 <b>Призы от блогера '{user.referral_code}':</b>\n"
            prize_text += "   └ Пока нет активных призов\n\n"
    else:
        prize_text += "📣 <b>Призы от блогера:</b>\n"
        prize_text += "   └ Укажите реферальный код блогера в профиле для просмотра его призов\n\n"

    prize_text += "🏆 <b>Система достижений:</b>\n"
    prize_text += "Призы начисляются автоматически при достижении целей!\n\n"
    prize_text += "<i>Следите за своими достижениями в профиле!</i>"

    await message.answer(
        prize_text,
        parse_mode="HTML",
        reply_markup=create_main_menu_keyboard()
    )

@router.message(F.text == "💬 Поддержка")
async def handle_support(message: Message, state: FSMContext):
    """Обработка поддержки"""

    await message.answer(
        "💬 <b>Поддержка</b>\n\n"
        "Если у вас возникли вопросы или проблемы:\n\n"
        "📧 <b>Email:</b> support@motivationbot.com\n"
        "💭 <b>Telegram:</b> @motivation_support\n"
        "🌐 <b>Сайт:</b> motivationbot.com/support\n\n"
        "🕐 <b>Время работы:</b>\n"
        "Пн-Пт: 9:00 - 18:00 (MSK)\n"
        "Сб-Вс: 10:00 - 16:00 (MSK)\n\n"
        "Мы всегда готовы помочь! 🚀",
        parse_mode="HTML",
        reply_markup=create_main_menu_keyboard()
    )

# Обработчики медиафайлов для сдачи заданий
@router.message(F.photo)
async def handle_task_submission_photo(message: Message, state: FSMContext):
    """Обработка отправки фото для сдачи задания"""
    await handle_task_submission(message, state, "photo")

@router.message(F.video)
async def handle_task_submission_video(message: Message, state: FSMContext):
    """Обработка отправки видео для сдачи задания"""
    await handle_task_submission(message, state, "video")

async def handle_task_submission(message: Message, state: FSMContext, media_type: str):
    """Обработка отправки медиафайла для сдачи задания"""
    user_id = message.from_user.id

    # Получаем активное задание пользователя
    active_task = await db.get_active_daily_task(user_id)
    if not active_task:
        await message.answer(
            "❌ <b>У вас нет активного задания для сдачи!</b>\n\n"
            "Сначала получите задание через меню.",
            parse_mode="HTML",
            reply_markup=create_main_menu_keyboard()
        )
        return

    try:
        # Создаем директорию для медиафайлов заданий
        media_dir = "task_submissions"
        os.makedirs(media_dir, exist_ok=True)

        # Определяем файл и сохраняем его
        if media_type == "photo":
            media_file = message.photo[-1]  # Самое большое фото
            file_extension = "jpg"
            file_name = f"{media_dir}/task_{active_task.id}_{user_id}_{int(datetime.datetime.now().timestamp())}.jpg"
        else:  # video
            media_file = message.video
            file_extension = media_file.file_name.split('.')[-1] if media_file.file_name else "mp4"
            file_name = f"{media_dir}/task_{active_task.id}_{user_id}_{int(datetime.datetime.now().timestamp())}.mp4"

        # Скачиваем файл
        file_bytes = await bot.download(media_file.file_id)

        # Сохраняем файл
        with open(file_name, 'wb') as f:
            f.write(file_bytes.read())

        # Обновляем статус задания в базе данных
        success = await db.submit_daily_task_media(active_task.id, file_name)

        if success:
            await message.answer(
                f"✅ <b>Задание отправлено на проверку!</b>\n\n"
                f"📝 <b>Задание:</b>\n{active_task.task_description}\n\n"
                f"⏳ <b>Статус:</b> Ожидает модерации\n\n"
                f"Вы получите уведомление о результате проверки.",
                parse_mode="HTML",
                reply_markup=create_main_menu_keyboard()
            )
            logger.info(f"Пользователь {user_id} отправил {media_type} для задания {active_task.id}")
        else:
            await message.answer(
                "❌ <b>Ошибка отправки задания</b>\n\n"
                "Попробуйте отправить файл еще раз.",
                parse_mode="HTML",
                reply_markup=create_main_menu_keyboard()
            )

    except Exception as e:
        logger.error(f"Ошибка обработки медиафайла от пользователя {user_id}: {e}")
        await message.answer(
            "❌ <b>Ошибка обработки файла</b>\n\n"
            "Попробуйте отправить файл в другом формате или обратитесь в поддержку.",
            parse_mode="HTML",
            reply_markup=create_main_menu_keyboard()
        )

def calculate_rank(level: int, best_streak: int, total_tasks: int) -> Rank:
    """Рассчитывает ранг пользователя на основе достижений"""
    score = level * 10 + best_streak * 2 + total_tasks

    if score >= 1000:
        return Rank.S_PLUS
    elif score >= 500:
        return Rank.S
    elif score >= 300:
        return Rank.A
    elif score >= 150:
        return Rank.B
    elif score >= 75:
        return Rank.C
    elif score >= 30:
        return Rank.D
    elif score >= 10:
        return Rank.E
    else:
        return Rank.F

# Обработчики подменю профиля

@router.callback_query(lambda c: c.data == "rating")
async def handle_rating(callback: CallbackQuery, state: FSMContext):
    """Обработка просмотра рейтинга"""
    await callback.answer()
    user_id = callback.from_user.id

    # Получаем данные пользователя
    user = await db.get_user(user_id)
    user_stats = await db.get_user_stats(user_id)

    if not user or not user_stats:
        await callback.message.edit_text(
            "❌ <b>Ошибка загрузки рейтинга</b>",
            parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="⬅️ Назад", callback_data="profile")]
            ])
        )
        return

    # Получаем топ пользователей по городу
    city_rating = await db.get_top_users_by_city(user.city, 10)

    # Получаем топ пользователей по рангу
    rank_rating = await db.get_top_users_by_rank(user_stats.rank.value, 10)

    # Получаем топ пользователей среди подписчиков блогера (если есть реферальный код)
    referral_rating = None
    if user.referral_code:
        referral_rating = await db.get_top_users_by_referral_code(user.referral_code, 10)

    rating_text = "📊 <b>Рейтинг</b>\n\n"

    # Рейтинг по городу
    rating_text += f"🏙️ <b>Топ по городу '{user.city}':</b>\n"
    if city_rating:
        for i, (name, level, exp, rank) in enumerate(city_rating, 1):
            rating_text += f"{i}. {name} - Ур.{level} ({rank})\n"
    else:
        rating_text += "Пока нет данных\n"

    rating_text += "\n"

    # Рейтинг по рангу
    rating_text += f"🏅 <b>Топ по рангу '{user_stats.rank.value}':</b>\n"
    if rank_rating:
        for i, (name, level, exp, city) in enumerate(rank_rating, 1):
            rating_text += f"{i}. {name} - Ур.{level} ({city})\n"
    else:
        rating_text += "Пока нет данных\n"

    rating_text += "\n"

    # Рейтинг среди подписчиков блогера (если есть реферальный код)
    if user.referral_code and referral_rating:
        rating_text += f"📣 <b>Топ подписчиков блогера '{user.referral_code}':</b>\n"
        for i, (name, level, exp, ref_rank, city) in enumerate(referral_rating, 1):
            rating_text += f"{i}. {name} - Ур.{level} ({ref_rank if ref_rank else 'Нет ранга'})\n"
    elif user.referral_code:
        rating_text += f"📣 <b>Топ подписчиков блогера '{user.referral_code}':</b>\n"
        rating_text += "Пока нет данных\n"

    await callback.message.edit_text(
        rating_text,
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="⬅️ Назад", callback_data="back_to_profile")]
        ])
    )

@router.callback_query(lambda c: c.data == "back_to_profile")
async def handle_back_to_profile(callback: CallbackQuery, state: FSMContext):
    """Обработка возврата в профиль"""
    await callback.answer()
    user_id = callback.from_user.id

    # Получаем данные пользователя
    user = await db.get_user(user_id)
    player_stats = await db.get_player_stats(user_id)
    user_statistics = await db.get_user_stats(user_id)

    if not user or not player_stats or not user_statistics:
        await callback.message.edit_text(
            "❌ <b>Ошибка загрузки профиля</b>\n\n"
            "Попробуйте позже или обратитесь в поддержку.",
            parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="⬅️ Назад в меню", callback_data="back_to_menu")]
            ])
        )
        return

    # Показываем профиль с подменю
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📊 Рейтинг", callback_data="rating")],
        [InlineKeyboardButton(text="📸 Заменить фотографию", callback_data="change_photo")],
        [InlineKeyboardButton(text="💳 Оплата", callback_data="payment_info")],
        [InlineKeyboardButton(text="🎯 Сменить цель", callback_data="change_goal")]
    ])

    # Сначала отправляем изображение карточки, если оно существует
    if player_stats.card_image_path and os.path.exists(player_stats.card_image_path):
        try:
            photo = FSInputFile(player_stats.card_image_path)
            await callback.message.delete()  # Удаляем сообщение рейтинга
            await callback.message.answer_photo(
                photo,
                caption=get_profile_text(user, player_stats, user_statistics),
                parse_mode="HTML",
                reply_markup=keyboard
            )
        except Exception as e:
            logger.error(f"Ошибка отправки фото профиля: {e}")
            # Если не удалось отправить фото, отправляем текстовую версию
            await callback.message.edit_text(
                get_profile_text(user, player_stats, user_statistics),
                parse_mode="HTML",
                reply_markup=keyboard
            )
    else:
        # Отправляем текстовую версию профиля
        await callback.message.edit_text(
            get_profile_text(user, player_stats, user_statistics),
            parse_mode="HTML",
            reply_markup=keyboard
        )

@router.callback_query(lambda c: c.data == "change_photo")
async def handle_change_photo(callback: CallbackQuery, state: FSMContext):
    """Обработка замены фотографии"""
    await callback.answer()

    await callback.message.edit_text(
        "📸 <b>Замена фотографии</b>\n\n"
        "Отправьте новое фото для анализа.\n"
        "Старые характеристики будут сохранены.\n\n"
        "<i>Только фото будет заменено, статы останутся прежними.</i>",
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="⬅️ Отмена", callback_data="profile")]
        ])
    )

    # Устанавливаем состояние для замены фото
    await state.set_state(UserRegistration.waiting_for_player_photo)

@router.callback_query(lambda c: c.data == "payment_info")
async def handle_payment_info(callback: CallbackQuery, state: FSMContext):
    """Обработка информации об оплате"""
    await callback.answer()
    user_id = callback.from_user.id

    # Получаем данные о подписке
    user = await db.get_user(user_id)

    if not user or not user.subscription_active or not user.subscription_end:
        await callback.message.edit_text(
            "💳 <b>Информация об оплате</b>\n\n"
            "❌ <b>Подписка не активна</b>\n\n"
            "Для доступа ко всем функциям оформите подписку.",
            parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="💰 Оформить подписку", callback_data="subscribe")],
                [InlineKeyboardButton(text="⬅️ Назад", callback_data="profile")]
            ])
        )
        return

    # Рассчитываем оставшееся время
    current_time = int(datetime.datetime.now().timestamp())
    time_left = user.subscription_end - current_time

    if time_left <= 0:
        days_left = 0
        status = "❌ Истекла"
    else:
        days_left = time_left // (24 * 60 * 60)
        status = f"✅ Активна ({days_left} дней)"

    await callback.message.edit_text(
        f"💳 <b>Информация об оплате</b>\n\n"
        f"📅 <b>Статус подписки:</b> {status}\n"
        f"🎯 <b>Доступ:</b> Все функции активны\n\n"
        f"Хотите продлить подписку?",
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="💰 Продлить подписку", callback_data="subscribe")],
            [InlineKeyboardButton(text="⬅️ Назад", callback_data="profile")]
        ])
    )

@router.callback_query(lambda c: c.data == "change_goal")
async def handle_change_goal(callback: CallbackQuery, state: FSMContext):
    """Обработка смены цели"""
    await callback.answer()

    await callback.message.edit_text(
        "🎯 <b>Смена цели</b>\n\n"
        "Расскажите о вашей новой цели:\n\n"
        "<i>ИИ поможет сформулировать её правильно.</i>",
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="⬅️ Отмена", callback_data="profile")]
        ])
    )

    # Устанавливаем состояние для ввода новой цели
    await state.set_state(UserRegistration.changing_goal)

@router.message(UserRegistration.changing_goal)
async def process_goal_change(message: Message, state: FSMContext):
    """Обработка новой цели пользователя"""
    user_id = message.from_user.id
    goal = message.text.strip()

    if len(goal) < 3:
        await message.answer(
            "Пожалуйста, опишите вашу цель более подробно (минимум 3 символа):"
        )
        return

    logger.info(f"Пользователь {user_id} меняет цель на: '{goal}'")

    # Улучшаем цель с помощью ИИ
    await message.answer("🤖 Улучшаю формулировку вашей цели...")
    improved_goal = await improve_goal_with_ai(goal)

    # Сохраняем новую цель в базу данных
    user = await db.get_user(user_id)
    if user:
        # Обновляем цель пользователя
        await db.update_user_field(user_id, 'goal', improved_goal)
        logger.info(f"Цель пользователя {user_id} обновлена на: '{improved_goal}'")

        await message.answer(
            f"✅ <b>Цель успешно обновлена!</b>\n\n"
            f"🎯 <b>Ваша новая цель:</b>\n"
            f"<i>{improved_goal}</i>\n\n"
            f"Теперь вы можете получать персонализированные задания по этой цели.",
            parse_mode="HTML"
        )

        # Очищаем состояние и возвращаемся в главное меню
        await state.clear()
        await show_main_menu(message)
    else:
        logger.error(f"Пользователь {user_id} не найден при обновлении цели")
        await message.answer(
            "❌ <b>Ошибка обновления цели</b>\n\n"
            "Попробуйте позже или обратитесь в поддержку.",
            parse_mode="HTML"
        )

@router.callback_query(lambda c: c.data == "back_to_menu")
async def handle_back_to_menu(callback: CallbackQuery, state: FSMContext):
    """Обработка возврата в главное меню"""
    await callback.answer()

    await callback.message.edit_text(
        "🎮 <b>Главное меню</b>\n\n"
        "Выберите действие:",
        parse_mode="HTML",
        reply_markup=None
    )

    # Отправляем новое сообщение с клавиатурой главного меню
    await callback.message.answer(
        "🎮 <b>Главное меню</b>\n\n"
        "Выберите действие:",
        parse_mode="HTML",
        reply_markup=create_main_menu_keyboard()
    )

@router.callback_query(lambda c: c.data == "subscribe")
async def handle_subscribe(callback: CallbackQuery, state: FSMContext):
    """Обработка оформления подписки"""
    await callback.answer()

    # Возвращаемся к выбору подписки
    await callback.message.edit_text(
        "💰 <b>Выберите план подписки</b>\n\n"
        "Все планы дают полный доступ ко всем функциям бота:",
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="1 месяц - 500 ₽", callback_data="sub_1")],
            [InlineKeyboardButton(text="3 месяца - 1200 ₽", callback_data="sub_3")],
            [InlineKeyboardButton(text="6 месяцев - 2200 ₽", callback_data="sub_6")],
            [InlineKeyboardButton(text="12 месяцев - 4000 ₽", callback_data="sub_12")],
            [InlineKeyboardButton(text="⏭️ Пропустить оплату (тест)", callback_data="skip_payment")],
            [InlineKeyboardButton(text="⬅️ Назад в меню", callback_data="back_to_menu")]
        ])
    )

async def generate_daily_task(user_goal: str) -> str:
    """Генерирует ежедневное задание на основе цели пользователя"""
    try:
        import ssl
        import certifi

        # Создаем SSL-контекст с сертификатами certifi
        ssl_context = ssl.create_default_context(cafile=certifi.where())
        connector = aiohttp.TCPConnector(ssl=ssl_context)

        task_prompt = TASK_GENERATION_TEMPLATE.format(user_goal=user_goal)

        async with aiohttp.ClientSession(connector=connector) as session:
            payload = {
                "model": DEFAULT_MODEL,
                "messages": [
                    {"role": "system", "content": task_prompt},
                    {"role": "user", "content": f"Создай задание для цели: {user_goal}"}
                ],
                "max_tokens": 300,
                "temperature": 0.8
            }

            headers = {
                "Authorization": f"Bearer {OPENROUTER_API_KEY}",
                "Content-Type": "application/json",
                "HTTP-Referer": "https://t.me/motivation_bot",
                "X-Title": "Motivation Bot"
            }

            async with session.post(
                f"{OPENROUTER_BASE_URL}/chat/completions",
                json=payload,
                headers=headers
            ) as response:
                if response.status == 200:
                    data = await response.json()
                    task = data["choices"][0]["message"]["content"].strip()
                    return task
                else:
                    logger.error(f"OpenRouter API error: {response.status}")
                    return f"Поработать над целью: {user_goal[:50]}..."

    except Exception as e:
        logger.error(f"Error generating daily task: {e}")
        return f"Сделать шаг к цели: {user_goal[:50]}..."

@router.message(Command("help"))
async def cmd_help(message: Message):
    """Обработчик команды помощи"""
    help_text = (
        "🤖 <b>Справка по мотивационному боту</b>\n\n"
        "Я — твой личный мотивационный помощник! Помогаю достигать целей через ежедневные задания.\n\n"
        "📋 <b>Команды:</b>\n"
        "/start - Начать регистрацию или проверить статус\n"
        "/update - Обновить свои данные\n"
        "/cancel - Отменить текущую регистрацию\n"
        "/help - Показать эту справку\n\n"
        "📝 <b>Что собирает бот для персонализации:</b>\n"
        "• Предпочитаемый язык\n"
        "• Имя\n"
        "• Дата рождения (ДД.ММ.ГГГГ)\n"
        "• Рост (в см)\n"
        "• Вес (в кг)\n"
        "• Город\n"
        "• Реферальный код (опционально)\n"
        "• Главная цель\n\n"
        "Все данные сохраняются в базе данных и используются для персонализации заданий и отслеживания прогресса."
    )
    await message.answer(help_text)

# Обработчик всех остальных сообщений
@router.message()
async def handle_unknown(message: Message, state: FSMContext):
    """Обработчик неизвестных сообщений"""
    current_state = await state.get_state()

    if current_state is not None:
        await message.answer(
            "Пожалуйста, следуйте инструкциям и введите корректные данные.\n"
            "Используйте /cancel для отмены регистрации."
        )
    else:
        await message.answer(
            "Неизвестная команда. Используйте /start для начала регистрации или /help для справки."
        )

async def payment_polling_task():
    """Фоновая задача для периодической проверки неоплаченных платежей"""
    while True:
        try:
            # Получаем все неоплаченные платежи из БД
            pending_payments = await db.get_pending_payments()

            for payment in pending_payments:
                # Проверяем статус оплаты через WATA API
                is_paid = await wata_check_payment(payment.user_id, payment.created_at)

                if is_paid:
                    # Обновляем статус платежа в БД
                    current_time = int(datetime.datetime.now().timestamp())
                    await db.update_payment_status(payment.id, "paid", current_time)

                    # Создаем подписку
                    subscription_start = current_time
                    subscription_end = subscription_start + (payment.months * 30 * 24 * 60 * 60)  # Примерно в секундах

                    subscription = Subscription(
                        user_id=payment.user_id,
                        payment_id=payment.id,
                        start_date=subscription_start,
                        end_date=subscription_end,
                        months=payment.months,
                        status=SubscriptionStatus.ACTIVE,
                        auto_renew=False,
                        created_at=current_time,
                        updated_at=current_time
                    )

                    subscription_id = await db.save_subscription(subscription)

                    # Активируем подписку пользователя
                    await db.activate_user_subscription(payment.user_id, subscription_start, subscription_end)

                    # Уведомляем пользователя об успешной оплате
                    try:
                        await bot.send_message(
                            payment.user_id,
                            f"✅ Оплата получена!\n\n"
                            f"🎉 Подписка на {payment.months} месяцев активирована!\n\n"
                            f"📅 Дата окончания: {datetime.datetime.fromtimestamp(subscription_end).strftime('%d.%m.%Y')}\n\n"
                            f"🚀 Теперь вы можете пользоваться всеми функциями бота!"
                        )
                    except Exception as e:
                        logger.error(f"Не удалось отправить уведомление пользователю {payment.user_id}: {e}")

                    logger.info(f"Платеж {payment.id} для пользователя {payment.user_id} подтвержден, подписка {subscription_id} создана")

            # Проверяем каждые 30 секунд
            await asyncio.sleep(30)

        except Exception as e:
            logger.error(f"[payment_polling_task] Error: {e}")
            await asyncio.sleep(60)

async def on_startup():
    """Функция, выполняемая при запуске бота"""
    await db.init_db()
    # Запускаем фоновую задачу проверки платежей
    asyncio.create_task(payment_polling_task())
    logger.info("Бот запущен и готов к работе")
    logger.info("Зарегистрированные handlers: check_payment_callback")

async def on_shutdown():
    """Функция, выполняемая при остановке бота"""
    logger.info("Бот остановлен")

async def main():
    """Главная функция"""
    # Регистрируем роутер
    dp.include_router(router)

    # Регистрируем обработчики запуска и остановки
    dp.startup.register(on_startup)
    dp.shutdown.register(on_shutdown)

    # Запускаем бота
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
