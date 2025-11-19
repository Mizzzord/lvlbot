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

from config import BOT_TOKEN, USE_POSTGRES, DATABASE_PATH
from database import Database
from models import User, Payment, PaymentStatus, Subscription, SubscriptionStatus, PlayerStats, Rank, DailyTask, UserStats, TaskStatus, Prize, PrizeType, Challenge, ChallengeSubmission, ChallengeSubmissionStatus
from polza_config import (
    POLZA_API_KEY, POLZA_BASE_URL, DEFAULT_MODEL, VISION_MODEL, SYSTEM_PROMPT,
    PHOTO_ANALYSIS_PROMPT, TASK_GENERATION_TEMPLATE
)
from subscription_config import SUBSCRIPTION_PLANS, SUBSCRIPTION_LEVELS

# Конфигурация дней неактивности по уровням подписки
INACTIVITY_DAYS_BY_LEVEL = {
    1: 2,  # Стартовый - 2 дня
    2: 3,  # Продвинутый - 3 дня
    3: 4   # Мастер - 4 дня
}
from wata_api import wata_create_payment, wata_check_payment

# Настройка логирования
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Определение состояний FSM
class UserRegistration(StatesGroup):
    waiting_for_start_confirmation = State()  # Ожидание подтверждения начала регистрации
    waiting_for_privacy_policy = State()
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
    changing_goal_confirmation = State()

class ChallengeStates(StatesGroup):
    viewing_challenges = State()  # Просмотр списка челленджей
    submitting_challenge = State()  # Загрузка ответа на челлендж
    waiting_for_challenge_text = State()  # Ввод текстового комментария к ответу

# Инициализация бота и диспетчера
bot = Bot(token=BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
dp = Dispatcher()

# Логируем настройки базы данных для отладки
logger.info(f"USE_POSTGRES из config: {USE_POSTGRES}")
logger.info(f"DATABASE_PATH: {DATABASE_PATH}")

db = Database(db_path=DATABASE_PATH, use_postgres=USE_POSTGRES)

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
            [KeyboardButton(text="🏆 Челленджи")],
            [KeyboardButton(text="💬 Поддержка")]
        ],
        resize_keyboard=True,
        one_time_keyboard=False
    )

def get_registration_status(user: User) -> dict:
    """
    Определяет статус регистрации пользователя

    Returns:
        dict: {
            'status': 'complete' | 'incomplete' | 'paid_pending' | 'new',
            'next_step': str,  # следующий этап регистрации
            'can_restart': bool,  # можно ли начать заново
            'message': str  # сообщение для пользователя
        }
    """
    if user.is_complete:
        # Проверяем, оплатили ли подписку
        if user.subscription_active:
            return {
                'status': 'complete',
                'next_step': None,
                'can_restart': False,
                'message': 'Регистрация завершена, подписка активна'
            }
        else:
            return {
                'status': 'paid_pending',
                'next_step': 'payment',
                'can_restart': False,
                'message': 'Регистрация завершена, но подписка не оплачена'
            }

    # Определяем следующий этап регистрации
    if not user.language:
        return {
            'status': 'incomplete',
            'next_step': 'language',
            'can_restart': True,
            'message': 'Не выбран язык'
        }
    elif not user.name:
        return {
            'status': 'incomplete',
            'next_step': 'name',
            'can_restart': True,
            'message': 'Не указано имя'
        }
    elif not user.birth_date:
        return {
            'status': 'incomplete',
            'next_step': 'birth_date',
            'can_restart': True,
            'message': 'Не указана дата рождения'
        }
    elif not user.height:
        return {
            'status': 'incomplete',
            'next_step': 'height',
            'can_restart': True,
            'message': 'Не указан рост'
        }
    elif not user.weight:
        return {
            'status': 'incomplete',
            'next_step': 'weight',
            'can_restart': True,
            'message': 'Не указан вес'
        }
    elif not user.city:
        return {
            'status': 'incomplete',
            'next_step': 'city',
            'can_restart': True,
            'message': 'Не указан город'
        }
    elif user.referral_code is None:  # проверяем именно None, так как пустая строка допустима
        return {
            'status': 'incomplete',
            'next_step': 'referral',
            'can_restart': True,
            'message': 'Не указан реферальный код'
        }
    elif not user.goal:
        return {
            'status': 'incomplete',
            'next_step': 'goal',
            'can_restart': True,
            'message': 'Не указана цель'
        }
    else:
        # Регистрация почти завершена, но не отмечена как complete
        return {
            'status': 'incomplete',
            'next_step': 'subscription',
            'can_restart': False,  # нельзя начать заново, так как цель уже указана
            'message': 'Регистрация почти завершена'
        }



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
                "Authorization": f"Bearer {POLZA_API_KEY}",
                "Content-Type": "application/json",
                "HTTP-Referer": "https://t.me/motivation_bot",
                "X-Title": "Motivation Bot"
            }

            async with session.post(
                f"{POLZA_BASE_URL}/chat/completions",
                json=payload,
                headers=headers
            ) as response:
                if response.status in (200, 201):
                    data = await response.json()
                    improved_goal = data["choices"][0]["message"]["content"].strip()
                    return improved_goal
                else:
                    logger.error(f"Polza.ai API error: {response.status}")
                    return goal  # Возвращаем оригинальную цель в случае ошибки

    except Exception as e:
        logger.error(f"Error calling OpenRouter API: {e}")
        return goal  # Возвращаем оригинальную цель в случае ошибки


async def show_main_menu(message_or_callback):
    """Показать главное меню пользователя"""
    keyboard = create_main_menu_keyboard()

    # Определяем chat_id в зависимости от типа объекта
    if hasattr(message_or_callback, 'from_user'):
        user = message_or_callback.from_user
        chat_id = user.id
        # Проверяем, что пользователь не является ботом
        if user.is_bot:
            logger.warning(f"Попытка показать главное меню боту: {chat_id}")
            return
    elif hasattr(message_or_callback, 'chat'):
        chat_id = message_or_callback.chat.id
    else:
        chat_id = message_or_callback

    await bot.send_message(
        chat_id=chat_id,
        text="🎮 <b>Главное меню</b>\n\n"
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
                "model": VISION_MODEL,  # Используем модель с поддержкой изображений
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
                "Authorization": f"Bearer {POLZA_API_KEY}",
                "Content-Type": "application/json",
                "HTTP-Referer": "https://t.me/motivation_bot",
                "X-Title": "Motivation Bot"
            }

            async with session.post(
                f"{POLZA_BASE_URL}/chat/completions",
                json=payload,
                headers=headers
            ) as response:
                if response.status in (200, 201):
                    data = await response.json()
                    result_text = data["choices"][0]["message"]["content"].strip()

                    # Парсим JSON из ответа
                    try:
                        import json
                        import re
                        
                        # Очищаем ответ от markdown разметки (```json ... ``` или ``` ... ```)
                        cleaned_text = result_text.strip()
                        # Удаляем markdown код блоки в начале и конце
                        # Удаляем ```json или ``` в начале строки
                        cleaned_text = re.sub(r'^```(?:json)?\s*', '', cleaned_text, flags=re.MULTILINE)
                        # Удаляем ``` в конце строки
                        cleaned_text = re.sub(r'```\s*$', '', cleaned_text, flags=re.MULTILINE)
                        cleaned_text = cleaned_text.strip()
                        
                        stats = json.loads(cleaned_text)
                        logger.info(f"ИИ вернул характеристики: {stats}")

                        # Валидируем и нормализуем значения
                        strength = max(1, min(100, int(stats.get('strength', 50))))
                        agility = max(1, min(100, int(stats.get('agility', 50))))
                        endurance = max(1, min(100, int(stats.get('endurance', 50))))

                        result_stats = {
                            'strength': strength,
                            'agility': agility,
                            'endurance': endurance
                        }
                        logger.info(f"Нормализованные характеристики: {result_stats}")
                        return result_stats
                    except (json.JSONDecodeError, KeyError, ValueError) as e:
                        logger.error(f"Ошибка парсинга ответа ИИ: {e}, ответ: {result_text}")
                        # Возвращаем значения по умолчанию
                        return {'strength': 50, 'agility': 50, 'endurance': 50}
                else:
                    logger.error(f"Polza.ai API error: {response.status}")
                    return {'strength': 50, 'agility': 50, 'endurance': 50}

    except Exception as e:
        logger.error(f"Error analyzing player photo: {e}")
        return {'strength': 50, 'agility': 50, 'endurance': 50}

async def create_player_card_image_nodejs(photo_path: str, nickname: str, experience: int, level: int, rank: str, rating_position: int, stats: dict) -> str:
    """
    Создает изображение карточки игрока с помощью Node.js сервиса

    Args:
        photo_path: путь к фото пользователя
        nickname: ник игрока
        experience: опыт игрока
        level: уровень игрока
        rank: ранг игрока
        rating_position: позиция в общем рейтинге
        stats: словарь с характеристиками

    Returns:
        str: путь к созданному изображению карточки
    """
    try:
        # Отправляем запрос к Node.js сервису
        # Увеличенный таймаут для генерации больших изображений
        async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=60, connect=10)) as session:
            payload = {
                "photoPath": photo_path,
                "nickname": nickname,
                "experience": experience,
                "level": level,
                "rank": rank,
                "ratingPosition": rating_position,
                "stats": stats
            }

            async with session.post(
                "http://localhost:3000/generate-card",
                json=payload,
                headers={"Content-Type": "application/json"}
            ) as response:
                logger.info(f"Node.js response status: {response.status}")
                logger.info(f"Node.js response headers: {dict(response.headers)}")

                if response.status in (200, 201):
                    # Получаем изображение
                    image_data = await response.read()
                    logger.info(f"Получено {len(image_data)} байт от Node.js сервиса")

                    # Проверяем, что это действительно изображение (начинается с PNG сигнатуры)
                    if not image_data or not image_data.startswith(b'\x89PNG'):
                        logger.error(f"Полученные данные не являются PNG изображением. Размер: {len(image_data) if image_data else 0} байт")
                        # Попробуем распарсить как JSON с ошибкой
                        if image_data:
                            try:
                                error_json = image_data.decode('utf-8')
                                logger.error(f"Ответ сервера (JSON): {error_json}")
                            except UnicodeDecodeError:
                                logger.error(f"Первые байты ответа: {image_data[:100].hex()}")
                        raise Exception("Node.js service returned invalid image data")

                    # Проверяем Content-Type
                    content_type = response.headers.get('Content-Type', '')
                    if 'image/png' not in content_type.lower():
                        logger.warning(f"Content-Type не соответствует изображению: {content_type}")

                    # Сохраняем изображение
                    cards_dir = "player_cards"
                    os.makedirs(cards_dir, exist_ok=True)

                    card_filename = f"{cards_dir}/card_{nickname}_{int(datetime.datetime.now().timestamp())}.png"
                    with open(card_filename, 'wb') as f:
                        f.write(image_data)

                    logger.info(f"Карточка игрока создана через Node.js: {card_filename}")
                    return card_filename
                else:
                    error_text = await response.text()
                    logger.error(f"Node.js сервис вернул ошибку {response.status}: {error_text}")
                    raise Exception(f"Node.js service error: {response.status}")

    except Exception as e:
        logger.warning(f"Не удалось создать карточку через Node.js сервис: {e}")
        raise e


async def create_player_card_image(photo_path: str, nickname: str, experience: int, stats: dict, level: int = 1, rank: str = 'F', rating_position: int = None) -> str:
    """
    Создает изображение карточки игрока с фото как фоном

    Args:
        photo_path: путь к фото пользователя (используется как фон)
        nickname: ник игрока
        experience: опыт игрока
        stats: словарь с характеристиками
        level: уровень игрока
        rank: ранг игрока
        rating_position: позиция в рейтинге (опционально)

    Returns:
        str: путь к созданному изображению карточки
    """
    try:
        from PIL import ImageFilter
        
        # Размеры карточки
        card_width = 800
        card_height = 1200

        # Загружаем фото пользователя и используем как фон
        try:
            user_photo = Image.open(photo_path).convert('RGB')
            # Изменяем размер фото под размер карточки с сохранением пропорций
            photo_ratio = user_photo.width / user_photo.height
            card_ratio = card_width / card_height
            
            if photo_ratio > card_ratio:
                # Фото шире - обрезаем по ширине
                new_height = card_height
                new_width = int(new_height * photo_ratio)
                user_photo = user_photo.resize((new_width, new_height), Image.Resampling.LANCZOS)
                # Обрезаем по центру
                left = (new_width - card_width) // 2
                user_photo = user_photo.crop((left, 0, left + card_width, new_height))
            else:
                # Фото выше - обрезаем по высоте
                new_width = card_width
                new_height = int(new_width / photo_ratio)
                user_photo = user_photo.resize((new_width, new_height), Image.Resampling.LANCZOS)
                # Обрезаем по центру
                top = (new_height - card_height) // 2
                user_photo = user_photo.crop((0, top, new_width, top + card_height))
            
            # Применяем легкое размытие для фона
            user_photo = user_photo.filter(ImageFilter.GaussianBlur(radius=2))
            
            # Создаем затемняющий слой для читаемости текста
            # Затемняем изображение, уменьшая яркость
            overlay = Image.new('RGB', (card_width, card_height), (0, 0, 0))
            overlay_alpha = Image.new('L', (card_width, card_height), 70)  # 70 из 255 = ~27% прозрачности
            
            # Создаем карточку с фоном
            card = Image.new('RGB', (card_width, card_height))
            card.paste(user_photo, (0, 0))
            
            # Накладываем затемнение
            darkened = Image.blend(card, overlay, 0.27)
            card = darkened
            
        except Exception as e:
            logger.warning(f"Не удалось загрузить фото пользователя: {e}")
            # Создаем градиентный фон если фото недоступно
            card = Image.new('RGB', (card_width, card_height), (30, 30, 46))
            # Добавляем градиент
            for y in range(card_height):
                alpha = y / card_height
                r = int(30 + (60 - 30) * alpha)
                g = int(30 + (50 - 30) * alpha)
                b = int(46 + (80 - 46) * alpha)
                for x in range(card_width):
                    card.putpixel((x, y), (r, g, b))

        draw = ImageDraw.Draw(card)

        # Цвета для дизайна
        primary_color = (147, 112, 219)  # Medium Purple
        secondary_color = (255, 215, 0)  # Gold
        accent_color = (255, 140, 0)     # Dark Orange
        text_color = (255, 255, 255)     # White
        stat_color = (176, 196, 222)     # Light Steel Blue

        # Загружаем шрифты
        try:
            title_font = ImageFont.truetype("/System/Library/Fonts/Arial.ttf", 52)
            nick_font = ImageFont.truetype("/System/Library/Fonts/Arial.ttf", 42)
            info_font = ImageFont.truetype("/System/Library/Fonts/Arial.ttf", 28)
            stat_font = ImageFont.truetype("/System/Library/Fonts/Arial.ttf", 26)
            value_font = ImageFont.truetype("/System/Library/Fonts/Arial.ttf", 24)
        except:
            title_font = ImageFont.load_default()
            nick_font = ImageFont.load_default()
            info_font = ImageFont.load_default()
            stat_font = ImageFont.load_default()
            value_font = ImageFont.load_default()

        # Верхняя панель с градиентом
        top_panel_height = 180
        top_panel = Image.new('RGB', (card_width, top_panel_height), (0, 0, 0))
        top_panel_alpha = Image.new('L', (card_width, top_panel_height), 200)  # 200 из 255 = ~78% непрозрачности
        top_panel_rgba = Image.merge('RGBA', (*top_panel.split(), top_panel_alpha))
        card_rgba = card.convert('RGBA')
        card_rgba.paste(top_panel_rgba, (0, 0), top_panel_rgba)
        card = card_rgba.convert('RGB')
        draw = ImageDraw.Draw(card)  # Пересоздаем draw после изменения формата

        # Заголовок "ИГРОВАЯ КАРТОЧКА"
        title_text = "ИГРОВАЯ КАРТОЧКА"
        title_bbox = draw.textbbox((0, 0), title_text, font=title_font)
        title_width = title_bbox[2] - title_bbox[0]
        title_x = (card_width - title_width) // 2
        title_y = 30

        # Тень для заголовка
        draw.text((title_x + 2, title_y + 2), title_text, font=title_font, fill=(0, 0, 0))
        # Основной текст заголовка
        draw.text((title_x, title_y), title_text, font=title_font, fill=secondary_color)

        # Ник игрока с эффектом свечения
        nick_y = title_y + 70
        nick_bbox = draw.textbbox((0, 0), nickname, font=nick_font)
        nick_width = nick_bbox[2] - nick_bbox[0]
        nick_x = (card_width - nick_width) // 2
        
        # Тень для ника
        draw.text((nick_x + 2, nick_y + 2), nickname, font=nick_font, fill=(0, 0, 0))
        # Основной текст ника
        draw.text((nick_x, nick_y), nickname, font=nick_font, fill=text_color)

        # Информационная панель (уровень, ранг, опыт)
        info_panel_y = top_panel_height + 20
        info_panel_height = 120
        info_panel = Image.new('RGB', (card_width - 80, info_panel_height), (0, 0, 0))
        info_panel_alpha = Image.new('L', (card_width - 80, info_panel_height), 150)
        info_panel_rgba = Image.merge('RGBA', (*info_panel.split(), info_panel_alpha))
        card_rgba = card.convert('RGBA')
        card_rgba.paste(info_panel_rgba, (40, info_panel_y), info_panel_rgba)
        card = card_rgba.convert('RGB')
        draw = ImageDraw.Draw(card)  # Пересоздаем draw после изменения формата

        # Уровень и ранг
        level_text = f"📊 Уровень: {level}"
        rank_text = f"🏅 Ранг: {rank}"
        
        draw.text((60, info_panel_y + 20), level_text, font=info_font, fill=text_color)
        draw.text((60, info_panel_y + 60), rank_text, font=info_font, fill=secondary_color)

        # Опыт справа
        exp_text = f"⭐ {experience} XP"
        exp_bbox = draw.textbbox((0, 0), exp_text, font=info_font)
        exp_width = exp_bbox[2] - exp_bbox[0]
        exp_x = card_width - 60 - exp_width
        draw.text((exp_x, info_panel_y + 40), exp_text, font=info_font, fill=accent_color)

        # Позиция в рейтинге (если указана)
        if rating_position:
            rating_text = f"🏆 #{rating_position}"
            rating_bbox = draw.textbbox((0, 0), rating_text, font=value_font)
            rating_width = rating_bbox[2] - rating_bbox[0]
            rating_x = card_width - 60 - rating_width
            draw.text((rating_x, info_panel_y + 80), rating_text, font=value_font, fill=stat_color)

        # Панель характеристик
        stats_panel_y = info_panel_y + info_panel_height + 30
        stats_panel_height = 550
        stats_panel = Image.new('RGB', (card_width - 80, stats_panel_height), (0, 0, 0))
        stats_panel_alpha = Image.new('L', (card_width - 80, stats_panel_height), 180)
        stats_panel_rgba = Image.merge('RGBA', (*stats_panel.split(), stats_panel_alpha))
        card_rgba = card.convert('RGBA')
        card_rgba.paste(stats_panel_rgba, (40, stats_panel_y), stats_panel_rgba)
        card = card_rgba.convert('RGB')
        draw = ImageDraw.Draw(card)  # Пересоздаем draw после изменения формата

        # Заголовок характеристик
        stats_title = "ХАРАКТЕРИСТИКИ"
        stats_title_bbox = draw.textbbox((0, 0), stats_title, font=info_font)
        stats_title_width = stats_title_bbox[2] - stats_title_bbox[0]
        stats_title_x = (card_width - stats_title_width) // 2
        draw.text((stats_title_x, stats_panel_y + 20), stats_title, font=info_font, fill=secondary_color)

        # Характеристики
        stat_names = {
            'strength': '💪 Сила',
            'agility': '🤸 Ловкость',
            'endurance': '🏃 Выносливость',
            'intelligence': '🧠 Интеллект',
            'charisma': '✨ Харизма'
        }

        start_y = stats_panel_y + 70
        bar_width = 500
        bar_height = 30
        spacing = 90

        for i, (stat_key, stat_name) in enumerate(stat_names.items()):
            stat_value = stats.get(stat_key, 50)

            # Название характеристики
            stat_y = start_y + i * spacing
            draw.text((60, stat_y), f"{stat_name}", font=stat_font, fill=text_color)

            # Значение характеристики справа
            value_text = f"{stat_value}/100"
            value_bbox = draw.textbbox((0, 0), value_text, font=value_font)
            value_width = value_bbox[2] - value_bbox[0]
            value_x = card_width - 60 - value_width
            draw.text((value_x, stat_y + 2), value_text, font=value_font, fill=secondary_color)

            # Полоса прогресса
            bar_x = 60
            bar_y = stat_y + 35

            # Фон полосы с зеленой рамкой
            green_outline = (34, 139, 34)  # Зеленый цвет для рамки
            draw.rectangle([bar_x, bar_y, bar_x + bar_width, bar_y + bar_height],
                         fill=(30, 30, 30), outline=green_outline, width=2)

            # Заполнение полосы с зеленым градиентом
            fill_width = int(bar_width * stat_value / 100)
            if fill_width > 0:
                # Зеленый градиент для полосы прогресса
                for x in range(bar_x + 2, bar_x + fill_width - 2):
                    progress = (x - bar_x) / bar_width
                    # Зеленые оттенки: от темно-зеленого к ярко-зеленому
                    r = int(34 + (76 * progress))   # 34-110 (темно-зеленый к ярко-зеленому)
                    g = int(139 + (116 * progress)) # 139-255 (средне-зеленый к ярко-зеленому)
                    b = int(34 + (76 * progress))    # 34-110
                    draw.rectangle([x, bar_y + 2, x + 1, bar_y + bar_height - 2], fill=(r, g, b))

        # Нижний декор
        footer_y = card_height - 60
        footer_text = "© Motivation Bot"
        footer_font_size = 18
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
        import traceback
        logger.error(traceback.format_exc())
        return None

async def update_player_card(user_id: int) -> bool:
    """
    Обновляет карточку игрока после изменения опыта или характеристик
    
    Args:
        user_id: ID пользователя
        
    Returns:
        bool: True если карточка успешно обновлена, False в противном случае
    """
    try:
        # Получаем данные игрока
        player_stats = await db.get_player_stats(user_id)
        if not player_stats or not player_stats.photo_path:
            logger.warning(f"Не удалось обновить карточку для пользователя {user_id}: нет фото или статистики")
            return False
        
        # Получаем статистику пользователя
        user_stats = await db.get_user_stats(user_id)
        if not user_stats:
            logger.warning(f"Не удалось обновить карточку для пользователя {user_id}: нет статистики пользователя")
            return False
        
        # Получаем позицию в рейтинге
        rating_position = await db.get_user_rating_position(user_id)
        
        # Формируем данные для карточки
        stats = {
            'strength': player_stats.strength,
            'agility': player_stats.agility,
            'endurance': player_stats.endurance,
            'intelligence': player_stats.intelligence,
            'charisma': player_stats.charisma
        }
        
        nickname = player_stats.nickname or f"Player_{user_id}"
        experience = user_stats.experience
        level = user_stats.level
        rank = user_stats.rank.value
        
        # Удаляем старую карточку, если она существует
        if player_stats.card_image_path and os.path.exists(player_stats.card_image_path):
            try:
                os.remove(player_stats.card_image_path)
                logger.info(f"Удалена старая карточка: {player_stats.card_image_path}")
            except Exception as e:
                logger.warning(f"Не удалось удалить старую карточку: {e}")
        
        # Создаем новую карточку
        try:
            # Пробуем создать через Node.js сервис
            card_image_path = await create_player_card_image_nodejs(
                player_stats.photo_path,
                nickname,
                experience,
                level,
                rank,
                rating_position,
                stats
            )
        except Exception as e:
            logger.warning(f"Не удалось создать карточку через Node.js: {e}, используем Python версию")
            # Используем Python версию как fallback
            card_image_path = await create_player_card_image(
                player_stats.photo_path,
                nickname,
                experience,
                stats,
                level,
                rank,
                rating_position
            )
        
        if card_image_path:
            # Обновляем путь к карточке в базе данных
            await db.update_player_card_path(user_id, card_image_path)
            logger.info(f"Карточка игрока обновлена для пользователя {user_id}: {card_image_path}")
            return True
        else:
            logger.error(f"Не удалось создать карточку для пользователя {user_id}")
            return False
            
    except Exception as e:
        logger.error(f"Ошибка при обновлении карточки игрока для пользователя {user_id}: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return False

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

def create_subscription_level_keyboard(current_level_index: int = 0) -> InlineKeyboardMarkup:
    """Создание inline клавиатуры для выбора уровня подписки с навигацией"""
    total_levels = len(SUBSCRIPTION_LEVELS)
    level = SUBSCRIPTION_LEVELS[current_level_index]
    
    # Кнопки навигации
    nav_buttons = []
    
    # Кнопка "Назад" (влево)
    if current_level_index > 0:
        nav_buttons.append(InlineKeyboardButton(text="⬅️", callback_data=f"sub_level_{current_level_index - 1}"))
    else:
        nav_buttons.append(InlineKeyboardButton(text="⬅️", callback_data="sub_level_disabled"))
    
    # Индикатор уровня (текущий из общего количества)
    nav_buttons.append(InlineKeyboardButton(
        text=f"{current_level_index + 1}/{total_levels}",
        callback_data="sub_level_info"
    ))
    
    # Кнопка "Вперед" (вправо)
    if current_level_index < total_levels - 1:
        nav_buttons.append(InlineKeyboardButton(text="➡️", callback_data=f"sub_level_{current_level_index + 1}"))
    else:
        nav_buttons.append(InlineKeyboardButton(text="➡️", callback_data="sub_level_disabled"))
    
    keyboard = [
        nav_buttons,
        [InlineKeyboardButton(text="✅ Подтвердить", callback_data=f"sub_confirm_{current_level_index}")],
        [InlineKeyboardButton(text="❌ Отмена", callback_data="cancel_registration")]
    ]
    
    return InlineKeyboardMarkup(inline_keyboard=keyboard)

def get_subscription_level_text(level_index: int) -> str:
    """Получение текста описания уровня подписки"""
    level = SUBSCRIPTION_LEVELS[level_index]
    
    features_text = "\n".join(level["features"])
    
    text = (
        f"🎯 <b>Уровень: {level['name']}</b>\n\n"
        f"⏱ Период: {level['description']}\n"
        f"💰 Стоимость: {level['price']} ₽\n\n"
        f"📋 <b>Что включено:</b>\n{features_text}"
    )
    
    return text

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

def split_long_message(text: str, max_length: int = 4000) -> list[str]:
    """Разбивает длинный текст на части для отправки в Telegram"""
    if len(text) <= max_length:
        return [text]
    
    parts = []
    current_part = ""
    lines = text.split('\n')
    
    for line in lines:
        # Если добавление строки превысит лимит, сохраняем текущую часть
        if len(current_part) + len(line) + 1 > max_length:
            if current_part:
                parts.append(current_part.rstrip())
            current_part = line + '\n'
        else:
            current_part += line + '\n'
    
    # Добавляем последнюю часть
    if current_part:
        parts.append(current_part.rstrip())
    
    return parts

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

    if existing_user:
        # Сначала проверяем активную подписку (может быть выдана администратором)
        active_subscription = await db.get_active_subscription(telegram_id)
        
        # Проверяем, есть ли карточка игрока
        player_stats = await db.get_player_stats(telegram_id)
        
        # Если есть активная подписка
        if active_subscription:
            end_date = datetime.datetime.fromtimestamp(active_subscription.end_date).strftime('%d.%m.%Y')
            
            if player_stats:
                # У пользователя есть карточка - показываем кнопку "Профиль"
                user_statistics = await db.get_user_stats(telegram_id)
                await message.answer(
                    f"С возвращением, {existing_user.name}! 👋\n\n"
                    f"💎 <b>Подписка активна до {end_date}</b>\n\n"
                    f"🎮 Ваша игровая карточка активна!\n\n"
                    f"🏆 Ник: {player_stats.nickname} | ⭐ Опыт: {user_statistics.experience if user_statistics else 0}\n"
                    f"📊 Уровень: {user_statistics.level if user_statistics else 1} | 🏅 Ранг: {user_statistics.rank.value if user_statistics else 'F'}\n\n"
                    f"Готов продолжить приключения?",
                    parse_mode="HTML",
                    reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                        [InlineKeyboardButton(text="👤 Профиль", callback_data="go_to_profile")]
                    ])
                )
            else:
                # У пользователя нет карточки - показываем кнопку "Продолжить путь"
                await message.answer(
                    f"Привет, {existing_user.name}! 👋\n\n"
                    f"💎 <b>Подписка активна до {end_date}</b>\n\n"
                    f"🎯 Чтобы начать пользоваться ботом, нужно загрузить своё фото и получить характеристики персонажа.\n\n"
                    f"Готов продолжить?",
                    parse_mode="HTML",
                    reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                        [InlineKeyboardButton(text="🚀 Продолжить путь", callback_data="continue_path")]
                    ])
                )
            return
        
        # Определяем статус регистрации
        reg_status = get_registration_status(existing_user)

        if reg_status['status'] == 'complete':
            # Пользователь полностью зарегистрирован и имеет активную подписку
            referral_text = f"📢 Реферальный код: {existing_user.referral_code}\n" if existing_user.referral_code else ""
            goal_text = f"🎯 Цель: {existing_user.goal}\n" if existing_user.goal else ""

            # Проверяем статус подписки
            subscription_text = ""
            if existing_user.subscription_active and existing_user.subscription_end:
                end_date = datetime.datetime.fromtimestamp(existing_user.subscription_end).strftime('%d.%m.%Y')
                subscription_text = f"💎 Подписка активна до {end_date}\n"
            else:
                subscription_text = "💎 Подписка: Не активна\n"

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
                    f"👤 Имя: {existing_user.name}\n"
                    f"📅 Дата рождения: {existing_user.birth_date.strftime('%d.%m.%Y') if existing_user.birth_date else 'Не указана'}\n"
                    f"📏 Рост: {existing_user.height} см\n"
                    f"⚖️ Вес: {existing_user.weight} кг\n"
                    f"🏙️ Город: {existing_user.city}\n"
                    f"{referral_text}"
                    f"{goal_text}"
                    f"{subscription_text}"
                    f"{stats_text}\n",
                    parse_mode="HTML"
                    )
        elif reg_status['status'] == 'paid_pending':
            # Регистрация завершена, но подписка не оплачена
            await message.answer(
                f"С возвращением, {existing_user.name}! 👋\n\n"
                f"📋 Ваша регистрация завершена, но подписка не активна.\n\n"
                f"🎯 Цель: {existing_user.goal}\n\n"
                f"Хотите продолжить с оплатой подписки?",
                reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                    [InlineKeyboardButton(text="💳 Оплатить подписку", callback_data="continue_payment")],
                    [InlineKeyboardButton(text="ℹ️ Проверить статус", callback_data="check_payment_status")]
                ])
            )
        elif reg_status['status'] == 'incomplete':
            # Регистрация не завершена - предлагаем продолжить или начать заново
            keyboard_buttons = [
                [InlineKeyboardButton(text="▶️ Продолжить регистрацию", callback_data="resume_registration")]
            ]

            if reg_status['can_restart']:
                keyboard_buttons.append(
                    [InlineKeyboardButton(text="🔄 Начать заново", callback_data="restart_registration")]
                )

            await message.answer(
                f"Привет, {message.from_user.first_name or 'друг'}! 👋\n\n"
                f"📝 Кажется, вы не завершили регистрацию.\n"
                f"🔍 Статус: {reg_status['message']}\n\n"
                f"Что вы хотите сделать?",
                reply_markup=InlineKeyboardMarkup(inline_keyboard=keyboard_buttons)
            )
    else:
        # Получаем имя пользователя из Telegram
        user_name = message.from_user.first_name or "друг"

        # Отправляем приветственное мотивационное сообщение с кнопкой "Продолжить"
        await state.set_state(UserRegistration.waiting_for_start_confirmation)
        await message.answer(
            f"Привет, {user_name}! 👋 Я GoPrime — твой личный мотивационный помощник в Telegram. Я помогу тебе достигать целей шаг за шагом: каждый день буду предлагать простые, но мощные задания, адаптированные под твои приоритеты — фитнес, обучение, карьера, хобби или что-то своё. Расскажи о своей главной цели, и мы сразу начнём! Готов к первым шагам к успеху? 🚀",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="▶️ Продолжить", callback_data="start_registration")]
            ])
        )


@router.callback_query(lambda c: c.data == "start_registration")
async def handle_start_registration(callback: CallbackQuery, state: FSMContext):
    """Обработка нажатия кнопки 'Продолжить' - переход к политике конфиденциальности"""
    await callback.answer()
    
    # Переходим к политике конфиденциальности
    await state.set_state(UserRegistration.waiting_for_privacy_policy)
    
    # Ссылки на документы
    privacy_policy_url = "https://docs.google.com/document/d/1o4LBBlGi1iy8omOh8c1bLSexxm4MeW3iW4PQZRBRt_A/edit?tab=t.0"
    user_agreement_url = "https://docs.google.com/document/d/1yjXpk6-H1sA4hkUCwutFBEwHv25--k1zBYZgH16i1Ok/edit?tab=t.0"
    
    await callback.message.edit_text(
        "📋 <b>Политика конфиденциальности и обработка персональных данных</b>\n\n"
        "Пожалуйста, ознакомьтесь с нашими документами:\n\n"
        "Нажимая '✅ Подтверждаю', вы соглашаетесь с условиями.",
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="📄 Политика конфиденциальности", url=privacy_policy_url)],
            [InlineKeyboardButton(text="📋 Пользовательское соглашение", url=user_agreement_url)],
            [InlineKeyboardButton(text="✅ Подтверждаю", callback_data="privacy_confirmed")],
            [InlineKeyboardButton(text="❌ Отмена", callback_data="privacy_declined")]
        ])
    )

@router.callback_query(lambda c: c.data == "privacy_confirmed")
async def handle_privacy_confirmed(callback: CallbackQuery, state: FSMContext):
    """Обработка подтверждения политики конфиденциальности"""
    await callback.answer()

    # Автоматически устанавливаем русский язык
    telegram_id = callback.from_user.id
    user = await db.get_user(telegram_id) or User(telegram_id=telegram_id)
    user.language = "ru"
    await db.save_user(user)

    # Сохраняем язык во временном состоянии
    await state.update_data(language="ru")

    await state.set_state(UserRegistration.waiting_for_name)
    await callback.message.edit_text(
        "✅ Спасибо за подтверждение!",
        reply_markup=None
    )
    await callback.message.answer(
        "Теперь введите ваше имя:",
        reply_markup=create_cancel_keyboard()
    )

@router.callback_query(lambda c: c.data == "privacy_declined")
async def handle_privacy_declined(callback: CallbackQuery, state: FSMContext):
    """Обработка отказа от политики конфиденциальности"""
    await callback.answer()
    await state.clear()

    await callback.message.edit_text(
        "❌ Регистрация отменена.\n\n"
        "Без согласия с политикой конфиденциальности регистрация невозможна.\n\n"
        "Вы можете начать заново командой /start",
        reply_markup=None
    )

@router.callback_query(lambda c: c.data == "resume_registration")
async def handle_resume_registration(callback: CallbackQuery, state: FSMContext):
    """Обработка продолжения незавершенной регистрации"""
    await callback.answer()
    telegram_id = callback.from_user.id

    # Получаем данные пользователя
    user = await db.get_user(telegram_id)
    if not user:
        await callback.message.edit_text(
            "❌ Ошибка: пользователь не найден. Начните регистрацию заново командой /start",
            reply_markup=None
        )
        return

    # Определяем следующий этап регистрации
    reg_status = get_registration_status(user)

    if reg_status['status'] == 'complete':
        await callback.message.edit_text(
            "✅ Ваша регистрация уже завершена!",
            reply_markup=None
        )
        return

    # Устанавливаем состояние и перенаправляем на соответствующий этап
    next_step = reg_status['next_step']

    if next_step == 'language':
        await state.set_state(UserRegistration.waiting_for_privacy_policy)
        
        # Ссылки на документы
        privacy_policy_url = "https://docs.google.com/document/d/1o4LBBlGi1iy8omOh8c1bLSexxm4MeW3iW4PQZRBRt_A/edit?tab=t.0"
        user_agreement_url = "https://docs.google.com/document/d/1yjXpk6-H1sA4hkUCwutFBEwHv25--k1zBYZgH16i1Ok/edit?tab=t.0"
        
        await callback.message.edit_text(
            "🔄 Продолжаем регистрацию...\n\n"
            "📋 <b>Политика конфиденциальности и обработка персональных данных</b>\n\n"
            "Пожалуйста, ознакомьтесь с нашими документами:\n\n"
            "Нажимая '✅ Подтверждаю', вы соглашаетесь с условиями.",
            parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="📄 Политика конфиденциальности", url=privacy_policy_url)],
                [InlineKeyboardButton(text="📋 Пользовательское соглашение", url=user_agreement_url)],
                [InlineKeyboardButton(text="✅ Подтверждаю", callback_data="privacy_confirmed")],
                [InlineKeyboardButton(text="❌ Отмена", callback_data="privacy_declined")]
            ])
        )
    elif next_step == 'name':
        await state.set_state(UserRegistration.waiting_for_name)
        await callback.message.edit_text(
            "🔄 Продолжаем регистрацию...\n\n"
            "✅ Спасибо за подтверждение!\n\n"
            "Теперь введите ваше имя:",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="❌ Отмена", callback_data="cancel_registration")]
            ])
        )
    elif next_step == 'birth_date':
        await state.set_state(UserRegistration.waiting_for_birth_date)
        await callback.message.edit_text(
            f"🔄 Продолжаем регистрацию...\n\n"
            f"👤 Имя: {user.name}\n\n"
            f"📅 Теперь введите дату рождения в формате ДД.ММ.ГГГГ\n"
            f"(например: 15.05.1990):",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="❌ Отмена", callback_data="cancel_registration")]
            ])
        )
    elif next_step == 'height':
        await state.set_state(UserRegistration.waiting_for_height)
        await callback.message.edit_text(
            f"🔄 Продолжаем регистрацию...\n\n"
            f"👤 Имя: {user.name}\n"
            f"📅 Дата рождения: {user.birth_date.strftime('%d.%m.%Y')}\n\n"
            f"📏 Теперь введите ваш рост в сантиметрах (50-250):",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="❌ Отмена", callback_data="cancel_registration")]
            ])
        )
    elif next_step == 'weight':
        await state.set_state(UserRegistration.waiting_for_weight)
        await callback.message.edit_text(
            f"🔄 Продолжаем регистрацию...\n\n"
            f"👤 Имя: {user.name}\n"
            f"📅 Дата рождения: {user.birth_date.strftime('%d.%m.%Y')}\n"
            f"📏 Рост: {user.height} см\n\n"
            f"⚖️ Теперь введите ваш вес в килограммах (3-300):",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="❌ Отмена", callback_data="cancel_registration")]
            ])
        )
    elif next_step == 'city':
        await state.set_state(UserRegistration.waiting_for_city)
        await callback.message.edit_text(
            f"🔄 Продолжаем регистрацию...\n\n"
            f"👤 Имя: {user.name}\n"
            f"📅 Дата рождения: {user.birth_date.strftime('%d.%m.%Y')}\n"
            f"📏 Рост: {user.height} см\n"
            f"⚖️ Вес: {user.weight} кг\n\n"
            f"🏙️ Теперь введите ваш город:",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="❌ Отмена", callback_data="cancel_registration")]
            ])
        )
    elif next_step == 'referral':
        await state.set_state(UserRegistration.waiting_for_referral)
        await callback.message.edit_text(
            f"🔄 Продолжаем регистрацию...\n\n"
            f"👤 Имя: {user.name}\n"
            f"📅 Дата рождения: {user.birth_date.strftime('%d.%m.%Y')}\n"
            f"📏 Рост: {user.height} см\n"
            f"⚖️ Вес: {user.weight} кг\n"
            f"🏙️ Город: {user.city}\n\n"
            f"🔗 Теперь введите реферальный код (если есть) или нажмите 'Пропустить':",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="⏭️ Пропустить", callback_data="skip_referral")]
            ])
        )
    elif next_step == 'goal':
        await state.set_state(UserRegistration.waiting_for_goal)
        await callback.message.edit_text(
            f"🔄 Продолжаем регистрацию...\n\n"
            f"👤 Имя: {user.name}\n"
            f"📅 Дата рождения: {user.birth_date.strftime('%d.%m.%Y')}\n"
            f"📏 Рост: {user.height} см\n"
            f"⚖️ Вес: {user.weight} кг\n"
            f"🏙️ Город: {user.city}\n\n"
            f"🎯 Теперь расскажите о вашей главной цели (минимум 3 символа):",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="❌ Отмена", callback_data="cancel_registration")]
            ])
        )
    elif next_step == 'subscription':
        await state.set_state(UserRegistration.waiting_for_subscription)
        await state.update_data(selected_level_index=0)  # Начинаем с первого уровня
        await callback.message.edit_text(
            f"🔄 Продолжаем регистрацию...\n\n"
            f"👤 Имя: {user.name}\n"
            f"🎯 Цель: {user.goal}\n\n"
            f"💎 Выберите уровень подписки:\n\n"
            f"{get_subscription_level_text(0)}",
            parse_mode="HTML",
            reply_markup=create_subscription_level_keyboard(0)
        )

@router.callback_query(lambda c: c.data == "restart_registration")
async def handle_restart_registration(callback: CallbackQuery, state: FSMContext):
    """Обработка начала регистрации заново"""
    await callback.answer()
    telegram_id = callback.from_user.id

    # Проверяем, можно ли начать заново
    user = await db.get_user(telegram_id)
    if user:
        reg_status = get_registration_status(user)
        if not reg_status['can_restart']:
            await callback.message.edit_text(
                "❌ Нельзя начать регистрацию заново, так как у вас уже указана цель.\n\n"
                "Используйте команду /start для продолжения.",
                reply_markup=None
            )
            return

    # Очищаем данные пользователя (кроме telegram_id)
    if user:
        # Создаем нового пользователя с тем же telegram_id
        new_user = User(telegram_id=telegram_id)
        await db.save_user(new_user)

    # Очищаем состояние FSM
    await state.clear()

    # Начинаем регистрацию заново
    user_name = callback.from_user.first_name or "друг"

    await state.set_state(UserRegistration.waiting_for_start_confirmation)
    await callback.message.edit_text(
        f"Привет, {user_name}! 👋 Я GoPrime — твой личный мотивационный помощник в Telegram. Я помогу тебе достигать целей шаг за шагом: каждый день буду предлагать простые, но мощные задания, адаптированные под твои приоритеты — фитнес, обучение, карьера, хобби или что-то своё. Расскажи о своей главной цели, и мы сразу начнём! Готов к первым шагам к успеху? 🚀",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="▶️ Продолжить", callback_data="start_registration")]
        ])
    )

@router.callback_query(lambda c: c.data == "continue_payment")
async def handle_continue_payment(callback: CallbackQuery, state: FSMContext):
    """Обработка продолжения оплаты подписки"""
    await callback.answer()
    telegram_id = callback.from_user.id

    user = await db.get_user(telegram_id)
    if not user or not user.is_complete:
        await callback.message.edit_text(
            "❌ Ошибка: регистрация не завершена. Используйте /start для продолжения.",
            reply_markup=None
        )
        return

    # Устанавливаем состояние для оплаты и начинаем с первого уровня
    await state.set_state(UserRegistration.waiting_for_subscription)
    await state.update_data(selected_level_index=0)  # Начинаем с первого уровня
    await callback.message.edit_text(
        f"💳 Продолжаем с оплатой подписки...\n\n"
        f"👤 Имя: {user.name}\n"
        f"🎯 Цель: {user.goal}\n\n"
        f"💎 Выберите уровень подписки:\n\n"
        f"{get_subscription_level_text(0)}",
        parse_mode="HTML",
        reply_markup=create_subscription_level_keyboard(0)
    )

@router.callback_query(lambda c: c.data == "check_payment_status")
async def handle_check_payment_status(callback: CallbackQuery, state: FSMContext):
    """Обработка проверки статуса оплаты"""
    await callback.answer()
    telegram_id = callback.from_user.id

    user = await db.get_user(telegram_id)
    if not user:
        await callback.message.edit_text(
            "❌ Ошибка: пользователь не найден.",
            reply_markup=None
        )
        return

    # Получаем активную подписку
    active_subscription = await db.get_active_subscription(telegram_id)

    if active_subscription:
        end_date = datetime.datetime.fromtimestamp(active_subscription.end_date).strftime('%d.%m.%Y')
        await callback.message.edit_text(
            f"✅ Ваша подписка активна!\n\n"
            f"📅 Дата окончания: {end_date}\n"
            f"🎯 Цель: {user.goal}\n\n"
            f"Готов продолжить приключения?",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="🎮 Начать игру", callback_data="start_game")]
            ])
        )
    else:
        await callback.message.edit_text(
            f"❌ Подписка не активна.\n\n"
            f"👤 Имя: {user.name}\n"
            f"🎯 Цель: {user.goal}\n\n"
            f"Хотите оплатить подписку?",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="💳 Оплатить", callback_data="continue_payment")],
                [InlineKeyboardButton(text="🔙 Назад", callback_data="back_to_start")]
            ])
        )

@router.callback_query(lambda c: c.data == "start_game")
async def handle_start_game(callback: CallbackQuery, state: FSMContext):
    """Обработка начала игры после проверки подписки"""
    await callback.answer()

    await state.set_state(UserRegistration.main_menu)
    await callback.message.edit_text(
        "🎮 Добро пожаловать в игру!\n\n"
        "Выберите действие:",
        reply_markup=create_main_menu_keyboard()
    )

@router.callback_query(lambda c: c.data == "back_to_start")
async def handle_back_to_start(callback: CallbackQuery, state: FSMContext):
    """Обработка возврата к началу"""
    await callback.answer()

    # Вызываем cmd_start напрямую с правильным контекстом
    telegram_id = callback.from_user.id
    
    # Проверяем, есть ли уже пользователь в базе
    existing_user = await db.get_user(telegram_id)

    if existing_user:
        # Сначала проверяем активную подписку (может быть выдана администратором)
        active_subscription = await db.get_active_subscription(telegram_id)
        
        # Проверяем, есть ли карточка игрока
        player_stats = await db.get_player_stats(telegram_id)
        
        # Если есть активная подписка
        if active_subscription:
            end_date = datetime.datetime.fromtimestamp(active_subscription.end_date).strftime('%d.%m.%Y')
            
            if player_stats:
                # У пользователя есть карточка - показываем кнопку "Профиль"
                user_statistics = await db.get_user_stats(telegram_id)
                await bot.send_message(
                    chat_id=telegram_id,
                    text=f"С возвращением, {existing_user.name}! 👋\n\n"
                    f"💎 <b>Подписка активна до {end_date}</b>\n\n"
                    f"🎮 Ваша игровая карточка активна!\n\n"
                    f"🏆 Ник: {player_stats.nickname} | ⭐ Опыт: {user_statistics.experience if user_statistics else 0}\n"
                    f"📊 Уровень: {user_statistics.level if user_statistics else 1} | 🏅 Ранг: {user_statistics.rank.value if user_statistics else 'F'}\n\n"
                    f"Готов продолжить приключения?",
                    parse_mode="HTML",
                    reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                        [InlineKeyboardButton(text="👤 Профиль", callback_data="go_to_profile")]
                    ])
                )
            else:
                # У пользователя нет карточки - показываем кнопку "Продолжить путь"
                await bot.send_message(
                    chat_id=telegram_id,
                    text=f"Привет, {existing_user.name}! 👋\n\n"
                    f"💎 <b>Подписка активна до {end_date}</b>\n\n"
                    f"🎯 Чтобы начать пользоваться ботом, нужно загрузить своё фото и получить характеристики персонажа.\n\n"
                    f"Готов продолжить?",
                    parse_mode="HTML",
                    reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                        [InlineKeyboardButton(text="🚀 Продолжить путь", callback_data="continue_path")]
                    ])
                )
            return
        
        # Определяем статус регистрации
        reg_status = get_registration_status(existing_user)

        if reg_status['status'] == 'complete':
            # Пользователь полностью зарегистрирован и имеет активную подписку
            referral_text = f"📢 Реферальный код: {existing_user.referral_code}\n" if existing_user.referral_code else ""
            goal_text = f"🎯 Цель: {existing_user.goal}\n" if existing_user.goal else ""

            # Проверяем статус подписки
            subscription_text = ""
            if existing_user.subscription_active and existing_user.subscription_end:
                end_date = datetime.datetime.fromtimestamp(existing_user.subscription_end).strftime('%d.%m.%Y')
                subscription_text = f"💎 Подписка активна до {end_date}\n"
            else:
                subscription_text = "💎 Подписка: Не активна\n"

            if player_stats:
                # У пользователя есть карточка игрока - показываем главное меню
                user_statistics = await db.get_user_stats(telegram_id)
                await bot.send_message(
                    chat_id=telegram_id,
                    text=f"С возвращением, {existing_user.name}! 👋\n\n"
                    f"🎮 Ваша игровая карточка активна!\n\n"
                    f"🏆 Ник: {player_stats.nickname} | ⭐ Опыт: {user_statistics.experience if user_statistics else 0}\n"
                    f"📊 Уровень: {user_statistics.level if user_statistics else 1} | 🏅 Ранг: {user_statistics.rank.value if user_statistics else 'F'}\n\n"
                    f"Готов продолжить приключения?",
                    parse_mode="HTML"
                )
                await state.set_state(UserRegistration.main_menu)
                await show_main_menu(telegram_id)
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

                await bot.send_message(
                    chat_id=telegram_id,
                    text=f"С возвращением, {existing_user.name}! 👋\n\n"
                    f"Ты уже в нашей команде изменений!\n\n"
                    f"👤 Имя: {existing_user.name}\n"
                    f"📅 Дата рождения: {existing_user.birth_date.strftime('%d.%m.%Y') if existing_user.birth_date else 'Не указана'}\n"
                    f"📏 Рост: {existing_user.height} см\n"
                    f"⚖️ Вес: {existing_user.weight} кг\n"
                    f"🏙️ Город: {existing_user.city}\n"
                    f"{referral_text}"
                    f"{goal_text}"
                    f"{subscription_text}"
                    f"{stats_text}\n",
                    parse_mode="HTML"
                )
        elif reg_status['status'] == 'paid_pending':
            # Регистрация завершена, но подписка не оплачена
            await bot.send_message(
                chat_id=telegram_id,
                text=f"С возвращением, {existing_user.name}! 👋\n\n"
                f"📋 Ваша регистрация завершена, но подписка не активна.\n\n"
                f"🎯 Цель: {existing_user.goal}\n\n"
                f"Хотите продолжить с оплатой подписки?",
                reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                    [InlineKeyboardButton(text="💳 Оплатить подписку", callback_data="continue_payment")],
                    [InlineKeyboardButton(text="ℹ️ Проверить статус", callback_data="check_payment_status")]
                ])
            )
        elif reg_status['status'] == 'incomplete':
            # Регистрация не завершена - предлагаем продолжить или начать заново
            keyboard_buttons = [
                [InlineKeyboardButton(text="▶️ Продолжить регистрацию", callback_data="resume_registration")]
            ]

            if reg_status['can_restart']:
                keyboard_buttons.append(
                    [InlineKeyboardButton(text="🔄 Начать заново", callback_data="restart_registration")]
                )

            await bot.send_message(
                chat_id=telegram_id,
                text=f"Привет, {callback.from_user.first_name or 'друг'}! 👋\n\n"
                f"📝 Кажется, вы не завершили регистрацию.\n"
                f"🔍 Статус: {reg_status['message']}\n\n"
                f"Что вы хотите сделать?",
                reply_markup=InlineKeyboardMarkup(inline_keyboard=keyboard_buttons)
            )
    else:
        # Получаем имя пользователя из Telegram
        user_name = callback.from_user.first_name or "друг"

        # Отправляем приветственное мотивационное сообщение с кнопкой "Продолжить"
        await state.set_state(UserRegistration.waiting_for_start_confirmation)
        await bot.send_message(
            chat_id=telegram_id,
            text=f"Привет, {user_name}! 👋 Я GoPrime — твой личный мотивационный помощник в Telegram. Я помогу тебе достигать целей шаг за шагом: каждый день буду предлагать простые, но мощные задания, адаптированные под твои приоритеты — фитнес, обучение, карьера, хобби или что-то своё. Расскажи о своей главной цели, и мы сразу начнём! Готов к первым шагам к успеху? 🚀",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="▶️ Продолжить", callback_data="start_registration")]
            ])
        )

@router.callback_query(lambda c: c.data == "cancel_registration")
async def handle_cancel_registration(callback: CallbackQuery, state: FSMContext):
    """Обработка отмены регистрации"""
    await callback.answer()
    await state.clear()

    await callback.message.edit_text(
        "❌ Регистрация отменена.\n\n"
        "Вы можете начать заново командой /start",
        reply_markup=None
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
    else:
        # Проверяем существование реферального кода
        if referral_code:
            blogger = await db.get_blogger_by_referral_code(referral_code.upper())
            if not blogger:
                await message.answer(
                    f"❌ Реферальный код '{referral_code}' не найден!\n\n"
                    "Пожалуйста, проверьте правильность написания кода или нажмите 'Пропустить', "
                    "если у вас нет реферального кода.",
                    reply_markup=ReplyKeyboardMarkup(
                        keyboard=[[KeyboardButton(text="Пропустить")]],
                        resize_keyboard=True,
                        one_time_keyboard=True
                    )
                )
                return
            # Код существует, продолжаем
            referral_code = referral_code.upper()

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

    # Переходим к выбору подписки без сообщения об успешной регистрации
    await state.set_state(UserRegistration.waiting_for_subscription)
    await state.update_data(selected_level_index=0)  # Начинаем с первого уровня
    
    await message.edit_text(
        f"💎 Выберите уровень подписки:\n\n"
        f"{get_subscription_level_text(0)}",
        parse_mode="HTML",
        reply_markup=create_subscription_level_keyboard(0)
    )

@router.callback_query(UserRegistration.waiting_for_subscription, lambda c: c.data.startswith("sub_level_"))
async def handle_subscription_level_navigation(callback: CallbackQuery, state: FSMContext):
    """Обработка навигации по уровням подписки"""
    await callback.answer()
    
    if callback.data == "sub_level_disabled":
        await callback.answer("Это крайний уровень", show_alert=True)
        return
    
    if callback.data == "sub_level_info":
        await callback.answer("Используйте стрелки для переключения уровней", show_alert=True)
        return
    
    # Получаем индекс уровня из callback_data
    level_index = int(callback.data.replace("sub_level_", ""))
    
    if level_index < 0 or level_index >= len(SUBSCRIPTION_LEVELS):
        await callback.answer("Неверный уровень", show_alert=True)
        return
    
    # Сохраняем выбранный уровень в состоянии
    await state.update_data(selected_level_index=level_index)
    
    # Обновляем сообщение с новым уровнем
    await callback.message.edit_text(
        f"💎 Выберите уровень подписки:\n\n"
        f"{get_subscription_level_text(level_index)}",
        parse_mode="HTML",
        reply_markup=create_subscription_level_keyboard(level_index)
    )

@router.callback_query(UserRegistration.waiting_for_subscription, lambda c: c.data.startswith("sub_confirm_"))
async def handle_subscription_confirmation(callback: CallbackQuery, state: FSMContext):
    """Обработка подтверждения выбора уровня подписки"""
    await callback.answer()
    
    # Проверяем, что пользователь не является ботом
    if callback.from_user.is_bot:
        logger.warning(f"Попытка подписки от бота: {callback.from_user.id}")
        return

    # Получаем индекс уровня из callback_data
    level_index = int(callback.data.replace("sub_confirm_", ""))
    
    if level_index < 0 or level_index >= len(SUBSCRIPTION_LEVELS):
        await callback.answer("Неверный уровень", show_alert=True)
        return
    
    level = SUBSCRIPTION_LEVELS[level_index]
    user_id = callback.from_user.id
    
    # Создаем timestamp
    now = int(datetime.datetime.now(datetime.timezone.utc).timestamp())
    
    # Получаем информацию о боте
    bot_info = await bot.get_me()
    bot_name = bot_info.username or "MotivationBot"
    
    # Создаем платеж через WATA API
    result = await wata_create_payment(
        user_mid=user_id,
        money=level['price'],
        months=level['months'],
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
            amount=level['price'],
            months=level['months'],
            status=PaymentStatus.PENDING,
            created_at=now,
            currency="RUB",
            payment_method="WATA",
            subscription_type="standard",
            subscription_level=level['level']  # Сохраняем уровень подписки
        )
        
        payment_db_id = await db.save_payment(payment)
        
        # Отправляем пользователю ссылку на оплату
        await callback.message.edit_text(
            f"💳 <b>Подписка: {level['name']}</b>\n\n"
            f"⏱ Период: {level['description']}\n"
            f"💰 Стоимость: {level['price']} ₽\n\n"
            f"Ссылка для оплаты: {payment_link}\n\n"
            f"⏰ Ссылка действительна 1 час",
            parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="💳 Оплатить", url=payment_link)],
                [InlineKeyboardButton(text="🔄 Проверить оплату", callback_data=f"check_payment_{payment_db_id}")]
            ])
        )
        
        # Переходим к состоянию ожидания оплаты
        await state.set_state(UserRegistration.waiting_for_payment)
        await state.update_data(current_payment_id=payment_db_id)
        
    else:
        logger.error(f"Не удалось создать платеж для пользователя {user_id}")
        await bot.send_message(
            chat_id=callback.from_user.id,
            text="❌ Ошибка создания платежа. Попробуйте позже или обратитесь в поддержку."
        )

@router.callback_query(UserRegistration.waiting_for_payment, lambda c: c.data.startswith("check_payment_"))
async def check_payment_callback(callback: CallbackQuery, state: FSMContext):
    """Обработка проверки оплаты"""
    await callback.answer()

    # Проверяем, что пользователь не является ботом
    if callback.from_user.is_bot:
        logger.warning(f"Попытка проверки платежа от бота: {callback.from_user.id}")
        return

    payment_db_id = int(callback.data.replace("check_payment_", ""))
    logger.info(f"Проверка платежа ID: {payment_db_id} для пользователя {callback.from_user.id}")

    # Получаем платеж из БД по ID
    async with aiosqlite.connect("bot_database.db") as conn:
        conn.row_factory = aiosqlite.Row
        cursor = await conn.execute("SELECT * FROM payments WHERE id = ?", (payment_db_id,))
        row = await cursor.fetchone()

    payment = None
    if row:
        # Проверяем наличие subscription_level в результате
        subscription_level = 1  # По умолчанию
        try:
            subscription_level = row['subscription_level'] if row['subscription_level'] else 1
        except (KeyError, IndexError):
            subscription_level = 1
        
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
            subscription_type=row['subscription_type'],
            subscription_level=subscription_level
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

            # Получаем текущего пользователя для проверки активной подписки
            user = await db.get_user(payment.user_id)

            # Создаем подписку с учетом активной подписки (суммируем время)
            subscription_start = current_time

            # Базовое время новой подписки
            new_subscription_duration = payment.months * 30 * 24 * 60 * 60  # Примерно в секундах

            # Если есть активная подписка, добавляем оставшееся время
            if user and user.subscription_active and user.subscription_end and user.subscription_end > current_time:
                remaining_time = user.subscription_end - current_time
                subscription_end = subscription_start + new_subscription_duration + remaining_time
                logger.info(f"Суммируем подписку: {remaining_time} сек осталось + {new_subscription_duration} сек новой = {subscription_end - subscription_start} сек")
            else:
                subscription_end = subscription_start + new_subscription_duration

            # Используем уровень подписки из платежа
            subscription_level = payment.subscription_level if payment.subscription_level else 1
            
            subscription = Subscription(
                user_id=payment.user_id,
                payment_id=payment.id,
                start_date=subscription_start,
                end_date=subscription_end,
                months=payment.months,
                subscription_level=subscription_level,
                status=SubscriptionStatus.ACTIVE,
                auto_renew=False,
                created_at=current_time,
                updated_at=current_time
            )

            subscription_id = await db.save_subscription(subscription)

            # Активируем подписку пользователя
            await db.activate_user_subscription(payment.user_id, subscription_start, subscription_end)

            logger.info(f"Подписка {subscription_id} активирована для пользователя {payment.user_id}")

            # Проверяем, есть ли у пользователя карточка игрока
            player_stats = await db.get_player_stats(payment.user_id)
            
            if not player_stats:
                # Если карточки нет, переходим к созданию карточки игрока
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
                # Если карточка уже есть, просто отправляем уведомление
                await callback.message.edit_text(
                    f"✅ Оплата подтверждена!\n\n"
                    f"🎉 Подписка на {payment.months} месяцев активирована!\n\n"
                    f"📅 Дата окончания: {datetime.datetime.fromtimestamp(subscription_end).strftime('%d.%m.%Y')}\n\n"
                    f"🚀 Теперь вы можете пользоваться всеми функциями бота!",
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

    # Проверяем, является ли это заменой фото
    data = await state.get_data()
    is_photo_change = data.get('is_photo_change', False)

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

        if is_photo_change:
            # Это замена фото - используем существующие характеристики
            await message.answer("📸 Заменяю фото... Характеристики остаются прежними.")
            existing_stats = await db.get_player_stats(user_id)
            if existing_stats:
                stats = {
                    'strength': existing_stats.strength,
                    'agility': existing_stats.agility,
                    'endurance': existing_stats.endurance
                }
            else:
                # Если статистики нет, анализируем заново
                await message.answer("🤖 Анализирую ваше фото и определяю характеристики...")
                stats = await analyze_player_photo(photo_bytes)
        else:
            # Это создание новой карточки - анализируем характеристики
            await message.answer("🤖 Анализирую ваше фото и определяю характеристики...")
            stats = await analyze_player_photo(photo_bytes)

        # Получаем статистику пользователя для карточки
        user_stats = await db.get_user_stats(user_id)
        level = user_stats.level if user_stats else 1
        rank = user_stats.rank.value if user_stats else 'F'
        experience = user_stats.experience if user_stats else 0
        
        # Получаем позицию в рейтинге
        rating_position = await db.get_user_rating_position(user_id)

        # Создаем изображение карточки игрока
        card_stats = {
            'strength': stats['strength'],
            'agility': stats['agility'],
            'endurance': stats['endurance'],
            'intelligence': 50,
            'charisma': 50
        }
        logger.info(f"Создание карточки с характеристиками: {card_stats}")
        try:
            # Сначала пытаемся использовать Node.js сервис
            card_image_path = await create_player_card_image_nodejs(
                photo_path=photo_path,
                nickname=nickname,
                experience=experience,
                level=level,
                rank=rank,
                rating_position=rating_position,
                stats=card_stats
            )
        except Exception as e:
            # Fallback на PIL если Node.js сервис недоступен
            logger.warning(f"Используем PIL fallback: {e}")
            card_image_path = await create_player_card_image(
                photo_path=photo_path,
                nickname=nickname,
                experience=experience,
                stats=card_stats,
                level=level,
                rank=rank,
                rating_position=rating_position
            )

        if is_photo_change:
            # Это замена фото - обновляем существующую запись
            existing_stats = await db.get_player_stats(user_id)
            if existing_stats:
                # Обновляем только фото и карточку
                existing_stats.photo_path = photo_path
                existing_stats.card_image_path = card_image_path
                existing_stats.updated_at = int(datetime.datetime.now().timestamp())

                # Сохраняем обновленные статы
                await db.save_player_stats(existing_stats)

                await message.answer("✅ Фото успешно заменено! Характеристики остались прежними.")
            else:
                # Если статистики нет, создаем заново (на всякий случай)
                await message.answer("⚠️ Статистика не найдена, создаю новую карточку...")

                player_stats = PlayerStats(
                    user_id=user_id,
                    nickname=nickname,
                    experience=0,
                    strength=stats['strength'],
                    agility=stats['agility'],
                    endurance=stats['endurance'],
                    intelligence=50,
                    charisma=50,
                    photo_path=photo_path,
                    card_image_path=card_image_path,
                    created_at=int(datetime.datetime.now().timestamp()),
                    updated_at=int(datetime.datetime.now().timestamp())
                )
                await db.save_player_stats(player_stats)
        else:
            # Это создание новой карточки
            # Создаем объект статов игрока
            logger.info(f"Создаем PlayerStats для user_id={user_id} с характеристиками: strength={stats['strength']}, agility={stats['agility']}, endurance={stats['endurance']}")
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
            logger.info(f"PlayerStats объект создан: strength={player_stats.strength}, agility={player_stats.agility}, endurance={player_stats.endurance}")

            # Сохраняем статы в базу данных
            await db.save_player_stats(player_stats)
            logger.info(f"PlayerStats сохранены в БД для user_id={user_id}")

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

    # Проверяем активную подписку
    is_active, error_msg = await check_user_subscription(user_id)
    if not is_active:
        await message.answer(
            error_msg,
            parse_mode="HTML",
            reply_markup=create_main_menu_keyboard()
        )
        return

    # Проверяем, есть ли уже активное задание
    active_task = await db.get_active_daily_task(user_id)
    if active_task:
        logger.info(f"У пользователя {user_id} уже есть активное задание со статусом {active_task.status}")
        if active_task.status == TaskStatus.SUBMITTED:
            await message.answer(
                "⏳ <b>У вас есть задание на проверке!</b>\n\n"
                "Ваше задание отправлено на проверку модератору. Дождитесь результата проверки.\n\n"
                "Используйте кнопку '📋 Активные задания' для просмотра статуса.",
                parse_mode="HTML",
                reply_markup=create_main_menu_keyboard()
            )
        else:
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

    task_message = (
        f"🎯 <b>Новое задание получено!</b>\n\n"
        f"📝 <b>Задание:</b>\n{task_description}\n\n"
        f"⏰ <b>Время на выполнение:</b> 24 часа\n\n"
        f"📸 <b>Для сдачи задания:</b> отправьте фото или видео выполнения\n\n"
        f"Удачи в выполнении!"
    )
    
    # Разбиваем длинное сообщение на части, если необходимо
    message_parts = split_long_message(task_message)
    for i, part in enumerate(message_parts):
        # Клавиатуру добавляем только к последней части
        reply_markup = create_main_menu_keyboard() if i == len(message_parts) - 1 else None
        await message.answer(part, parse_mode="HTML", reply_markup=reply_markup)

@router.message(F.text == "📋 Активные задания")
async def handle_active_tasks(message: Message, state: FSMContext):
    """Обработка просмотра активных заданий"""
    user_id = message.from_user.id

    # Проверяем активную подписку
    is_active, error_msg = await check_user_subscription(user_id)
    if not is_active:
        await message.answer(
            error_msg,
            parse_mode="HTML",
            reply_markup=create_main_menu_keyboard()
        )
        return

    # Получаем активное задание
    active_task = await db.get_active_daily_task(user_id)

    # Если нет активного задания, проверяем недавно проверенные задания
    if not active_task:
        recently_checked_task = await db.get_recently_checked_task(user_id, hours=24)
        if recently_checked_task:
            if recently_checked_task.status == TaskStatus.APPROVED:
                task_message = (
                    f"✅ <b>Ваше задание было одобрено!</b>\n\n"
                    f"📝 <b>Задание:</b>\n{recently_checked_task.task_description}\n\n"
                    f"🎉 Задание успешно выполнено и одобрено модератором!\n\n"
                    f"Получите новое задание для продолжения!"
                )
                message_parts = split_long_message(task_message)
                for i, part in enumerate(message_parts):
                    reply_markup = create_main_menu_keyboard() if i == len(message_parts) - 1 else None
                    await message.answer(part, parse_mode="HTML", reply_markup=reply_markup)
            elif recently_checked_task.status == TaskStatus.REJECTED:
                reason_text = ""
                if recently_checked_task.moderator_comment:
                    reason_text = f"\n\n📋 <b>Причина:</b>\n{recently_checked_task.moderator_comment}"
                task_message = (
                    f"❌ <b>Ваше задание было отклонено</b>\n\n"
                    f"📝 <b>Задание:</b>\n{recently_checked_task.task_description}{reason_text}\n\n"
                    f"💡 Попробуйте выполнить задание лучше и отправьте снова!\n\n"
                    f"Получите новое задание!"
                )
                message_parts = split_long_message(task_message)
                for i, part in enumerate(message_parts):
                    reply_markup = create_main_menu_keyboard() if i == len(message_parts) - 1 else None
                    await message.answer(part, parse_mode="HTML", reply_markup=reply_markup)
            return
        
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

    # Проверяем статус задания
    if active_task.status == TaskStatus.SUBMITTED:
        # Задание отправлено на проверку
        task_message = (
            f"📋 <b>Ваше активное задание</b>\n\n"
            f"📝 <b>Задание:</b>\n{active_task.task_description}\n\n"
            f"⏳ <b>Статус:</b> На проверке\n\n"
            f"Ваше задание отправлено на проверку модератору. Ожидайте результата!"
        )
        message_parts = split_long_message(task_message)
        for i, part in enumerate(message_parts):
            reply_markup = create_main_menu_keyboard() if i == len(message_parts) - 1 else None
            await message.answer(part, parse_mode="HTML", reply_markup=reply_markup)
        return

    # Задание ожидает выполнения
    # Форматируем время
    hours = time_left // 3600
    minutes = (time_left % 3600) // 60

    task_message = (
        f"📋 <b>Ваше активное задание</b>\n\n"
        f"📝 <b>Задание:</b>\n{active_task.task_description}\n\n"
        f"⏰ <b>Осталось времени:</b> {hours}ч {minutes}мин\n"
        f"📸 <b>Статус:</b> Ожидает выполнения\n\n"
        f"Для сдачи задания отправьте фото или видео выполнения в чат!"
    )
    message_parts = split_long_message(task_message)
    for i, part in enumerate(message_parts):
        reply_markup = create_main_menu_keyboard() if i == len(message_parts) - 1 else None
        await message.answer(part, parse_mode="HTML", reply_markup=reply_markup)

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
        [InlineKeyboardButton(text="🎯 Сменить цель", callback_data="change_goal")],
        [InlineKeyboardButton(text="⭐ Мои привилегии", callback_data="my_privileges")]
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

    # Получаем детальную информацию о ранге
    rank_info = await db.get_user_rank_info(user_id)

    # Формируем текст ранга
    if rank_info:
        rank_text = (
            f"🏅 <b>Ранг:</b> {rank_info['current_rank_emoji']} {rank_info['current_rank_name']} ({rank_info['current_rank'].value})\n"
            f"📈 <b>Прогресс:</b> {rank_info['experience_in_rank']}/{rank_info['experience_in_rank'] + rank_info['experience_to_next_rank']} XP "
            f"({rank_info['progress_percentage']:.1f}%)\n"
        )

        if rank_info['next_rank_info']:
            next_rank, next_exp = rank_info['next_rank_info']
            from rank_config import RANK_EMOJIS, RANK_NAMES
            next_rank_emoji = RANK_EMOJIS.get(next_rank, "")
            next_rank_name = RANK_NAMES.get(next_rank, str(next_rank))
            rank_text += f"🎯 <b>Следующий ранг:</b> {next_rank_emoji} {next_rank_name} ({next_exp} XP)\n"
        else:
            rank_text += "🏆 <b>Максимальный ранг достигнут!</b>\n"
    else:
        rank_text = f"🏅 <b>Ранг:</b> {user_statistics.rank.value}\n"

    await message.answer(
        f"👤 <b>Профиль игрока</b>\n\n"
        f"🏆 <b>Ник:</b> {player_stats.nickname}\n"
        f"⭐ <b>Опыт:</b> {user_statistics.experience} | 📊 <b>Уровень:</b> {user_statistics.level}\n"
        f"{rank_text}"
        f"🔥 <b>Стрик:</b> {user_statistics.current_streak} дней\n"
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

@router.callback_query(lambda c: c.data == "go_to_profile")
async def handle_go_to_profile(callback: CallbackQuery, state: FSMContext):
    """Обработка перехода в профиль из команды /start"""
    await callback.answer()
    user_id = callback.from_user.id

    # Проверяем, что пользователь не является ботом
    if callback.from_user.is_bot:
        logger.warning(f"Попытка доступа к профилю от бота: {user_id}")
        await callback.message.answer(
            "❌ <b>Ошибка</b>\n\n"
            "Боты не могут использовать эту функцию.",
            parse_mode="HTML"
        )
        return
    
    # Получаем данные пользователя
    user = await db.get_user(user_id)
    player_stats = await db.get_player_stats(user_id)
    user_statistics = await db.get_user_stats(user_id)
    
    if not user or not player_stats or not user_statistics:
        await callback.message.answer(
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
        [InlineKeyboardButton(text="🎯 Сменить цель", callback_data="change_goal")],
        [InlineKeyboardButton(text="⭐ Мои привилегии", callback_data="my_privileges")]
    ])
    
    # Сначала отправляем изображение карточки, если оно существует
    if player_stats.card_image_path and os.path.exists(player_stats.card_image_path):
        try:
            photo = FSInputFile(player_stats.card_image_path)
            await callback.message.answer_photo(
                photo,
                caption="🎮 <b>Ваша игровая карточка</b>",
                parse_mode="HTML"
            )
        except Exception as e:
            logger.warning(f"Не удалось отправить карточку: {e}")
    
    # Получаем детальную информацию о ранге
    rank_info = await db.get_user_rank_info(user_id)
    
    # Формируем текст ранга
    if rank_info:
        rank_text = (
            f"🏅 <b>Ранг:</b> {rank_info['current_rank_emoji']} {rank_info['current_rank_name']} ({rank_info['current_rank'].value})\n"
            f"📈 <b>Прогресс:</b> {rank_info['experience_in_rank']}/{rank_info['experience_in_rank'] + rank_info['experience_to_next_rank']} XP "
            f"({rank_info['progress_percentage']:.1f}%)\n"
        )
        
        if rank_info['next_rank_info']:
            next_rank, next_exp = rank_info['next_rank_info']
            from rank_config import RANK_EMOJIS, RANK_NAMES
            next_rank_emoji = RANK_EMOJIS.get(next_rank, "")
            next_rank_name = RANK_NAMES.get(next_rank, str(next_rank))
            rank_text += f"🎯 <b>Следующий ранг:</b> {next_rank_emoji} {next_rank_name} ({next_exp} XP)\n"
        else:
            rank_text += "🏆 <b>Максимальный ранг достигнут!</b>\n"
    else:
        rank_text = f"🏅 <b>Ранг:</b> {user_statistics.rank.value}\n"
    
    await callback.message.answer(
        f"👤 <b>Профиль игрока</b>\n\n"
        f"🏆 <b>Ник:</b> {player_stats.nickname}\n"
        f"⭐ <b>Опыт:</b> {user_statistics.experience} | 📊 <b>Уровень:</b> {user_statistics.level}\n"
        f"{rank_text}"
        f"🔥 <b>Стрик:</b> {user_statistics.current_streak} дней\n"
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
    
    # Показываем главное меню
    await state.set_state(UserRegistration.main_menu)
    await show_main_menu(callback.message)

@router.callback_query(lambda c: c.data == "continue_path")
async def handle_continue_path(callback: CallbackQuery, state: FSMContext):
    """Обработка кнопки 'Продолжить путь' для загрузки фото"""
    await callback.answer()
    user_id = callback.from_user.id
    
    # Проверяем, завершена ли регистрация
    user = await db.get_user(user_id)
    if not user:
        await callback.message.answer(
            "❌ Пользователь не найден. Пожалуйста, начните регистрацию заново.",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="🔄 Начать регистрацию", callback_data="start_registration")]
            ])
        )
        return
    
    # Проверяем, есть ли все необходимые данные для создания карточки
    if not user.name or not user.birth_date or not user.height or not user.weight:
        # Регистрация не завершена - предлагаем продолжить
        await callback.message.answer(
            "📝 Чтобы создать карточку игрока, нужно завершить регистрацию.\n\n"
            "Продолжить регистрацию?",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="▶️ Продолжить регистрацию", callback_data="resume_registration")]
            ])
        )
        return
    
    # Переходим к загрузке фото
    await state.set_state(UserRegistration.waiting_for_player_photo)
    await callback.message.answer(
        "🎮 <b>Создание карточки игрока</b>\n\n"
        "📸 Пожалуйста, загрузите ваше фото для создания игровой карточки.\n"
        "ИИ проанализирует ваше фото и определит стартовые характеристики:\n"
        "• 💪 Сила\n"
        "• 🤸 Ловкость\n"
        "• 🏃 Выносливость\n"
        "• 🧠 Интеллект (базовый: 50/100)\n"
        "• ✨ Харизма (базовый: 50/100)\n\n"
        "После анализа будет создана ваша уникальная игровая карточка!",
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="⬅️ Отмена", callback_data="back_to_start")]
        ])
    )

def get_achievement_description(achievement_type: str, achievement_value: int, custom_condition: Optional[str] = None) -> str:
    """Получение описания достижения"""
    if achievement_type == 'custom' and custom_condition:
        return custom_condition
    
    if achievement_type == 'rank':
        from rank_config import RANK_NAMES
        # achievement_value соответствует индексу ранга (1 = F, 2 = E, ..., 8 = S+)
        rank_order = list(RANK_NAMES.keys())
        rank = rank_order[achievement_value - 1] if 0 <= achievement_value - 1 < len(rank_order) else None
        if rank:
            rank_name = RANK_NAMES[rank]
            return f'Достижение ранга {rank_name} ({rank.value})'
        else:
            return f'Достижение ранга {achievement_value}'

    descriptions = {
        'streak': f'Стрик {achievement_value} дней подряд',
        'level': f'Достижение уровня {achievement_value}',
        'tasks': f'Выполнение {achievement_value} заданий',
        'experience': f'Набор {achievement_value} опыта'
    }
    return descriptions.get(achievement_type, f'{achievement_type}: {achievement_value}')

async def get_profile_text(user, player_stats, user_statistics, db) -> str:
    """Формирование текста профиля"""
    # Получаем информацию о ранге асинхронно
    rank_info = await db.get_user_rank_info(user.telegram_id)

    referral_text = f"🔗 <b>Реферальный код:</b> {user.referral_code}\n" if user.referral_code else ""

    # Формируем текст ранга
    if rank_info:
        rank_text = (
            f"🏅 <b>Ранг:</b> {rank_info['current_rank_emoji']} {rank_info['current_rank_name']} ({rank_info['current_rank'].value})\n"
            f"📈 <b>Прогресс:</b> {rank_info['experience_in_rank']}/{rank_info['experience_in_rank'] + rank_info['experience_to_next_rank']} XP\n"
        )
    else:
        rank_text = f"🏅 <b>Ранг:</b> {user_statistics.rank.value}\n"

    return (
        f"👤 <b>Профиль игрока</b>\n\n"
        f"🏆 <b>Ник:</b> {player_stats.nickname}\n"
        f"⭐ <b>Опыт:</b> {user_statistics.experience} | 📊 <b>Уровень:</b> {user_statistics.level}\n"
        f"{rank_text}"
        f"🔥 <b>Стрик:</b> {user_statistics.current_streak} дней\n"
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

    # Получаем активную подписку пользователя
    active_subscription = await db.get_active_subscription(user_id)
    subscription_level = active_subscription.subscription_level if active_subscription else None

    # Получаем призы от главного модератора (для всех и для уровня подписки пользователя)
    admin_prizes = await db.get_prizes(prize_type=PrizeType.ADMIN, is_active=True, subscription_level=subscription_level)

    # Получаем призы от блогера (если есть реферальный код)
    blogger_prizes = []
    if user and user.referral_code:
        blogger_prizes = await db.get_prizes(prize_type=PrizeType.BLOGGER, referral_code=user.referral_code, is_active=True, subscription_level=subscription_level)

    prize_text = "🎁 <b>Текущие призы</b>\n\n"

    # Призы от главного модератора
    if admin_prizes:
        prize_text += "👑 <b>Призы от главного модератора:</b>\n"
        for prize in admin_prizes:
            prize_text += f"{prize.emoji} <b>{prize.title}</b>"
            if prize.subscription_level:
                level_names = {2: "Продвинутый", 3: "Мастер"}
                prize_text += f" <i>(для уровня {prize.subscription_level} - {level_names.get(prize.subscription_level, '')})</i>"
            prize_text += "\n"
            if prize.description:
                prize_text += f"   └ {prize.description}\n"
            prize_text += f"   └ Достижение: {get_achievement_description(prize.achievement_type, prize.achievement_value, prize.custom_condition)}\n\n"
    else:
        prize_text += "👑 <b>Призы от главного модератора:</b>\n"
        prize_text += "   └ Пока нет активных призов\n\n"

    # Призы от блогера
    if user and user.referral_code:
        if blogger_prizes:
            prize_text += f"📣 <b>Призы от блогера '{user.referral_code}':</b>\n"
            for prize in blogger_prizes:
                prize_text += f"{prize.emoji} <b>{prize.title}</b>"
                if prize.subscription_level:
                    level_names = {2: "Продвинутый", 3: "Мастер"}
                    prize_text += f" <i>(для уровня {prize.subscription_level} - {level_names.get(prize.subscription_level, '')})</i>"
                prize_text += "\n"
                if prize.description:
                    prize_text += f"   └ {prize.description}\n"
                prize_text += f"   └ Достижение: {get_achievement_description(prize.achievement_type, prize.achievement_value, prize.custom_condition)}\n\n"
        else:
            prize_text += f"📣 <b>Призы от блогера '{user.referral_code}':</b>\n"
            prize_text += "   └ Пока нет активных призов\n\n"
    else:
        prize_text += "📣 <b>Призы от блогера:</b>\n"
        prize_text += "   └ Укажите реферальный код блогера в профиле для просмотра его призов\n\n"

    prize_text += "🏆 <b>Система достижений:</b>\n"
    prize_text += "Призы начисляются автоматически при достижении целей!\n\n"
    if subscription_level and subscription_level >= 2:
        prize_text += f"⭐ <b>Вы имеете доступ к специальным призам для уровня {subscription_level}!</b>\n\n"
    prize_text += "<i>Следите за своими достижениями в профиле!</i>"

    await message.answer(
        prize_text,
        parse_mode="HTML",
        reply_markup=create_main_menu_keyboard()
    )

@router.message(F.text == "🏆 Челленджи")
async def handle_challenges(message: Message, state: FSMContext):
    """Обработка просмотра челленджей"""
    user_id = message.from_user.id
    
    # Получаем данные пользователя для реферального кода
    user = await db.get_user(user_id)
    user_referral_code = user.referral_code if user else None
    
    # Получаем активную подписку пользователя для определения уровня
    active_subscription = await db.get_active_subscription(user_id)
    subscription_level = active_subscription.subscription_level if active_subscription else None
    
    # Получаем активные челленджи для уровня подписки пользователя и его реферального кода
    challenges = await db.get_active_challenges(
        subscription_level=subscription_level,
        user_referral_code=user_referral_code
    )
    
    if not challenges:
        await message.answer(
            "🏆 <b>Челленджи</b>\n\n"
            "📭 Пока нет активных челленджей для вашего уровня подписки.\n\n"
            "Следите за обновлениями! Новые челленджи появятся здесь.",
            parse_mode="HTML",
            reply_markup=create_main_menu_keyboard()
        )
        return
    
    text = "🏆 <b>Активные челленджи</b>\n\n"
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[])
    
    for challenge in challenges:
        # Проверяем, отправил ли пользователь уже ответ
        existing_submission = await db.get_user_challenge_submissions(user_id, challenge.id)
        
        level_indicator = ""
        if challenge.subscription_level:
            if challenge.subscription_level == 3:
                level_indicator = " 👑"
            elif challenge.subscription_level == 2:
                level_indicator = " 💎"
        
        # Добавляем индикатор для челленджей от блогера
        if challenge.referral_code:
            level_indicator += " 📢"
        
        status_emoji = "✅" if existing_submission else "🎯"
        status_text = " (ответ отправлен)" if existing_submission else ""
        
        text += f"{status_emoji} <b>{challenge.title}</b>{level_indicator}{status_text}\n"
        text += f"   └ {challenge.description[:100]}{'...' if len(challenge.description) > 100 else ''}\n"
        
        if challenge.expires_at:
            import time
            expires_date = time.strftime('%d.%m.%Y %H:%M', time.localtime(challenge.expires_at))
            text += f"   └ ⏰ До: {expires_date}\n"
        
        text += "\n"
        
        # Добавляем кнопку для просмотра/отправки ответа
        if existing_submission:
            if existing_submission.status == ChallengeSubmissionStatus.APPROVED:
                button_text = f"✅ {challenge.title[:30]} (одобрено)"
            elif existing_submission.status == ChallengeSubmissionStatus.REJECTED:
                button_text = f"❌ {challenge.title[:30]} (отклонено)"
            else:
                button_text = f"⏳ {challenge.title[:30]} (на проверке)"
        else:
            button_text = f"📤 Отправить ответ: {challenge.title[:25]}"
        
        keyboard.inline_keyboard.append([
            InlineKeyboardButton(
                text=button_text,
                callback_data=f"view_challenge_{challenge.id}"
            )
        ])
    
    keyboard.inline_keyboard.append([
        InlineKeyboardButton(text="⬅️ В меню", callback_data="back_to_main_menu")
    ])
    
    await message.answer(text, reply_markup=keyboard, parse_mode="HTML")
    await state.set_state(ChallengeStates.viewing_challenges)

@router.callback_query(lambda c: c.data.startswith("view_challenge_"))
async def handle_view_challenge(callback: CallbackQuery, state: FSMContext):
    """Просмотр деталей челленджа и отправка ответа"""
    await callback.answer()
    user_id = callback.from_user.id
    challenge_id = int(callback.data.replace("view_challenge_", ""))
    
    challenge = await db.get_challenge_by_id(challenge_id)
    if not challenge:
        await callback.message.edit_text("❌ Челлендж не найден.")
        return
    
    # Проверяем, отправил ли пользователь уже ответ
    existing_submission = await db.get_user_challenge_submissions(user_id, challenge_id)
    
    text = f"🏆 <b>{challenge.title}</b>\n\n"
    text += f"{challenge.description}\n\n"
    
    if challenge.expires_at:
        import time
        expires_date = time.strftime('%d.%m.%Y %H:%M', time.localtime(challenge.expires_at))
        text += f"⏰ <b>Срок действия:</b> до {expires_date}\n\n"
    
    if existing_submission:
        if existing_submission.status == ChallengeSubmissionStatus.APPROVED:
            text += "✅ <b>Ваш ответ одобрен!</b>\n\n"
            if existing_submission.moderator_comment:
                text += f"💬 <b>Комментарий модератора:</b> {existing_submission.moderator_comment}\n\n"
        elif existing_submission.status == ChallengeSubmissionStatus.REJECTED:
            text += "❌ <b>Ваш ответ отклонен</b>\n\n"
            if existing_submission.moderator_comment:
                text += f"💬 <b>Причина:</b> {existing_submission.moderator_comment}\n\n"
            text += "Вы можете отправить новый ответ."
        else:
            text += "⏳ <b>Ваш ответ на проверке</b>\n\n"
            text += "Ожидайте решения модератора."
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[])
    
    # Если медиафайл есть, отправляем его отдельно
    if challenge.media_path and os.path.exists(challenge.media_path):
        try:
            if challenge.media_path.endswith(('.jpg', '.jpeg', '.png')):
                photo = FSInputFile(challenge.media_path)
                await callback.message.answer_photo(photo, caption=text, parse_mode="HTML")
            elif challenge.media_path.endswith(('.mp4', '.avi', '.mov')):
                video = FSInputFile(challenge.media_path)
                await callback.message.answer_video(video, caption=text, parse_mode="HTML")
            else:
                await callback.message.edit_text(text, reply_markup=keyboard, parse_mode="HTML")
        except Exception as e:
            logger.error(f"Ошибка отправки медиафайла челленджа: {e}")
            await callback.message.edit_text(text, reply_markup=keyboard, parse_mode="HTML")
    else:
        await callback.message.edit_text(text, reply_markup=keyboard, parse_mode="HTML")
    
    # Если ответ еще не отправлен или был отклонен, показываем кнопку отправки
    if not existing_submission or existing_submission.status == ChallengeSubmissionStatus.REJECTED:
        keyboard.inline_keyboard.append([
            InlineKeyboardButton(text="📤 Отправить ответ", callback_data=f"submit_challenge_{challenge_id}")
        ])
    
    keyboard.inline_keyboard.append([
        InlineKeyboardButton(text="⬅️ Назад к челленджам", callback_data="back_to_challenges")
    ])
    
    await callback.message.answer(
        "Выберите действие:",
        reply_markup=keyboard
    )

@router.callback_query(lambda c: c.data.startswith("submit_challenge_"))
async def handle_submit_challenge_start(callback: CallbackQuery, state: FSMContext):
    """Начало процесса отправки ответа на челлендж"""
    await callback.answer()
    user_id = callback.from_user.id
    challenge_id = int(callback.data.replace("submit_challenge_", ""))
    
    challenge = await db.get_challenge_by_id(challenge_id)
    if not challenge:
        await callback.message.edit_text("❌ Челлендж не найден.")
        return
    
    # Сохраняем ID челленджа в состоянии
    await state.update_data(challenge_id=challenge_id)
    
    text = f"📤 <b>Отправка ответа на челлендж</b>\n\n"
    text += f"🏆 <b>{challenge.title}</b>\n\n"
    text += "Отправьте фото или видео вашего ответа (до 30 секунд для видео).\n"
    text += "Вы также можете добавить текстовый комментарий после загрузки медиафайла."
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="❌ Отмена", callback_data=f"view_challenge_{challenge_id}")]
    ])
    
    await callback.message.edit_text(text, reply_markup=keyboard, parse_mode="HTML")
    await state.set_state(ChallengeStates.submitting_challenge)

@router.message(ChallengeStates.submitting_challenge, F.photo | F.video)
async def handle_challenge_media_submission(message: Message, state: FSMContext):
    """Обработка загрузки медиафайла для ответа на челлендж"""
    user_id = message.from_user.id
    data = await state.get_data()
    challenge_id = data.get('challenge_id')
    
    if not challenge_id:
        await message.answer("❌ Ошибка: челлендж не найден.")
        await state.clear()
        return
    
    challenge = await db.get_challenge_by_id(challenge_id)
    if not challenge:
        await message.answer("❌ Челлендж не найден.")
        await state.clear()
        return
    
    try:
        # Создаем директорию для медиафайлов челленджей
        media_dir = "task_submissions"  # Используем ту же директорию
        os.makedirs(media_dir, exist_ok=True)
        
        # Определяем тип медиафайла и сохраняем его
        if message.photo:
            media_file = message.photo[-1]  # Самое большое фото
            file_extension = "jpg"
            file_name = f"{media_dir}/challenge_{challenge_id}_{user_id}_{int(datetime.datetime.now().timestamp())}.jpg"
        else:  # video
            media_file = message.video
            # Проверяем длительность видео (максимум 30 секунд)
            if media_file.duration and media_file.duration > 30:
                await message.answer("❌ Видео должно быть не длиннее 30 секунд.")
                return
            file_extension = media_file.file_name.split('.')[-1] if media_file.file_name else "mp4"
            file_name = f"{media_dir}/challenge_{challenge_id}_{user_id}_{int(datetime.datetime.now().timestamp())}.mp4"
        
        # Скачиваем файл
        file_bytes = await bot.download(media_file.file_id)
        
        # Сохраняем файл
        with open(file_name, 'wb') as f:
            f.write(file_bytes.read())
        
        # Сохраняем путь к файлу в состоянии
        await state.update_data(challenge_media_path=file_name)
        
        text = "✅ <b>Медиафайл загружен!</b>\n\n"
        text += "Теперь вы можете добавить текстовый комментарий к вашему ответу (или отправьте 'пропустить' чтобы отправить без комментария):"
        
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="⏭️ Пропустить комментарий", callback_data="skip_challenge_text")],
            [InlineKeyboardButton(text="❌ Отмена", callback_data=f"view_challenge_{challenge_id}")]
        ])
        
        await message.answer(text, reply_markup=keyboard, parse_mode="HTML")
        await state.set_state(ChallengeStates.waiting_for_challenge_text)
        
    except Exception as e:
        logger.error(f"Ошибка при сохранении медиафайла челленджа: {e}")
        await message.answer("❌ Ошибка при загрузке файла. Попробуйте еще раз.")

@router.message(ChallengeStates.submitting_challenge, ~F.photo & ~F.video)
async def handle_challenge_text_only_submission(message: Message, state: FSMContext):
    """Обработка отправки только текста без медиафайла"""
    user_id = message.from_user.id
    data = await state.get_data()
    challenge_id = data.get('challenge_id')
    
    if not challenge_id:
        await message.answer("❌ Ошибка: челлендж не найден.")
        await state.clear()
        return
    
    text = message.text.strip()
    if len(text) < 3:
        await message.answer("❌ Текст слишком короткий. Минимум 3 символа или отправьте фото/видео.")
        return
    
    # Сохраняем только текст
    await state.update_data(challenge_text=text, challenge_media_path=None)
    
    # Отправляем ответ
    await submit_challenge_response(message, state)

@router.message(ChallengeStates.waiting_for_challenge_text)
async def handle_challenge_text_input(message: Message, state: FSMContext):
    """Обработка ввода текстового комментария к ответу на челлендж"""
    user_id = message.from_user.id
    text = message.text.strip()
    
    if text.lower() == 'пропустить':
        text = None
    elif len(text) < 3:
        await message.answer("❌ Текст слишком короткий. Минимум 3 символа или отправьте 'пропустить'.")
        return
    
    await state.update_data(challenge_text=text)
    await submit_challenge_response(message, state)

@router.callback_query(lambda c: c.data == "skip_challenge_text")
async def handle_skip_challenge_text(callback: CallbackQuery, state: FSMContext):
    """Пропуск текстового комментария"""
    await callback.answer()
    await state.update_data(challenge_text=None)
    await submit_challenge_response(callback.message, state)

async def submit_challenge_response(message_or_callback, state: FSMContext):
    """Отправка ответа на челлендж"""
    if isinstance(message_or_callback, CallbackQuery):
        message = message_or_callback.message
    else:
        message = message_or_callback
    
    user_id = message.from_user.id
    data = await state.get_data()
    challenge_id = data.get('challenge_id')
    media_path = data.get('challenge_media_path')
    text = data.get('challenge_text')
    
    if not challenge_id:
        await message.answer("❌ Ошибка: челлендж не найден.")
        await state.clear()
        return
    
    if not media_path and not text:
        await message.answer("❌ Отправьте фото, видео или текст.")
        return
    
    # Создаем объект ответа
    submission = ChallengeSubmission(
        challenge_id=challenge_id,
        user_id=user_id,
        media_path=media_path,
        text=text,
        status=ChallengeSubmissionStatus.PENDING,
        created_at=int(datetime.datetime.now().timestamp())
    )
    
    # Сохраняем ответ в базу данных
    submission_id = await db.save_challenge_submission(submission)
    
    if submission_id:
        challenge = await db.get_challenge_by_id(challenge_id)
        await message.answer(
            f"✅ <b>Ответ отправлен!</b>\n\n"
            f"🏆 <b>{challenge.title}</b>\n\n"
            f"Ваш ответ отправлен на проверку модератору.\n"
            f"Вы получите уведомление о результате проверки.",
            parse_mode="HTML",
            reply_markup=create_main_menu_keyboard()
        )
    else:
        await message.answer("❌ Ошибка при отправке ответа. Попробуйте еще раз.")
    
    await state.clear()

@router.callback_query(lambda c: c.data == "back_to_challenges")
async def handle_back_to_challenges(callback: CallbackQuery, state: FSMContext):
    """Возврат к списку челленджей"""
    await callback.answer()
    await handle_challenges(callback.message, state)

@router.callback_query(lambda c: c.data == "back_to_main_menu")
async def handle_back_to_main_menu_from_challenges(callback: CallbackQuery, state: FSMContext):
    """Возврат в главное меню из челленджей"""
    await callback.answer()
    await state.set_state(UserRegistration.main_menu)
    
    # Удаляем сообщение с inline клавиатурой
    await callback.message.delete()
    
    # Отправляем новое сообщение с Reply клавиатурой
    await callback.message.answer(
        "🏠 <b>Главное меню</b>\n\n"
        "Выберите действие:",
        reply_markup=create_main_menu_keyboard(),
        parse_mode="HTML"
    )

@router.message(F.text == "💬 Поддержка")
async def handle_support(message: Message, state: FSMContext):
    """Обработка поддержки"""

    await message.answer(
        "💬 <b>Поддержка</b>\n\n"
        "Если у вас возникли вопросы или проблемы, обращайтесь в поддержку:\n\n"
        "💭 <b>Telegram:</b> @primetexpod\n\n"
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

    # Проверяем активную подписку
    is_active, error_msg = await check_user_subscription(user_id)
    if not is_active:
        await message.answer(
            error_msg,
            parse_mode="HTML",
            reply_markup=create_main_menu_keyboard()
        )
        return

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
    
    # Проверяем, что задание не уже отправлено на проверку
    if active_task.status == TaskStatus.SUBMITTED:
        await message.answer(
            "⏳ <b>Задание уже отправлено на проверку!</b>\n\n"
            "Ваше задание находится на проверке у модератора. Ожидайте результата.",
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
            task_message = (
                f"✅ <b>Задание отправлено на проверку!</b>\n\n"
                f"📝 <b>Задание:</b>\n{active_task.task_description}\n\n"
                f"⏳ <b>Статус:</b> Ожидает модерации\n\n"
                f"Вы получите уведомление о результате проверки."
            )
            message_parts = split_long_message(task_message)
            for i, part in enumerate(message_parts):
                reply_markup = create_main_menu_keyboard() if i == len(message_parts) - 1 else None
                await message.answer(part, parse_mode="HTML", reply_markup=reply_markup)
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

    # Получаем активную подписку пользователя
    active_subscription = await db.get_active_subscription(user_id)
    subscription_level = active_subscription.subscription_level if active_subscription else None

    # Получаем топ пользователей по городу
    city_rating = await db.get_top_users_by_city(user.city, 10)

    # Получаем топ пользователей по рангу
    rank_rating = await db.get_top_users_by_rank(user_stats.rank.value, 10)

    # Получаем топ пользователей среди подписчиков блогера (если есть реферальный код)
    referral_rating = None
    if user.referral_code:
        referral_rating = await db.get_top_users_by_referral_code(user.referral_code, 10)

    # Получаем рейтинг по уровню подписки для уровней 2 и 3
    level_2_rating = None
    level_3_rating = None
    if subscription_level and subscription_level >= 2:
        level_2_rating = await db.get_top_users_by_subscription_level(2, 10)
    if subscription_level and subscription_level >= 3:
        level_3_rating = await db.get_top_users_by_subscription_level(3, 10)

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

    # Дополнительный рейтинг для уровня 2
    if subscription_level and subscription_level >= 2:
        rating_text += "\n"
        rating_text += "⭐ <b>Топ уровня Продвинутый (уровень 2):</b>\n"
        if level_2_rating:
            for i, (name, level, exp, rank, city) in enumerate(level_2_rating, 1):
                rating_text += f"{i}. {name} - Ур.{level} ({rank})\n"
        else:
            rating_text += "Пока нет данных\n"

    # Дополнительный рейтинг для уровня 3
    if subscription_level and subscription_level >= 3:
        rating_text += "\n"
        rating_text += "💎 <b>Топ уровня Мастер (уровень 3):</b>\n"
        if level_3_rating:
            for i, (name, level, exp, rank, city) in enumerate(level_3_rating, 1):
                rating_text += f"{i}. {name} - Ур.{level} ({rank})\n"
        else:
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
        [InlineKeyboardButton(text="🎯 Сменить цель", callback_data="change_goal")],
        [InlineKeyboardButton(text="⭐ Мои привилегии", callback_data="my_privileges")]
    ])

    # Сначала отправляем изображение карточки, если оно существует
    if player_stats.card_image_path and os.path.exists(player_stats.card_image_path):
        try:
            photo = FSInputFile(player_stats.card_image_path)
            await callback.message.delete()  # Удаляем сообщение рейтинга
            await callback.message.answer_photo(
                photo,
                caption=await get_profile_text(user, player_stats, user_statistics, db),
                parse_mode="HTML",
                reply_markup=keyboard
            )
        except Exception as e:
            logger.error(f"Ошибка отправки фото профиля: {e}")
            # Если не удалось отправить фото, отправляем текстовую версию
            await callback.message.edit_text(
                await get_profile_text(user, player_stats, user_statistics, db),
                parse_mode="HTML",
                reply_markup=keyboard
            )
    else:
        # Отправляем текстовую версию профиля
        await callback.message.edit_text(
            await get_profile_text(user, player_stats, user_statistics, db),
            parse_mode="HTML",
            reply_markup=keyboard
        )

@router.callback_query(lambda c: c.data == "my_privileges")
async def handle_my_privileges(callback: CallbackQuery, state: FSMContext):
    """Обработка просмотра привилегий подписки"""
    await callback.answer()
    user_id = callback.from_user.id
    
    # Получаем активную подписку пользователя
    active_subscription = await db.get_active_subscription(user_id)
    
    if not active_subscription:
        await callback.message.answer(
            "❌ <b>Подписка не активна</b>\n\n"
            "У вас нет активной подписки. Оформите подписку, чтобы получить привилегии.",
            parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="💰 Оформить подписку", callback_data="subscribe")],
                [InlineKeyboardButton(text="⬅️ Назад", callback_data="back_to_profile")]
            ])
        )
        return
    
    # Получаем уровень подписки
    subscription_level = active_subscription.subscription_level
    
    # Находим информацию об уровне подписки
    level_info = None
    for level in SUBSCRIPTION_LEVELS:
        if level['level'] == subscription_level:
            level_info = level
            break
    
    if not level_info:
        # Fallback на уровень 1, если не найден
        level_info = SUBSCRIPTION_LEVELS[0]
    
    # Формируем текст привилегий
    privileges_text = f"⭐ <b>Мои привилегии</b>\n\n"
    privileges_text += f"📦 <b>Уровень подписки:</b> {level_info['name']}\n"
    privileges_text += f"⏱ <b>Период:</b> {level_info['description']}\n\n"
    privileges_text += f"🎁 <b>Ваши привилегии:</b>\n\n"
    
    # Добавляем список привилегий
    for feature in level_info['features']:
        privileges_text += f"{feature}\n"
    
    # Добавляем контакт специальной поддержки для уровней 2 и 3
    if subscription_level >= 2:
        privileges_text += f"\n💬 <b>Специальная поддержка:</b>\n"
        privileges_text += f"Telegram: @primetexpod\n"
        privileges_text += f"Для пользователей уровня {level_info['name']} доступна приоритетная поддержка!"
    
    await callback.message.answer(
        privileges_text,
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="⬅️ Назад", callback_data="back_to_profile")]
        ])
    )

@router.callback_query(lambda c: c.data == "change_photo")
async def handle_change_photo(callback: CallbackQuery, state: FSMContext):
    """Обработка замены фотографии"""
    await callback.answer()

    # Вместо редактирования отправляем новое сообщение
    await callback.message.answer(
        "📸 <b>Замена фотографии</b>\n\n"
        "Отправьте новое фото для анализа.\n"
        "Старые характеристики будут сохранены.\n\n"
        "<i>Только фото будет заменено, статы останутся прежними.</i>",
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="⬅️ Отмена", callback_data="profile")]
        ])
    )

    # Устанавливаем состояние для замены фото и флаг замены
    await state.set_state(UserRegistration.waiting_for_player_photo)
    await state.update_data(is_photo_change=True)

@router.callback_query(lambda c: c.data == "profile")
async def handle_profile_callback(callback: CallbackQuery, state: FSMContext):
    """Обработка возврата в профиль из различных состояний"""
    await callback.answer()

    # Очищаем состояние, если оно было установлено для замены фото
    await state.clear()

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

    # Формируем текст профиля
    profile_text = await get_profile_text(user, player_stats, user_statistics, db)

    # Создаем клавиатуру профиля
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📊 Статистика", callback_data="stats")],
        [InlineKeyboardButton(text="📸 Заменить фотографию", callback_data="change_photo")],
        [InlineKeyboardButton(text="💳 Подписка", callback_data="subscription")],
        [InlineKeyboardButton(text="⬅️ Назад в меню", callback_data="back_to_menu")]
    ])

    # Если есть карточка профиля, показываем её
    if player_stats.card_image_path and os.path.exists(player_stats.card_image_path):
        try:
            # Проверяем, есть ли у текущего сообщения фото
            if callback.message.photo:
                # Если сообщение содержит фото, обновляем caption
                await callback.message.edit_caption(
                    caption=profile_text,
                    reply_markup=keyboard,
                    parse_mode="HTML"
                )
            else:
                # Если сообщение не содержит фото, удаляем его и отправляем новое с фото
                await callback.message.delete()
                photo = FSInputFile(player_stats.card_image_path)
                await callback.message.answer_photo(
                    photo,
                    caption=profile_text,
                    parse_mode="HTML",
                    reply_markup=keyboard
                )
        except Exception as e:
            logger.error(f"Ошибка обновления фото профиля: {e}")
            # Если не удалось обновить фото, отправляем текстовую версию
            try:
                await callback.message.edit_text(
                    profile_text,
                    reply_markup=keyboard,
                    parse_mode="HTML"
                )
            except Exception:
                # Если не удалось редактировать, отправляем новое сообщение
                await callback.message.answer(
                    profile_text,
                    reply_markup=keyboard,
                    parse_mode="HTML"
                )
    else:
        # Отправляем текстовую версию профиля
        await callback.message.edit_text(
            profile_text,
            reply_markup=keyboard,
            parse_mode="HTML"
        )

@router.callback_query(lambda c: c.data == "payment_info")
async def handle_payment_info(callback: CallbackQuery, state: FSMContext):
    """Обработка информации об оплате"""
    await callback.answer()
    user_id = callback.from_user.id

    # Получаем данные о подписке
    user = await db.get_user(user_id)

    if not user or not user.subscription_active or not user.subscription_end:
        await callback.message.answer(
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

    await callback.message.answer(
        f"💳 <b>Информация об оплате</b>\n\n"
        f"📅 <b>Статус подписки:</b> {status}\n"
        f"🎯 <b>Доступ:</b> Все функции активны\n\n"
        f"Хотите продлить подписку?",
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="💰 Продлить подписку", callback_data="subscribe")]
        ])
    )

@router.callback_query(lambda c: c.data == "change_goal")
async def handle_change_goal(callback: CallbackQuery, state: FSMContext):
    """Обработка смены цели"""
    await callback.answer()

    # Проверяем, что пользователь не является ботом
    if callback.from_user.is_bot:
        logger.warning(f"Попытка смены цели от бота: {callback.from_user.id}")
        return

    await bot.send_message(
        chat_id=callback.from_user.id,
        text="🎯 <b>Смена цели</b>\n\n"
        "Расскажите о вашей новой цели (минимум 3 символа):",
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

    logger.info(f"Пользователь {user_id} ввел новую цель: '{goal}'")

    # Сохраняем цель во временном состоянии
    await state.update_data(goal=goal)
    await state.set_state(UserRegistration.changing_goal_confirmation)

    await message.answer(
        f"🎯 Ваша новая цель:\n\n<i>{goal}</i>\n\n"
        f"Уверены ли вы в этой формулировке?",
        reply_markup=create_goal_confirmation_keyboard()
    )

@router.callback_query(UserRegistration.changing_goal_confirmation)
async def process_goal_change_confirmation(callback: CallbackQuery, state: FSMContext):
    """Обработка подтверждения смены цели"""
    await callback.answer()
    
    # Проверяем, что пользователь не является ботом
    if callback.from_user.is_bot:
        logger.warning(f"Попытка подтверждения смены цели от бота: {callback.from_user.id}")
        return

    action = callback.data
    user_id = callback.from_user.id
    logger.info(f"process_goal_change_confirmation: callback.from_user.id = {user_id}, action = {action}")

    if action == "goal_confirm":
        # Пользователь подтвердил цель - сохраняем её
        data = await state.get_data()
        goal = data.get('goal', '')
        
        logger.info(f"Пользователь {user_id} подтвердил новую цель: '{goal}'")
        
        # Сохраняем новую цель в базу данных
        user = await db.get_user(user_id)
        if user:
            # Обновляем цель пользователя
            await db.update_user_field(user_id, 'goal', goal)
            logger.info(f"Цель пользователя {user_id} обновлена на: '{goal}'")

            await bot.edit_message_text(
                chat_id=callback.from_user.id,
                message_id=callback.message.message_id,
                text=f"✅ <b>Цель успешно обновлена!</b>\n\n"
                f"🎯 <b>Ваша новая цель:</b>\n"
                f"<i>{goal}</i>\n\n"
                f"Теперь вы можете получать персонализированные задания по этой цели.",
                parse_mode="HTML"
            )

            # Очищаем состояние и возвращаемся в главное меню
            await state.clear()
            await show_main_menu(callback.from_user.id)
        else:
            logger.error(f"Пользователь {user_id} не найден при обновлении цели")
            await bot.edit_message_text(
                chat_id=callback.from_user.id,
                message_id=callback.message.message_id,
                text="❌ <b>Ошибка обновления цели</b>\n\n"
                "Попробуйте позже или обратитесь в поддержку.",
                parse_mode="HTML"
            )

    elif action == "goal_improve":
        # Улучшаем цель с помощью ИИ
        logger.info(f"Пользователь {user_id} выбрал улучшение цели ИИ при смене")
        data = await state.get_data()
        original_goal = data.get('goal', '')

        # Отправляем сообщение о том, что ИИ работает
        await bot.edit_message_text(
            chat_id=callback.from_user.id,
            message_id=callback.message.message_id,
            text=f"🎯 Ваша цель:\n\n<i>{original_goal}</i>\n\n"
            f"🤖 Улучшаю формулировку с помощью ИИ...",
            reply_markup=None
        )

        # Вызываем OpenRouter API
        improved_goal = await improve_goal_with_ai(original_goal)
        logger.info(f"Цель улучшена ИИ для пользователя {user_id}: '{original_goal}' -> '{improved_goal}'")

        # Сохраняем улучшенную цель
        await state.update_data(goal=improved_goal)

        # Показываем улучшенную цель с той же клавиатурой
        await bot.edit_message_text(
            chat_id=callback.from_user.id,
            message_id=callback.message.message_id,
            text=f"🎯 Улучшенная цель:\n\n<i>{improved_goal}</i>\n\n"
            f"Теперь лучше звучит? Что скажете?",
            reply_markup=create_goal_confirmation_keyboard()
        )

    elif action == "goal_edit":
        # Возвращаемся к вводу цели
        logger.info(f"Пользователь {user_id} выбрал редактирование цели при смене")
        await state.set_state(UserRegistration.changing_goal)
        await bot.edit_message_text(
            chat_id=callback.from_user.id,
            message_id=callback.message.message_id,
            text="🎯 Хорошо, давайте переформулируем цель.\n\n"
            "Расскажите о вашей новой цели:",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="⬅️ Отмена", callback_data="profile")]
            ])
        )

@router.callback_query(lambda c: c.data == "stats")
async def handle_stats(callback: CallbackQuery, state: FSMContext):
    """Обработка просмотра статистики"""
    await callback.answer()
    user_id = callback.from_user.id

    # Получаем данные пользователя
    user = await db.get_user(user_id)
    user_stats = await db.get_user_stats(user_id)
    player_stats = await db.get_player_stats(user_id)

    if not user or not user_stats or not player_stats:
        await callback.message.edit_text(
            "❌ <b>Ошибка загрузки статистики</b>\n\n"
            "Попробуйте позже или обратитесь в поддержку.",
            parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="⬅️ Назад", callback_data="profile")]
            ])
        )
        return

    # Получаем информацию о ранге
    rank_info = await db.get_user_rank_info(user_id)

    # Получаем статистику заданий
    daily_tasks = await db.get_user_daily_tasks(user_id, limit=30)  # последние 30 дней

    # Подсчитываем статистику заданий
    completed_tasks = sum(1 for task in daily_tasks if task.status == TaskStatus.COMPLETED)
    total_tasks = len(daily_tasks)
    completion_rate = (completed_tasks / total_tasks * 100) if total_tasks > 0 else 0

    # Получаем текущую серию выполнений
    current_streak = user_stats.current_streak

    # Формируем текст статистики
    stats_text = (
        f"📊 <b>Детальная статистика</b>\n\n"
        f"👤 <b>Игрок:</b> {player_stats.nickname}\n"
        f"🏆 <b>Опыт:</b> {user_stats.experience} XP\n"
        f"📈 <b>Уровень:</b> {user_stats.level}\n"
    )

    if rank_info:
        stats_text += (
            f"🏅 <b>Ранг:</b> {rank_info['current_rank_emoji']} {rank_info['current_rank_name']}\n"
            f"📊 <b>Прогресс ранга:</b> {rank_info['experience_in_rank']}/{rank_info['experience_in_rank'] + rank_info['experience_to_next_rank']} XP\n"
            f"📈 <b>Прогресс:</b> {rank_info['progress_percentage']:.1f}%\n"
        )
    else:
        stats_text += f"🏅 <b>Ранг:</b> {user_stats.rank.value}\n"

    stats_text += (
        f"\n🔥 <b>Стрики:</b>\n"
        f"📅 <b>Текущий:</b> {current_streak} дней\n"
        f"🏆 <b>Лучший:</b> {user_stats.best_streak} дней\n"
        f"\n✅ <b>Задания:</b>\n"
        f"📝 <b>Всего создано:</b> {total_tasks}\n"
        f"✔️ <b>Выполнено:</b> {completed_tasks}\n"
        f"📊 <b>Процент выполнения:</b> {completion_rate:.1f}%\n"
        f"\n🏆 <b>Характеристики:</b>\n"
        f"💪 <b>Сила:</b> {player_stats.strength}/100\n"
        f"🤸 <b>Ловкость:</b> {player_stats.agility}/100\n"
        f"🏃 <b>Выносливость:</b> {player_stats.endurance}/100\n"
        f"🧠 <b>Интеллект:</b> {player_stats.intelligence}/100\n"
        f"✨ <b>Харизма:</b> {player_stats.charisma}/100\n"
    )

    # Создаем клавиатуру
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🏅 Рейтинг", callback_data="rating")],
        [InlineKeyboardButton(text="⬅️ Назад", callback_data="profile")]
    ])

    await callback.message.edit_text(
        stats_text,
        reply_markup=keyboard,
        parse_mode="HTML"
    )

@router.callback_query(lambda c: c.data == "subscription")
async def handle_subscription(callback: CallbackQuery, state: FSMContext):
    """Обработка просмотра подписки"""
    await callback.answer()
    user_id = callback.from_user.id

    # Получаем данные пользователя
    user = await db.get_user(user_id)

    if not user:
        await callback.message.edit_text(
            "❌ <b>Ошибка загрузки данных</b>\n\n"
            "Попробуйте позже или обратитесь в поддержку.",
            parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="⬅️ Назад", callback_data="profile")]
            ])
        )
        return

    # Проверяем статус подписки
    if user.subscription_active and user.subscription_end:
        from datetime import datetime
        days_left = (user.subscription_end - datetime.now()).days

        subscription_text = (
            f"💳 <b>Статус подписки</b>\n\n"
            f"✅ <b>Подписка активна</b>\n"
            f"📅 <b>Истекает:</b> {user.subscription_end.strftime('%d.%m.%Y')}\n"
            f"⏰ <b>Осталось:</b> {days_left} дней\n\n"
            f"🎁 <b>Преимущества активной подписки:</b>\n"
            f"• Неограниченное количество заданий\n"
            f"• Доступ ко всем функциям бота\n"
            f"• Приоритетная поддержка\n"
            f"• Детальная статистика прогресса\n"
        )

        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🔄 Продлить подписку", callback_data="subscribe")],
            [InlineKeyboardButton(text="⬅️ Назад", callback_data="profile")]
        ])
    else:
        subscription_text = (
            f"💳 <b>Статус подписки</b>\n\n"
            f"❌ <b>Подписка не активна</b>\n\n"
            f"🎁 <b>Преимущества подписки:</b>\n"
            f"• Неограниченное количество заданий\n"
            f"• Доступ ко всем функциям бота\n"
            f"• Приоритетная поддержка\n"
            f"• Детальная статистика прогресса\n\n"
            f"💰 <b>Тарифы:</b>\n"
            f"1 месяц - 200₽\n"
            f"3 месяца - 1200₽ (400₽/мес)\n"
            f"6 месяцев - 3000₽ (500₽/мес)\n"
            f"12 месяцев - 4000₽ (333₽/мес)\n"
        )

        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="💰 Оформить подписку", callback_data="subscribe")],
            [InlineKeyboardButton(text="⬅️ Назад", callback_data="profile")]
        ])

    await callback.message.edit_text(
        subscription_text,
        reply_markup=keyboard,
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

    # Переходим к состоянию выбора подписки
    await state.set_state(UserRegistration.waiting_for_subscription)
    await state.update_data(selected_level_index=0)  # Начинаем с первого уровня

    # Возвращаемся к выбору подписки
    await callback.message.edit_text(
        "💰 <b>Выберите уровень подписки</b>\n\n"
        f"{get_subscription_level_text(0)}",
        parse_mode="HTML",
        reply_markup=create_subscription_level_keyboard(0)
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
                "Authorization": f"Bearer {POLZA_API_KEY}",
                "Content-Type": "application/json",
                "HTTP-Referer": "https://t.me/motivation_bot",
                "X-Title": "Motivation Bot"
            }

            async with session.post(
                f"{POLZA_BASE_URL}/chat/completions",
                json=payload,
                headers=headers
            ) as response:
                if response.status in (200, 201):
                    data = await response.json()
                    task = data["choices"][0]["message"]["content"].strip()
                    return task
                else:
                    logger.error(f"Polza.ai API error: {response.status}")
                    return f"Поработать над целью: {user_goal[:50]}..."

    except Exception as e:
        logger.error(f"Error generating daily task: {e}")
        return f"Сделать шаг к цели: {user_goal[:50]}..."

@router.message(Command("subscribe"))
async def cmd_subscribe(message: Message, state: FSMContext):
    """Обработчик команды /subscribe для оформления подписки"""
    user_id = message.from_user.id
    user = await db.get_user(user_id)
    
    if not user:
        await message.answer(
            "❌ Пользователь не найден. Используйте /start для начала регистрации.",
            parse_mode="HTML"
        )
        return
    
    if not user.is_complete:
        await message.answer(
            "❌ Регистрация не завершена. Завершите регистрацию, чтобы оформить подписку.",
            parse_mode="HTML"
        )
        return
    
    # Переходим к выбору уровня подписки
    await state.update_data(selected_level_index=0)
    await message.answer(
        f"💎 Выберите уровень подписки:\n\n{get_subscription_level_text(0)}",
        parse_mode="HTML",
        reply_markup=create_subscription_level_keyboard(0)
    )
    await state.set_state(UserRegistration.waiting_for_subscription)

@router.message(Command("help"))
async def cmd_help(message: Message):
    """Обработчик команды помощи"""
    help_text = (
        "🤖 <b>Справка по мотивационному боту</b>\n\n"
        "Я — твой личный мотивационный помощник! Помогаю достигать целей через ежедневные задания.\n\n"
        "📋 <b>Команды:</b>\n"
        "/start - Начать регистрацию или проверить статус\n"
        "/subscribe - Оформить или продлить подписку\n"
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

# Обработчик для состояния ожидания подтверждения начала регистрации
@router.message(UserRegistration.waiting_for_start_confirmation)
async def handle_waiting_for_start_confirmation(message: Message, state: FSMContext):
    """Обработчик сообщений в состоянии ожидания подтверждения начала регистрации"""
    user_name = message.from_user.first_name or "друг"
    await message.answer(
        f"Привет, {user_name}! 👋\n\n"
        "Пожалуйста, нажмите кнопку '▶️ Продолжить' для начала регистрации.",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="▶️ Продолжить", callback_data="start_registration")]
        ])
    )

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
    # Получаем bot_id один раз при старте задачи
    bot_info = await bot.get_me()
    bot_id = bot_info.id
    
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
                    # Получаем текущего пользователя для проверки активной подписки
                    user = await db.get_user(payment.user_id)

                    # Создаем подписку с учетом активной подписки (суммируем время)
                    subscription_start = current_time

                    # Базовое время новой подписки
                    new_subscription_duration = payment.months * 30 * 24 * 60 * 60  # Примерно в секундах

                    # Если есть активная подписка, добавляем оставшееся время
                    if user and user.subscription_active and user.subscription_end and user.subscription_end > current_time:
                        remaining_time = user.subscription_end - current_time
                        subscription_end = subscription_start + new_subscription_duration + remaining_time
                        logger.info(f"Суммируем подписку: {remaining_time} сек осталось + {new_subscription_duration} сек новой = {subscription_end - subscription_start} сек")
                    else:
                        subscription_end = subscription_start + new_subscription_duration

                    # Используем уровень подписки из платежа
                    subscription_level = payment.subscription_level if payment.subscription_level else 1
                    
                    subscription = Subscription(
                        user_id=payment.user_id,
                        payment_id=payment.id,
                        start_date=subscription_start,
                        end_date=subscription_end,
                        months=payment.months,
                        subscription_level=subscription_level,
                        status=SubscriptionStatus.ACTIVE,
                        auto_renew=False,
                        created_at=current_time,
                        updated_at=current_time
                    )

                    subscription_id = await db.save_subscription(subscription)

                    # Активируем подписку пользователя
                    await db.activate_user_subscription(payment.user_id, subscription_start, subscription_end)

                    # Проверяем, есть ли у пользователя карточка игрока
                    player_stats = await db.get_player_stats(payment.user_id)
                    
                    # Уведомляем пользователя об успешной оплате
                    try:
                        if not player_stats:
                            # Если карточки нет, устанавливаем состояние ожидания фото и отправляем сообщение
                            from aiogram.fsm.storage.base import StorageKey
                            storage_key = StorageKey(
                                chat_id=payment.user_id,
                                user_id=payment.user_id,
                                bot_id=bot_id
                            )
                            await dp.storage.set_state(storage_key, UserRegistration.waiting_for_player_photo)
                            
                            await bot.send_message(
                                payment.user_id,
                                f"✅ Оплата получена!\n\n"
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
                                parse_mode="HTML"
                            )
                            logger.info(f"Пользователь {payment.user_id} переведен в состояние ожидания фото после успешной оплаты")
                        else:
                            # Если карточка уже есть, просто отправляем уведомление
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

async def notification_sender_task():
    """Фоновая задача отправки уведомлений пользователям"""
    logger.info("Запущена задача отправки уведомлений")

    while True:
        try:
            # Получаем неотправленные уведомления
            notifications = await db.get_unsent_notifications(limit=10)

            for notification in notifications:
                try:
                    # Формируем полное сообщение
                    full_message = f"{notification['title']}\n\n{notification['message']}"
                    
                    # Разбиваем длинное сообщение на части, если необходимо
                    message_parts = split_long_message(full_message)
                    
                    # Отправляем все части
                    for part in message_parts:
                        await bot.send_message(
                            chat_id=notification['user_id'],
                            text=part,
                            parse_mode="HTML"
                        )

                    # Отмечаем уведомление как отправленное
                    await db.mark_notification_sent(notification['id'])
                    logger.info(f"Уведомление {notification['id']} отправлено пользователю {notification['user_id']}")

                except Exception as e:
                    logger.error(f"Не удалось отправить уведомление {notification['id']} пользователю {notification['user_id']}: {e}")

            # Проверяем каждые 30 секунд
            await asyncio.sleep(30)

        except Exception as e:
            logger.error(f"[notification_sender_task] Error: {e}")
            await asyncio.sleep(60)  # При ошибке ждем минуту

def get_subscription_level_by_months(months: int) -> int:
    """Определение уровня подписки по количеству месяцев"""
    # Находим соответствующий уровень по месяцам
    for level in SUBSCRIPTION_LEVELS:
        if level['months'] == months:
            return level['level']
    # Если не найден точный уровень, определяем по ближайшему
    if months >= 12:
        return 3  # Мастер
    elif months >= 3:
        return 2  # Продвинутый
    else:
        return 1  # Стартовый

async def experience_reset_task():
    """Фоновая задача для сброса опыта неактивным пользователям"""
    logger.info("Запущена задача сброса опыта неактивным пользователям")
    
    while True:
        try:
            # Получаем всех пользователей с активной подпиской
            subscribed_users = await db.get_all_active_subscribed_users()
            current_time = int(datetime.datetime.now().timestamp())
            
            reset_count = 0
            
            for user_data in subscribed_users:
                user_id = user_data['user_id']
                subscription_level = user_data['subscription_level']
                last_task_date = user_data['last_task_date']
                
                # Получаем разрешенное количество дней неактивности
                allowed_inactivity_days = INACTIVITY_DAYS_BY_LEVEL.get(subscription_level, 2)
                
                # Если у пользователя нет last_task_date, пропускаем (новый пользователь)
                if not last_task_date:
                    continue
                
                # Вычисляем количество дней с последнего задания
                days_since_last_task = (current_time - last_task_date) / (24 * 60 * 60)
                
                # Если прошло больше дней, чем разрешено - сбрасываем опыт
                if days_since_last_task > allowed_inactivity_days:
                    # Получаем текущую статистику пользователя
                    user_stats = await db.get_user_stats(user_id)
                    if user_stats and user_stats.experience > 0:
                        # Сбрасываем опыт
                        await db.reset_user_experience(user_id)
                        reset_count += 1
                        
                        # Отправляем уведомление пользователю
                        try:
                            level_name = SUBSCRIPTION_LEVELS[subscription_level - 1]['name']
                            await bot.send_message(
                                chat_id=user_id,
                                text=f"⚠️ <b>Опыт сброшен</b>\n\n"
                                     f"Вы не выполняли задания более {allowed_inactivity_days} дней.\n"
                                     f"Согласно правилам уровня подписки '{level_name}', ваш опыт был сброшен до 0.\n\n"
                                     f"Начните выполнять задания снова, чтобы заработать новый опыт!",
                                parse_mode="HTML"
                            )
                            logger.info(f"Опыт пользователя {user_id} сброшен. Дней неактивности: {days_since_last_task:.1f}, разрешено: {allowed_inactivity_days}")
                        except Exception as e:
                            logger.error(f"Не удалось отправить уведомление пользователю {user_id} о сбросе опыта: {e}")
            
            if reset_count > 0:
                logger.info(f"Сброшен опыт {reset_count} неактивным пользователям")
            
            # Проверяем каждые 6 часов (21600 секунд)
            await asyncio.sleep(21600)
            
        except Exception as e:
            logger.error(f"[experience_reset_task] Error: {e}")
            await asyncio.sleep(3600)  # При ошибке ждем час

async def subscription_warning_task():
    """Фоновая задача для предупреждения пользователей об окончании подписки"""
    logger.info("Запущена задача предупреждений об окончании подписки")
    
    # Словарь для отслеживания отправленных предупреждений (user_id -> timestamp)
    sent_warnings = {}
    
    while True:
        try:
            # Получаем подписки, которые истекают через 3 дня
            expiring_subscriptions = await db.get_subscriptions_expiring_soon(days_before=3)
            current_time = int(datetime.datetime.now().timestamp())
            
            for sub_data in expiring_subscriptions:
                user_id = sub_data['user_id']
                end_date = sub_data['end_date']
                
                # Вычисляем количество дней до окончания
                days_until_expiry = (end_date - current_time) / (24 * 60 * 60)
                
                # Отправляем предупреждение только если до окончания 2.5-3.5 дня (чтобы не дублировать)
                if 2.5 <= days_until_expiry <= 3.5:
                    # Проверяем, не отправляли ли мы уже предупреждение этому пользователю
                    last_warning_time = sent_warnings.get(user_id, 0)
                    # Отправляем предупреждение не чаще раза в день
                    if current_time - last_warning_time > 24 * 60 * 60:
                        try:
                            end_date_str = datetime.datetime.fromtimestamp(end_date).strftime('%d.%m.%Y')
                            await bot.send_message(
                                chat_id=user_id,
                                text=f"⚠️ <b>Важная информация о подписке</b>\n\n"
                                     f"Ваша подписка истекает через 3 дня ({end_date_str}).\n\n"
                                     f"Чтобы продолжить пользоваться всеми функциями бота, необходимо продлить подписку.\n\n"
                                     f"💎 Используйте команду /subscribe для продления подписки.",
                                parse_mode="HTML"
                            )
                            sent_warnings[user_id] = current_time
                            logger.info(f"Отправлено предупреждение об окончании подписки пользователю {user_id}")
                        except Exception as e:
                            logger.error(f"Не удалось отправить предупреждение пользователю {user_id}: {e}")
            
            # Проверяем каждые 6 часов
            await asyncio.sleep(21600)
            
        except Exception as e:
            logger.error(f"[subscription_warning_task] Error: {e}")
            await asyncio.sleep(3600)  # При ошибке ждем час

async def check_user_subscription(user_id: int) -> tuple[bool, Optional[str]]:
    """
    Проверка активной подписки пользователя
    Возвращает (is_active, error_message)
    """
    user = await db.get_user(user_id)
    if not user:
        return False, "❌ Пользователь не найден в системе."
    
    if not user.subscription_active:
        return False, "❌ <b>Подписка не активна</b>\n\nДля доступа ко всем функциям бота необходимо оформить подписку.\n\nИспользуйте команду /subscribe для оформления подписки."
    
    if not user.subscription_end:
        return False, "❌ <b>Ошибка данных подписки</b>\n\nОбратитесь в поддержку."
    
    current_time = int(datetime.datetime.now().timestamp())
    if user.subscription_end <= current_time:
        return False, "❌ <b>Подписка истекла</b>\n\nДля продолжения использования бота необходимо продлить подписку.\n\nИспользуйте команду /subscribe для продления подписки."
    
    return True, None

async def on_startup():
    """Функция, выполняемая при запуске бота"""
    # База данных уже инициализирована в main()
    # Запускаем фоновую задачу проверки платежей
    asyncio.create_task(payment_polling_task())
    # Запускаем фоновую задачу отправки уведомлений
    asyncio.create_task(notification_sender_task())
    # Запускаем фоновую задачу сброса опыта неактивным пользователям
    asyncio.create_task(experience_reset_task())
    # Запускаем фоновую задачу предупреждений об окончании подписки
    asyncio.create_task(subscription_warning_task())
    logger.info("Бот запущен и готов к работе")
    logger.info("Зарегистрированные handlers: check_payment_callback, notification_sender_task, experience_reset_task, subscription_warning_task")

async def on_shutdown():
    """Функция, выполняемая при остановке бота"""
    logger.info("Бот остановлен")

async def main():
    """Главная функция"""
    # Инициализируем базу данных перед запуском бота
    logger.info("Инициализация базы данных...")
    await db.init_db()
    logger.info("База данных инициализирована")
    
    # Регистрируем роутер
    dp.include_router(router)

    # Регистрируем обработчики запуска и остановки
    dp.startup.register(on_startup)
    dp.shutdown.register(on_shutdown)

    # Запускаем бота
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
