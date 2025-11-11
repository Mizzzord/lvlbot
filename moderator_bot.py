import asyncio
import logging
from datetime import datetime
from typing import Optional, List, Dict

import os
from aiogram import Bot, Dispatcher, F
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import Message, FSInputFile

class ModerationStates(StatesGroup):
    waiting_for_task_id = State()
    waiting_for_experience = State()
    waiting_for_stats = State()
    waiting_for_rejection_reason = State()
    choosing_task_action = State()
from aiogram.types import (
    Message, ReplyKeyboardMarkup, KeyboardButton,
    InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery
)

from moderator_config import (
    MODERATOR_BOT_TOKEN, ADMIN_TELEGRAM_IDS, BLOGGER_TELEGRAM_IDS, MODERATOR_TELEGRAM_IDS,
    DATABASE_PATH, LOG_LEVEL, LOG_FILE
)
from database import Database
from models import Prize, PrizeType, Rank

# Настройки логирования
logging.basicConfig(
    level=getattr(logging, LOG_LEVEL),
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(LOG_FILE),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# Проверка токена
if not MODERATOR_BOT_TOKEN or MODERATOR_BOT_TOKEN == "ВАШ_МОДЕРАТОРСКИЙ_ТОКЕН_ЗДЕСЬ":
    logger.error("Токен модераторского бота не настроен! Установите MODERATOR_BOT_TOKEN в moderator_config.py")
    exit(1)

# Инициализация бота и диспетчера
bot = Bot(token=MODERATOR_BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
dp = Dispatcher()

# Отладка: логируем все callback запросы
db = Database(DATABASE_PATH)

class ModeratorRole:
    ADMIN = "admin"
    BLOGGER = "blogger"
    MODERATOR = "moderator"

async def get_user_role(telegram_id: int) -> Optional[str]:
    """Определение роли пользователя по Telegram ID"""
    # Проверяем админов
    admin_ids = await db.get_admin_telegram_ids()
    if telegram_id in admin_ids:
        return ModeratorRole.ADMIN

    # Проверяем блогеров
    blogger_ids = await db.get_blogger_telegram_ids()
    if telegram_id in blogger_ids:
        return ModeratorRole.BLOGGER

    # Проверяем модераторов
    moderator_ids = await db.get_moderator_telegram_ids()
    if telegram_id in moderator_ids:
        return ModeratorRole.MODERATOR

    return None

async def is_authorized(telegram_id: int) -> bool:
    """Проверка авторизации пользователя"""
    role = await get_user_role(telegram_id)
    return role is not None

class PrizeManagementStates(StatesGroup):
    waiting_for_prize_type = State()
    waiting_for_referral_code = State()
    waiting_for_prize_title = State()
    waiting_for_prize_description = State()
    waiting_for_achievement_type = State()
    waiting_for_achievement_value = State()
    waiting_for_prize_emoji = State()
    confirming_prize = State()

class ModeratorManagementStates(StatesGroup):
    waiting_for_moderator_telegram_id = State()
    confirming_moderator_add = State()
    waiting_for_moderator_id_to_remove = State()

class BloggerManagementStates(StatesGroup):
    waiting_for_blogger_telegram_id = State()
    waiting_for_blogger_referral_code = State()
    confirming_blogger_add = State()
    waiting_for_blogger_id_to_remove = State()

class PrizeManagementStates(StatesGroup):
    waiting_for_prize_type = State()
    waiting_for_referral_code = State()
    waiting_for_prize_title = State()
    waiting_for_prize_description = State()
    waiting_for_achievement_type = State()
    waiting_for_achievement_value = State()
    waiting_for_prize_emoji = State()
    confirming_prize = State()
    waiting_for_prize_id_to_delete = State()

def create_admin_keyboard() -> ReplyKeyboardMarkup:
    """Создание клавиатуры для главного модератора"""
    keyboard = [
        [KeyboardButton(text="🎁 Управление призами")],
        [KeyboardButton(text="👥 Статистика пользователей")],
        [KeyboardButton(text="📊 Общая статистика")],
        [KeyboardButton(text="🔍 Поиск пользователя")],
        [KeyboardButton(text="📋 Активные подписки")],
        [KeyboardButton(text="🛡️ Управление модераторами"), KeyboardButton(text="📣 Управление блогерами")]
    ]
    return ReplyKeyboardMarkup(keyboard=keyboard, resize_keyboard=True)

def create_blogger_keyboard() -> ReplyKeyboardMarkup:
    """Создание клавиатуры для блогера"""
    keyboard = [
        [KeyboardButton(text="🎁 Мои призы")],
        [KeyboardButton(text="➕ Добавить приз")],
        [KeyboardButton(text="📊 Статистика подписчиков")],
        [KeyboardButton(text="👤 Найти подписчика")]
    ]
    return ReplyKeyboardMarkup(keyboard=keyboard, resize_keyboard=True)

def create_moderator_keyboard() -> ReplyKeyboardMarkup:
    """Создание клавиатуры для обычного модератора"""
    keyboard = [
        [KeyboardButton(text="📋 Проверить задания")],
        [KeyboardButton(text="✅ Одобрить задание")],
        [KeyboardButton(text="❌ Отклонить задание")],
        [KeyboardButton(text="📊 Статистика модерации")]
    ]
    return ReplyKeyboardMarkup(keyboard=keyboard, resize_keyboard=True)

@dp.message(Command("start"))
async def cmd_start(message: Message):
    """Обработчик команды /start"""
    user_id = message.from_user.id
    username = message.from_user.username or "Без username"
    logger.info(f"Пользователь {user_id} ({username}) запустил бота")

    if not await is_authorized(user_id):
        await message.answer(
            "❌ <b>Доступ запрещен</b>\n\n"
            "У вас нет прав для использования этого бота.\n"
            "Обратитесь к администратору для получения доступа.",
            parse_mode="HTML"
        )
        logger.warning(f"Попытка несанкционированного доступа от пользователя {username} (ID: {user_id})")
        return

    role = await get_user_role(user_id)

    if role == ModeratorRole.ADMIN:
        await message.answer(
            "🎩 <b>Добро пожаловать, главный модератор!</b>\n\n"
            "Вы имеете полный доступ к системе управления.",
            parse_mode="HTML",
            reply_markup=create_admin_keyboard()
        )
    elif role == ModeratorRole.BLOGGER:
        await message.answer(
            "📣 <b>Добро пожаловать, блогер!</b>\n\n"
            "Управляйте своими призами и подписчиками.",
            parse_mode="HTML",
            reply_markup=create_blogger_keyboard()
        )
    elif role == ModeratorRole.MODERATOR:
        await message.answer(
            "🛡️ <b>Добро пожаловать, модератор!</b>\n\n"
            "Проверяйте задания пользователей и выдавайте награды.",
            parse_mode="HTML",
            reply_markup=create_moderator_keyboard()
        )

    logger.info(f"Авторизован {role}: {username} (ID: {user_id})")

# Обработчики для обычных модераторов

@dp.message(lambda message: message.text == "📋 Проверить задания")
async def handle_moderator_check_tasks(message: Message):
    """Просмотр заданий на модерацию"""
    user_id = message.from_user.id
    logger.info(f"Пользователь {user_id} нажал 'Проверить задания'")

    if await get_user_role(user_id) != ModeratorRole.MODERATOR:
        await message.answer("❌ У вас нет доступа к этой функции.")
        logger.warning(f"Пользователь {user_id} попытался получить доступ к модерации без прав")
        return

    # Получаем задания на модерацию
    pending_tasks = await db.get_pending_tasks_for_moderation(limit=10)

    if not pending_tasks:
        await message.answer(
            "📋 <b>Задания на модерацию</b>\n\n"
            "✅ Все задания проверены!\n"
            "Новых заданий на модерацию нет.",
            parse_mode="HTML",
            reply_markup=create_moderator_keyboard()
        )
        return

    text = "📋 <b>Задания на модерацию</b>\n\n"
    keyboard = InlineKeyboardMarkup(inline_keyboard=[])

    for task_id, user_id, task_desc, media_path, user_name, nickname in pending_tasks[:5]:
        player_name = nickname or user_name
        short_desc = task_desc[:50] + "..." if len(task_desc) > 50 else task_desc
        text += f"🎯 <b>ID {task_id}</b>: {player_name}\n"
        text += f"   └ {short_desc}\n\n"

        keyboard.inline_keyboard.append([
            InlineKeyboardButton(
                text=f"📝 Проверить #{task_id}",
                callback_data=f"check_task_{task_id}"
            )
        ])
        logger.info(f"Добавлена кнопка check_task_{task_id} для модератора {user_id}")

    keyboard.inline_keyboard.append([
        InlineKeyboardButton(text="⬅️ В меню", callback_data="back_to_moderator_menu")
    ])

    logger.info(f"Отправлено сообщение с клавиатурой модератору {user_id}")
    await message.answer(text, reply_markup=keyboard)

@dp.callback_query(lambda c: c.data.startswith("check_task_"))
async def handle_check_task(callback: CallbackQuery, state: FSMContext):
    """Просмотр деталей задания"""
    logger.info(f"Вызван handle_check_task для task_id: {callback.data}")
    await callback.answer()
    task_id = int(callback.data.replace("check_task_", ""))

    task_details = await db.get_task_details(task_id)
    if not task_details:
        await callback.message.edit_text("❌ Задание не найдено.")
        return

    user_name = task_details['name']
    nickname = task_details['nickname'] or user_name
    task_desc = task_details['task_description']

    text = f"📝 <b>Задание #{task_id}</b>\n\n"
    text += f"👤 <b>Игрок:</b> {nickname} ({user_name})\n"
    text += f"🎯 <b>Задание:</b>\n{task_desc}\n\n"

    # Проверяем, есть ли медиафайл
    media_path = task_details.get('submitted_media_path')
    if media_path and os.path.exists(media_path):
        text += "📎 <b>Прикреплен файл</b>\n"

        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="✅ Одобрить", callback_data=f"approve_task_{task_id}")],
            [InlineKeyboardButton(text="❌ Отклонить", callback_data=f"reject_task_{task_id}")],
            [InlineKeyboardButton(text="⬅️ Назад к списку", callback_data="back_to_task_list")]
        ])

        # Отправляем медиафайл и текст
        try:
            if media_path.endswith(('.jpg', '.jpeg', '.png')):
                photo = FSInputFile(media_path)
                await callback.message.answer_photo(photo, caption=text, reply_markup=keyboard)
            elif media_path.endswith(('.mp4', '.avi', '.mov')):
                video = FSInputFile(media_path)
                await callback.message.answer_video(video, caption=text, reply_markup=keyboard)
            else:
                await callback.message.edit_text(text + "\n❌ Неподдерживаемый тип файла", reply_markup=keyboard)
        except Exception as e:
            logger.error(f"Ошибка отправки медиафайла: {e}")
            await callback.message.edit_text(text + "\n❌ Ошибка загрузки файла", reply_markup=keyboard)
    else:
        text += "📎 <b>Файл не прикреплен</b>\n"

        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="✅ Одобрить", callback_data=f"approve_task_{task_id}")],
            [InlineKeyboardButton(text="❌ Отклонить", callback_data=f"reject_task_{task_id}")],
            [InlineKeyboardButton(text="⬅️ Назад к списку", callback_data="back_to_task_list")]
        ])

        await callback.message.edit_text(text, reply_markup=keyboard)

@dp.callback_query(lambda c: c.data.startswith("approve_task_"))
async def handle_approve_task(callback: CallbackQuery, state: FSMContext):
    """Одобрение задания"""
    logger.info(f"Вызван handle_approve_task для task_id: {callback.data}")
    await callback.answer()
    task_id = int(callback.data.replace("approve_task_", ""))
    moderator_id = callback.from_user.id

    # Сохраняем ID задания в состоянии
    await state.update_data(task_id=task_id, moderator_id=moderator_id)

    text = f"✅ <b>Одобрение задания #{task_id}</b>\n\n"
    text += "Укажите количество опыта для начисления (1-50):"

    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="10 опыта", callback_data="exp_10")],
        [InlineKeyboardButton(text="20 опыта", callback_data="exp_20")],
        [InlineKeyboardButton(text="30 опыта", callback_data="exp_30")],
        [InlineKeyboardButton(text="❌ Отмена", callback_data="cancel_approval")]
    ])

    try:
        await callback.message.edit_text(text, reply_markup=keyboard)
    except Exception as e:
        logger.error(f"Ошибка редактирования сообщения: {e}")
        await callback.message.answer(text, reply_markup=keyboard)

@dp.callback_query(lambda c: c.data.startswith("exp_"))
async def handle_experience_selection(callback: CallbackQuery, state: FSMContext):
    """Выбор количества опыта"""
    await callback.answer()
    experience = int(callback.data.replace("exp_", ""))

    # Сохраняем опыт в состоянии
    data = await state.get_data()
    data['experience'] = experience
    await state.update_data(data)

    text = f"💪 <b>Начисление характеристик</b>\n\n"
    text += f"Опыт: {experience}\n\n"
    text += "Выберите, какие характеристики начислить:\n"
    text += "• 💪 Сила\n"
    text += "• 🤸 Ловкость\n"
    text += "• 🏃 Выносливость\n"
    text += "• 🧠 Интеллект\n"
    text += "• ✨ Харизма\n\n"
    text += "Отправьте сообщение в формате:\n"
    text += "<code>сила:2 ловкость:1 интеллект:3</code>"

    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Без бонусов", callback_data="no_stats_bonus")],
        [InlineKeyboardButton(text="❌ Отмена", callback_data="cancel_approval")]
    ])

    await callback.message.edit_text(text, reply_markup=keyboard)
    await state.set_state(ModerationStates.waiting_for_stats)

@dp.callback_query(lambda c: c.data == "no_stats_bonus")
async def handle_no_stats_bonus(callback: CallbackQuery, state: FSMContext):
    """Одобрение без бонусов к характеристикам"""
    await callback.answer()

    data = await state.get_data()
    task_id = data.get('task_id')
    moderator_id = data.get('moderator_id')
    experience = data.get('experience', 10)

    if not task_id:
        await callback.message.edit_text("❌ Ошибка: ID задания не найден.")
        await state.clear()
        return

    # Одобряем задание без бонусов
    success = await db.approve_task(task_id, moderator_id, experience_reward=experience)

    if success:
        await callback.message.edit_text(
            f"✅ <b>Задание #{task_id} одобрено!</b>\n\n"
            f"🎉 Начислено: {experience} опыта\n"
            f"💪 Бонусы к характеристикам: нет",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="📋 К следующим заданиям", callback_data="back_to_task_list")],
                [InlineKeyboardButton(text="⬅️ В меню", callback_data="back_to_moderator_menu")]
            ])
        )
    else:
        await callback.message.edit_text(
            "❌ Ошибка при одобрении задания.",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="⬅️ Назад", callback_data="back_to_task_list")]
            ])
        )

    await state.clear()

@dp.message(ModerationStates.waiting_for_stats)
async def handle_stats_input(message: Message, state: FSMContext):
    """Обработка ввода характеристик"""
    stats_text = message.text.lower().strip()

    # Парсим характеристики
    stat_rewards = {
        'strength': 0,
        'agility': 0,
        'endurance': 0,
        'intelligence': 0,
        'charisma': 0
    }

    # Разбираем строку вида "сила:2 ловкость:1 интеллект:3"
    stat_names = {
        'сила': 'strength',
        'ловкость': 'agility',
        'выносливость': 'endurance',
        'интеллект': 'intelligence',
        'харизма': 'charisma'
    }

    try:
        parts = stats_text.split()
        for part in parts:
            if ':' in part:
                name, value = part.split(':', 1)
                name = name.strip()
                value = int(value.strip())

                if name in stat_names and 0 <= value <= 10:
                    stat_rewards[stat_names[name]] = value
                else:
                    await message.answer("❌ Неверный формат. Используйте: сила:2 ловкость:1")
                    return

        # Получаем данные из состояния
        data = await state.get_data()
        task_id = data.get('task_id')
        moderator_id = data.get('moderator_id')
        experience = data.get('experience', 10)

        if not task_id:
            await message.answer("❌ Ошибка: ID задания не найден.")
            await state.clear()
            return

        # Одобряем задание с бонусами
        success = await db.approve_task(task_id, moderator_id, experience_reward=experience, stat_rewards=stat_rewards)

        if success:
            bonus_text = ""
            for stat_name, value in stat_rewards.items():
                if value > 0:
                    stat_display_names = {
                        'strength': '💪 Сила',
                        'agility': '🤸 Ловкость',
                        'endurance': '🏃 Выносливость',
                        'intelligence': '🧠 Интеллект',
                        'charisma': '✨ Харизма'
                    }
                    bonus_text += f"{stat_display_names[stat_name]}: +{value}\n"

            if not bonus_text:
                bonus_text = "нет"

            await message.answer(
                f"✅ <b>Задание #{task_id} одобрено!</b>\n\n"
                f"🎉 Начислено: {experience} опыта\n"
                f"💪 Бонусы к характеристикам:\n{bonus_text}",
                reply_markup=create_moderator_keyboard()
            )
        else:
            await message.answer(
                "❌ Ошибка при одобрении задания.",
                reply_markup=create_moderator_keyboard()
            )

    except ValueError:
        await message.answer("❌ Неверный формат числа. Используйте: сила:2 ловкость:1")
    except Exception as e:
        logger.error(f"Ошибка обработки характеристик: {e}")
        await message.answer("❌ Произошла ошибка. Попробуйте снова.")

    await state.clear()

@dp.callback_query(lambda c: c.data.startswith("reject_task_"))
async def handle_reject_task(callback: CallbackQuery, state: FSMContext):
    """Отклонение задания"""
    logger.info(f"Вызван handle_reject_task для task_id: {callback.data}")
    await callback.answer()
    task_id = int(callback.data.replace("reject_task_", ""))

    # Сохраняем ID задания в состоянии
    await state.update_data(task_id=task_id, moderator_id=callback.from_user.id)

    text = f"❌ <b>Отклонение задания #{task_id}</b>\n\n"
    text += "Укажите причину отклонения (или отправьте 'Без причины'):"
    text += "\n\nПримеры причин:\n"
    text += "• Задание выполнено не полностью\n"
    text += "• Качество фото/видео низкое\n"
    text += "• Нарушение правил"

    try:
        await callback.message.edit_text(text, reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="Без причины", callback_data="reject_no_reason")],
            [InlineKeyboardButton(text="❌ Отмена", callback_data="cancel_rejection")]
        ]))
    except Exception as e:
        logger.error(f"Ошибка редактирования сообщения: {e}")
        await callback.message.answer(text, reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="Без причины", callback_data="reject_no_reason")],
            [InlineKeyboardButton(text="❌ Отмена", callback_data="cancel_rejection")]
        ]))

    await state.set_state(ModerationStates.waiting_for_rejection_reason)

@dp.callback_query(lambda c: c.data == "reject_no_reason")
async def handle_reject_no_reason(callback: CallbackQuery, state: FSMContext):
    """Отклонение без указания причины"""
    await callback.answer()

    data = await state.get_data()
    task_id = data.get('task_id')
    moderator_id = data.get('moderator_id')

    if not task_id:
        await callback.message.edit_text("❌ Ошибка: ID задания не найден.")
        await state.clear()
        return

    success = await db.reject_task(task_id, moderator_id, "Без указания причины")

    if success:
        await callback.message.edit_text(
            f"❌ <b>Задание #{task_id} отклонено</b>\n\n"
            f"Причина: Без указания причины",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="📋 К следующим заданиям", callback_data="back_to_task_list")],
                [InlineKeyboardButton(text="⬅️ В меню", callback_data="back_to_moderator_menu")]
            ])
        )
    else:
        await callback.message.edit_text(
            "❌ Ошибка при отклонении задания.",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="⬅️ Назад", callback_data="back_to_task_list")]
            ])
        )

    await state.clear()

@dp.message(ModerationStates.waiting_for_rejection_reason)
async def handle_rejection_reason(message: Message, state: FSMContext):
    """Обработка причины отклонения"""
    reason = message.text.strip()

    data = await state.get_data()
    task_id = data.get('task_id')
    moderator_id = data.get('moderator_id')

    if not task_id:
        await message.answer("❌ Ошибка: ID задания не найден.")
        await state.clear()
        return

    success = await db.reject_task(task_id, moderator_id, reason)

    if success:
        await message.answer(
            f"❌ <b>Задание #{task_id} отклонено</b>\n\n"
            f"Причина: {reason}",
            reply_markup=create_moderator_keyboard()
        )
    else:
        await message.answer(
            "❌ Ошибка при отклонении задания.",
            reply_markup=create_moderator_keyboard()
        )

    await state.clear()

@dp.callback_query(lambda c: c.data == "back_to_task_list")
async def handle_back_to_task_list(callback: CallbackQuery):
    """Возврат к списку заданий"""
    await callback.answer()

    # Получаем задания на модерацию
    pending_tasks = await db.get_pending_tasks_for_moderation(limit=10)

    if not pending_tasks:
        await callback.message.edit_text(
            "📋 <b>Задания на модерацию</b>\n\n"
            "✅ Все задания проверены!\n"
            "Новых заданий на модерацию нет.",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="⬅️ В меню", callback_data="back_to_moderator_menu")]
            ])
        )
        return

    text = "📋 <b>Задания на модерацию</b>\n\n"
    keyboard = InlineKeyboardMarkup(inline_keyboard=[])

    for task_id, user_id, task_desc, media_path, user_name, nickname in pending_tasks[:5]:
        player_name = nickname or user_name
        short_desc = task_desc[:50] + "..." if len(task_desc) > 50 else task_desc
        text += f"🎯 <b>ID {task_id}</b>: {player_name}\n"
        text += f"   └ {short_desc}\n\n"

        keyboard.inline_keyboard.append([
            InlineKeyboardButton(
                text=f"📝 Проверить #{task_id}",
                callback_data=f"check_task_{task_id}"
            )
        ])

    keyboard.inline_keyboard.append([
        InlineKeyboardButton(text="⬅️ В меню", callback_data="back_to_moderator_menu")
    ])

    await callback.message.edit_text(text, reply_markup=keyboard)

@dp.message(F.text == "📊 Статистика модерации")
async def handle_moderator_stats(message: Message):
    """Статистика модератора"""
    user_id = message.from_user.id

    if await get_user_role(user_id) != ModeratorRole.MODERATOR:
        await message.answer("❌ У вас нет доступа к этой функции.")
        return

    # Получаем статистику модератора
    stats = await db.get_moderator_stats(user_id)

    # Получаем количество заданий на проверку
    pending_count = len(await db.get_pending_tasks_for_moderation(limit=1000))

    text = "📊 <b>Статистика модерации</b>\n\n"

    # Статистика за сегодня
    text += "📅 <b>Сегодня:</b>\n"
    text += f"✅ Одобрено: {stats['today_moderated']}\n"
    text += f"❌ Отклонено: {stats['today_rejected']}\n"
    text += f"📊 Всего за день: {stats['today_tasks']}\n\n"

    # Статистика за все время
    text += "🏆 <b>За все время:</b>\n"
    text += f"✅ Одобрено: {stats['total_moderated']}\n"
    text += f"❌ Отклонено: {stats['total_rejected']}\n"
    text += f"📊 Всего заданий: {stats['total_tasks']}\n\n"

    # Общая статистика
    text += "📋 <b>Текущая очередь:</b>\n"
    text += f"⏳ Заданий на проверку: {pending_count}"

    await message.answer(text, reply_markup=create_moderator_keyboard())

# Обработчики для управления модераторами (только для админов)

@dp.message(F.text == "🛡️ Управление модераторами")
async def handle_admin_moderators(message: Message):
    """Управление модераторами для главного модератора"""
    user_id = message.from_user.id

    if await get_user_role(user_id) != ModeratorRole.ADMIN:
        await message.answer("❌ У вас нет доступа к этой функции.")
        return

    # Получаем список модераторов
    moderators = await db.get_moderators(active_only=True)

    text = "🛡️ <b>Управление модераторами</b>\n\n"

    if moderators:
        text += f"👥 <b>Активных модераторов:</b> {len(moderators)}\n\n"
        for mod in moderators:
            username = mod.get('username', 'N/A')
            full_name = mod.get('full_name', 'N/A')
            text += f"🆔 <code>{mod['telegram_id']}</code>\n"
            text += f"👤 {full_name} (@{username})\n"
            text += f"📅 Добавлен: {datetime.fromtimestamp(mod['created_at']).strftime('%d.%m.%Y')}\n\n"
    else:
        text += "👥 <b>Активных модераторов:</b> 0\n\n"
        text += "Пока нет назначенных модераторов."

    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="➕ Добавить модератора", callback_data="add_moderator")],
        [InlineKeyboardButton(text="🗑️ Удалить модератора", callback_data="remove_moderator")],
        [InlineKeyboardButton(text="📋 Просмотреть всех", callback_data="view_all_moderators")],
        [InlineKeyboardButton(text="⬅️ Назад", callback_data="back_to_admin_menu")]
    ])

    await message.answer(text, reply_markup=keyboard)

@dp.message(F.text == "📣 Управление блогерами")
async def handle_admin_bloggers(message: Message):
    """Управление блогерами для главного модератора"""
    user_id = message.from_user.id

    if await get_user_role(user_id) != ModeratorRole.ADMIN:
        await message.answer("❌ У вас нет доступа к этой функции.")
        return

    # Получаем список блогеров
    bloggers = await db.get_bloggers(active_only=True)

    text = "📣 <b>Управление блогерами</b>\n\n"

    if bloggers:
        text += f"👥 <b>Активных блогеров:</b> {len(bloggers)}\n\n"
        for blogger in bloggers:
            username = blogger.get('username', 'N/A')
            full_name = blogger.get('full_name', 'N/A')
            text += f"🆔 <code>{blogger['telegram_id']}</code>\n"
            text += f"🔗 Реферальный код: <code>{blogger['referral_code']}</code>\n"
            text += f"👤 {full_name} (@{username})\n"
            text += f"📅 Добавлен: {datetime.fromtimestamp(blogger['created_at']).strftime('%d.%m.%Y')}\n\n"
    else:
        text += "👥 <b>Активных блогеров:</b> 0\n\n"
        text += "Пока нет зарегистрированных блогеров."

    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="➕ Добавить блогера", callback_data="add_blogger")],
        [InlineKeyboardButton(text="🗑️ Удалить блогера", callback_data="remove_blogger")],
        [InlineKeyboardButton(text="📋 Просмотреть всех", callback_data="view_all_bloggers")],
        [InlineKeyboardButton(text="⬅️ Назад", callback_data="back_to_admin_menu")]
    ])

    await message.answer(text, reply_markup=keyboard)

# Обработчики для главного модератора

@dp.message(F.text == "🎁 Управление призами")
async def handle_admin_prizes(message: Message):
    """Управление призами для главного модератора"""
    user_id = message.from_user.id

    if await get_user_role(user_id) != ModeratorRole.ADMIN:
        await message.answer("❌ У вас нет доступа к этой функции.")
        return

    # Получаем все призы
    admin_prizes = await db.get_prizes(prize_type=PrizeType.ADMIN, is_active=True)
    blogger_prizes = await db.get_prizes(prize_type=PrizeType.BLOGGER, is_active=True)

    text = "🎁 <b>Управление призами</b>\n\n"

    text += f"👑 <b>Призы главного модератора:</b> {len(admin_prizes)}\n"
    for prize in admin_prizes[:5]:  # Показываем первые 5
        text += f"• {prize.emoji} {prize.title} (ID: {prize.id})\n"
    if len(admin_prizes) > 5:
        text += f"... и еще {len(admin_prizes) - 5} призов\n"

    text += f"\n📣 <b>Призы блогеров:</b> {len(blogger_prizes)}\n"
    for prize in blogger_prizes[:5]:  # Показываем первые 5
        text += f"• {prize.emoji} {prize.title} (Блогер: {prize.referral_code}, ID: {prize.id})\n"
    if len(blogger_prizes) > 5:
        text += f"... и еще {len(blogger_prizes) - 5} призов\n"

    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="➕ Создать новый приз", callback_data="create_prize_admin")],
        [InlineKeyboardButton(text="📝 Редактировать приз", callback_data="edit_prize")],
        [InlineKeyboardButton(text="🗑️ Удалить приз", callback_data="delete_prize")],
        [InlineKeyboardButton(text="👁️ Просмотреть все", callback_data="view_all_prizes")],
        [InlineKeyboardButton(text="⬅️ Назад", callback_data="back_to_admin_menu")]
    ])

    await message.answer(text, reply_markup=keyboard)

@dp.message(F.text == "👥 Статистика пользователей")
async def handle_admin_users(message: Message):
    """Статистика пользователей для главного модератора"""
    user_id = message.from_user.id

    if await get_user_role(user_id) != ModeratorRole.ADMIN:
        await message.answer("❌ У вас нет доступа к этой функции.")
        return

    # Получаем общую статистику
    total_users = await db.get_total_users_count()
    active_users = await db.get_active_users_count()
    total_tasks = await db.get_total_completed_tasks()

    text = "👥 <b>Статистика пользователей</b>\n\n"
    text += f"📊 <b>Всего пользователей:</b> {total_users}\n"
    text += f"✅ <b>Активных подписок:</b> {active_users}\n"
    text += f"🎯 <b>Выполнено заданий:</b> {total_tasks}\n"

    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📈 Детальная статистика", callback_data="detailed_stats")],
        [InlineKeyboardButton(text="🏆 Топ пользователей", callback_data="top_users")],
        [InlineKeyboardButton(text="⬅️ Назад", callback_data="back_to_admin_menu")]
    ])

    await message.answer(text, reply_markup=keyboard)

@dp.message(F.text == "📊 Общая статистика")
async def handle_admin_general_stats(message: Message):
    """Общая статистика для главного модератора"""
    user_id = message.from_user.id

    if await get_user_role(user_id) != ModeratorRole.ADMIN:
        await message.answer("❌ У вас нет доступа к этой функции.")
        return

    # Получаем статистику по городам
    city_stats = await db.get_users_by_city_stats()
    rank_stats = await db.get_users_by_rank_stats()

    text = "📊 <b>Общая статистика</b>\n\n"

    text += "🏙️ <b>Распределение по городам:</b>\n"
    for city, count in city_stats[:10]:  # Топ 10 городов
        text += f"• {city}: {count} пользователей\n"

    text += "\n🏅 <b>Распределение по рангам:</b>\n"
    for rank, count in rank_stats:
        text += f"• Ранг {rank}: {count} пользователей\n"

    await message.answer(text, reply_markup=InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="⬅️ Назад", callback_data="back_to_admin_menu")]
    ]))

# Обработчики для блогеров

@dp.message(F.text == "🎁 Мои призы")
async def handle_blogger_prizes(message: Message):
    """Призы блогера"""
    user_id = message.from_user.id
    role = await get_user_role(user_id)

    if role != ModeratorRole.BLOGGER:
        await message.answer("❌ У вас нет доступа к этой функции.")
        return

    # Находим реферальный код блогера (предполагаем, что он совпадает с каким-то полем)
    # Для простоты будем использовать user_id как реферальный код, но в реальности
    # нужно добавить поле referral_code для блогеров в базу данных

    # Пока что покажем все призы блогеров
    blogger_prizes = await db.get_prizes(prize_type=PrizeType.BLOGGER, is_active=True)

    text = "🎁 <b>Ваши призы</b>\n\n"

    if blogger_prizes:
        for prize in blogger_prizes:
            text += f"{prize.emoji} <b>{prize.title}</b>\n"
            if prize.description:
                text += f"   └ {prize.description}\n"
            text += f"   └ Достижение: {get_achievement_description(prize.achievement_type, prize.achievement_value)}\n"
            text += f"   └ ID: {prize.id}\n\n"
    else:
        text += "У вас пока нет созданных призов.\nИспользуйте кнопку '➕ Добавить приз' для создания."

    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="➕ Добавить приз", callback_data="add_blogger_prize")],
        [InlineKeyboardButton(text="✏️ Редактировать", callback_data="edit_blogger_prize")],
        [InlineKeyboardButton(text="⬅️ Назад", callback_data="back_to_blogger_menu")]
    ])

    await message.answer(text, reply_markup=keyboard)

@dp.message(F.text == "📊 Статистика подписчиков")
async def handle_blogger_stats(message: Message):
    """Статистика подписчиков блогера"""
    user_id = message.from_user.id
    role = await get_user_role(user_id)

    if role != ModeratorRole.BLOGGER:
        await message.answer("❌ У вас нет доступа к этой функции.")
        return

    # Получаем реферальный код блогера (нужно будет добавить логику определения)
    referral_code = str(user_id)  # Временное решение

    # Получаем статистику подписчиков
    subscribers = await db.get_users_by_referral_code_stats(referral_code)
    total_subscribers = len(subscribers)

    text = "📊 <b>Статистика ваших подписчиков</b>\n\n"
    text += f"👥 <b>Всего подписчиков:</b> {total_subscribers}\n\n"

    if subscribers:
        # Показываем топ подписчиков
        text += "🏆 <b>Топ подписчиков:</b>\n"
        for i, (name, level, exp, rank) in enumerate(subscribers[:10], 1):
            text += f"{i}. {name} - Ур.{level} ({rank})\n"

    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📈 Детальная статистика", callback_data="blogger_detailed_stats")],
        [InlineKeyboardButton(text="⬅️ Назад", callback_data="back_to_blogger_menu")]
    ])

    await message.answer(text, reply_markup=keyboard)

# Вспомогательные функции

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

# Callback handlers

@dp.callback_query(lambda c: c.data == "back_to_admin_menu")
async def handle_back_to_admin_menu(callback: CallbackQuery):
    """Возврат в меню главного модератора"""
    await callback.answer()
    await callback.message.answer(
        "🎩 <b>Меню главного модератора</b>",
        reply_markup=create_admin_keyboard()
    )

@dp.callback_query(lambda c: c.data == "back_to_blogger_menu")
async def handle_back_to_blogger_menu(callback: CallbackQuery):
    """Возврат в меню блогера"""
    await callback.answer()
    await callback.message.answer(
        "📣 <b>Меню блогера</b>",
        reply_markup=create_blogger_keyboard()
    )

@dp.callback_query(lambda c: c.data == "back_to_moderator_menu")
async def handle_back_to_moderator_menu(callback: CallbackQuery):
    """Возврат в меню модератора"""
    await callback.answer()
    await callback.message.answer(
        "🛡️ <b>Меню модератора</b>",
        reply_markup=create_moderator_keyboard()
    )

# Заглушки для будущих функций
@dp.callback_query(lambda c: c.data.startswith("admin_"))
async def handle_admin_callbacks(callback: CallbackQuery):
    """Обработка callback'ов главного модератора"""
    await callback.answer()
    action = callback.data.replace("admin_", "")

    if action == "prizes":
        await handle_admin_prizes(callback.message)
    elif action == "users":
        await handle_admin_users(callback.message)
    elif action == "stats":
        await handle_admin_general_stats(callback.message)
    else:
        await callback.message.answer("Функция в разработке")

@dp.callback_query(lambda c: c.data.startswith("blogger_"))
async def handle_blogger_callbacks(callback: CallbackQuery):
    """Обработка callback'ов блогера"""
    await callback.answer()
    action = callback.data.replace("blogger_", "")

    if action == "prizes":
        await handle_blogger_prizes(callback.message)
    elif action == "stats":
        await handle_blogger_stats(callback.message)
    else:
        await callback.message.answer("Функция в разработке")

# Обработчики для управления призами
@dp.callback_query(lambda c: c.data == "create_prize_admin")
async def handle_create_prize_admin(callback: CallbackQuery, state: FSMContext):
    """Создание нового приза для главного модератора"""
    await callback.answer()

    text = "🎁 <b>Создание нового приза</b>\n\n"
    text += "Выберите тип приза:"

    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="👑 Приз для всех пользователей", callback_data="prize_type_admin")],
        [InlineKeyboardButton(text="📣 Приз для блогеров", callback_data="prize_type_blogger")],
        [InlineKeyboardButton(text="❌ Отмена", callback_data="cancel_prize_creation")]
    ])

    await callback.message.edit_text(text, reply_markup=keyboard)

@dp.callback_query(lambda c: c.data.startswith("prize_type_"))
async def handle_prize_type_selection(callback: CallbackQuery, state: FSMContext):
    """Выбор типа приза"""
    await callback.answer()

    prize_type = callback.data.replace("prize_type_", "")
    await state.update_data(prize_type=prize_type)

    text = "🎁 <b>Создание приза</b>\n\n"
    text += f"Тип: {'Главный модератор' if prize_type == 'admin' else 'Блогер'}\n\n"
    text += "Введите название приза:"

    await callback.message.edit_text(text, reply_markup=InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="❌ Отмена", callback_data="cancel_prize_creation")]
    ]))

    await state.set_state(PrizeManagementStates.waiting_for_prize_title)

@dp.message(PrizeManagementStates.waiting_for_prize_title)
async def handle_prize_title(message: Message, state: FSMContext):
    """Обработка названия приза"""
    title = message.text.strip()
    if len(title) < 3:
        await message.answer("❌ Название приза должно содержать минимум 3 символа.")
        return

    await state.update_data(prize_title=title)

    text = "🎁 <b>Создание приза</b>\n\n"
    text += f"Название: {title}\n\n"
    text += "Введите описание приза (опционально, можно пропустить):"

    await message.answer(text, reply_markup=InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="⏭️ Пропустить", callback_data="skip_description")],
        [InlineKeyboardButton(text="❌ Отмена", callback_data="cancel_prize_creation")]
    ]))

    await state.set_state(PrizeManagementStates.waiting_for_prize_description)

@dp.message(PrizeManagementStates.waiting_for_prize_description)
async def handle_prize_description(message: Message, state: FSMContext):
    """Обработка описания приза"""
    description = message.text.strip()
    await state.update_data(prize_description=description)

    text = "🎁 <b>Создание приза</b>\n\n"
    text += f"Описание: {description}\n\n"
    text += "Выберите тип достижения:"

    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔥 Стрик (дни подряд)", callback_data="achievement_streak")],
        [InlineKeyboardButton(text="🏅 Ранг", callback_data="achievement_rank")],
        [InlineKeyboardButton(text="📊 Уровень", callback_data="achievement_level")],
        [InlineKeyboardButton(text="✅ Задания", callback_data="achievement_tasks")],
        [InlineKeyboardButton(text="⭐ Опыт", callback_data="achievement_experience")],
        [InlineKeyboardButton(text="❌ Отмена", callback_data="cancel_prize_creation")]
    ])

    await message.answer(text, reply_markup=keyboard)
    await state.set_state(PrizeManagementStates.waiting_for_achievement_type)

@dp.callback_query(lambda c: c.data == "skip_description")
async def handle_skip_description(callback: CallbackQuery, state: FSMContext):
    """Пропуск описания приза"""
    await callback.answer()
    await state.update_data(prize_description="")

    text = "🎁 <b>Создание приза</b>\n\n"
    text += "Описание: (без описания)\n\n"
    text += "Выберите тип достижения:"

    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔥 Стрик (дни подряд)", callback_data="achievement_streak")],
        [InlineKeyboardButton(text="🏅 Ранг", callback_data="achievement_rank")],
        [InlineKeyboardButton(text="📊 Уровень", callback_data="achievement_level")],
        [InlineKeyboardButton(text="✅ Задания", callback_data="achievement_tasks")],
        [InlineKeyboardButton(text="⭐ Опыт", callback_data="achievement_experience")],
        [InlineKeyboardButton(text="❌ Отмена", callback_data="cancel_prize_creation")]
    ])

    await callback.message.edit_text(text, reply_markup=keyboard)
    await state.set_state(PrizeManagementStates.waiting_for_achievement_type)

@dp.callback_query(lambda c: c.data.startswith("achievement_"))
async def handle_achievement_type(callback: CallbackQuery, state: FSMContext):
    """Выбор типа достижения"""
    await callback.answer()

    achievement_type = callback.data.replace("achievement_", "")
    await state.update_data(achievement_type=achievement_type)

    # Показываем примеры значений для разных типов
    examples = {
        "streak": "Примеры: 7, 14, 30 (дни подряд)",
        "rank": "Примеры: 3 (Ранг C), 4 (Ранг B), 5 (Ранг A), 6 (Ранг S)",
        "level": "Примеры: 5, 10, 25 (уровень игрока)",
        "tasks": "Примеры: 10, 50, 100 (выполненных заданий)",
        "experience": "Примеры: 100, 500, 1000 (единиц опыта)"
    }

    text = "🎁 <b>Создание приза</b>\n\n"
    text += f"Тип достижения: {achievement_type.title()}\n"
    text += f"{examples.get(achievement_type, '')}\n\n"
    text += "Введите значение достижения:"

    await callback.message.edit_text(text, reply_markup=InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="❌ Отмена", callback_data="cancel_prize_creation")]
    ]))

    await state.set_state(PrizeManagementStates.waiting_for_achievement_value)

@dp.message(PrizeManagementStates.waiting_for_achievement_value)
async def handle_achievement_value(message: Message, state: FSMContext):
    """Обработка значения достижения"""
    try:
        value = int(message.text.strip())
        if value <= 0:
            await message.answer("❌ Значение должно быть положительным числом.")
            return
    except ValueError:
        await message.answer("❌ Введите корректное число.")
        return

    await state.update_data(achievement_value=value)

    text = "🎁 <b>Создание приза</b>\n\n"
    text += f"Значение: {value}\n\n"
    text += "Введите эмодзи для приза (или нажмите '🎁 По умолчанию'):"

    await message.answer(text, reply_markup=InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🎁 По умолчанию", callback_data="default_emoji")],
        [InlineKeyboardButton(text="❌ Отмена", callback_data="cancel_prize_creation")]
    ]))

    await state.set_state(PrizeManagementStates.waiting_for_prize_emoji)

@dp.message(PrizeManagementStates.waiting_for_prize_emoji)
async def handle_prize_emoji(message: Message, state: FSMContext):
    """Обработка эмодзи приза"""
    emoji = message.text.strip()
    if len(emoji) > 10:  # Проверка на слишком длинный ввод
        await message.answer("❌ Эмодзи слишком длинное. Введите 1-10 символов.")
        return

    await state.update_data(prize_emoji=emoji)
    await confirm_prize_creation(message, state)

@dp.callback_query(lambda c: c.data == "default_emoji")
async def handle_default_emoji(callback: CallbackQuery, state: FSMContext):
    """Использование эмодзи по умолчанию"""
    await callback.answer()
    await state.update_data(prize_emoji="🎁")
    await confirm_prize_creation(callback.message, state)

async def confirm_prize_creation(message, state: FSMContext):
    """Подтверждение создания приза"""
    data = await state.get_data()

    # Получаем achievement_description для отображения
    achievement_desc = get_achievement_description(data['achievement_type'], data['achievement_value'])

    text = "🎁 <b>Подтверждение создания приза</b>\n\n"
    text += f"🏷️ <b>Название:</b> {data['prize_title']}\n"
    text += f"📝 <b>Описание:</b> {data.get('prize_description', 'Без описания')}\n"
    text += f"🎯 <b>Условие:</b> {achievement_desc}\n"
    text += f"😊 <b>Эмодзи:</b> {data.get('prize_emoji', '🎁')}\n"
    text += f"👑 <b>Тип:</b> {'Главный модератор' if data['prize_type'] == 'admin' else 'Блогер'}\n\n"
    text += "Создать этот приз?"

    await message.answer(text, reply_markup=InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ Создать", callback_data="confirm_create_prize")],
        [InlineKeyboardButton(text="❌ Отмена", callback_data="cancel_prize_creation")]
    ]))

    await state.set_state(PrizeManagementStates.confirming_prize)

@dp.callback_query(lambda c: c.data == "confirm_create_prize")
async def handle_confirm_create_prize(callback: CallbackQuery, state: FSMContext):
    """Подтверждение создания приза"""
    await callback.answer()

    data = await state.get_data()
    user_id = callback.from_user.id

    if await get_user_role(user_id) != ModeratorRole.ADMIN:
        await callback.message.edit_text("❌ У вас нет доступа к этой функции.")
        await state.clear()
        return

    # Создаем объект приза
    prize = Prize(
        prize_type=PrizeType.ADMIN if data['prize_type'] == 'admin' else PrizeType.BLOGGER,
        title=data['prize_title'],
        description=data.get('prize_description', ''),
        achievement_type=data['achievement_type'],
        achievement_value=data['achievement_value'],
        emoji=data.get('prize_emoji', '🎁'),
        is_active=True,
        created_at=int(datetime.datetime.now().timestamp()),
        updated_at=int(datetime.datetime.now().timestamp())
    )

    # Сохраняем в БД
    prize_id = await db.save_prize(prize)

    if prize_id:
        await callback.message.edit_text(
            f"✅ <b>Приз успешно создан!</b>\n\n"
            f"🏷️ <b>{prize.title}</b>\n"
            f"🆔 ID: {prize_id}\n\n"
            f"Приз теперь доступен для получения пользователями.",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="🎁 К управлению призами", callback_data="back_to_admin_menu")],
                [InlineKeyboardButton(text="➕ Создать еще один", callback_data="create_prize_admin")]
            ])
        )
    else:
        await callback.message.edit_text(
            "❌ Ошибка при создании приза.",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="⬅️ Назад", callback_data="back_to_admin_menu")]
            ])
        )

    await state.clear()

@dp.callback_query(lambda c: c.data == "cancel_prize_creation")
async def handle_cancel_prize_creation(callback: CallbackQuery, state: FSMContext):
    """Отмена создания приза"""
    await callback.answer()
    await callback.message.edit_text("❌ Создание приза отменено.")
    await state.clear()

@dp.callback_query(lambda c: c.data == "edit_prize")
async def handle_edit_prize(callback: CallbackQuery):
    """Редактирование приза"""
    await callback.answer()
    await callback.message.edit_text(
        "📝 <b>Редактирование призов</b>\n\n"
        "Функция редактирования призов находится в разработке.\n"
        "Пока что вы можете удалить старый приз и создать новый.",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="⬅️ Назад", callback_data="back_to_admin_menu")]
        ])
    )

@dp.callback_query(lambda c: c.data == "delete_prize")
async def handle_delete_prize(callback: CallbackQuery, state: FSMContext):
    """Удаление приза"""
    await callback.answer()

    text = "🗑️ <b>Удаление приза</b>\n\n"
    text += "Введите ID приза для удаления:\n\n"
    text += "<i>Посмотреть ID призов можно в разделе управления призами</i>"

    await callback.message.edit_text(text, reply_markup=InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="❌ Отмена", callback_data="cancel_delete_prize")]
    ]))

    await state.set_state(PrizeManagementStates.waiting_for_prize_id_to_delete)

@dp.message(PrizeManagementStates.waiting_for_prize_id_to_delete)
async def handle_prize_id_to_delete(message: Message, state: FSMContext):
    """Обработка ID приза для удаления"""
    try:
        prize_id = int(message.text.strip())
    except ValueError:
        await message.answer("❌ Введите корректный числовой ID приза.")
        return

    # Проверяем существование приза
    prize = await db.get_prize_by_id(prize_id)
    if not prize:
        await message.answer(
            "❌ Приз с таким ID не найден.",
            reply_markup=create_admin_keyboard()
        )
        await state.clear()
        return

    # Показываем подтверждение удаления
    text = "🗑️ <b>Подтверждение удаления</b>\n\n"
    text += f"🏷️ <b>{prize.title}</b>\n"
    text += f"🆔 ID: {prize.id}\n"
    text += f"🎯 {get_achievement_description(prize.achievement_type, prize.achievement_value)}\n\n"
    text += "Удалить этот приз?"

    await message.answer(text, reply_markup=InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🗑️ Удалить", callback_data=f"confirm_delete_prize_{prize_id}")],
        [InlineKeyboardButton(text="❌ Отмена", callback_data="cancel_delete_prize")]
    ]))

    await state.clear()

@dp.callback_query(lambda c: c.data.startswith("confirm_delete_prize_"))
async def handle_confirm_delete_prize(callback: CallbackQuery):
    """Подтверждение удаления приза"""
    await callback.answer()
    prize_id = int(callback.data.replace("confirm_delete_prize_", ""))

    success = await db.delete_prize(prize_id)

    if success:
        await callback.message.edit_text(
            f"✅ <b>Приз #{prize_id} успешно удален!</b>",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="🎁 К управлению призами", callback_data="back_to_admin_menu")]
            ])
        )
    else:
        await callback.message.edit_text(
            "❌ Ошибка при удалении приза.",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="⬅️ Назад", callback_data="back_to_admin_menu")]
            ])
        )

@dp.callback_query(lambda c: c.data == "cancel_delete_prize")
async def handle_cancel_delete_prize(callback: CallbackQuery, state: FSMContext):
    """Отмена удаления приза"""
    await callback.answer()
    await callback.message.edit_text("❌ Удаление приза отменено.")
    await state.clear()

@dp.callback_query(lambda c: c.data == "view_all_prizes")
async def handle_view_all_prizes(callback: CallbackQuery):
    """Просмотр всех призов"""
    await callback.answer()

    admin_prizes = await db.get_prizes(prize_type=PrizeType.ADMIN, is_active=True)
    blogger_prizes = await db.get_prizes(prize_type=PrizeType.BLOGGER, is_active=True)

    text = "🎁 <b>Все активные призы</b>\n\n"

    text += f"👑 <b>Призы главного модератора ({len(admin_prizes)}):</b>\n"
    if admin_prizes:
        for prize in admin_prizes:
            text += f"• {prize.emoji} <b>{prize.title}</b> (ID: {prize.id}) - {get_achievement_description(prize.achievement_type, prize.achievement_value)}\n"
    else:
        text += "   Нет активных призов\n"

    text += f"\n📣 <b>Призы блогеров ({len(blogger_prizes)}):</b>\n"
    if blogger_prizes:
        for prize in blogger_prizes:
            text += f"• {prize.emoji} <b>{prize.title}</b> (ID: {prize.id}, Код: {prize.referral_code}) - {get_achievement_description(prize.achievement_type, prize.achievement_value)}\n"
    else:
        text += "   Нет активных призов\n"

    await callback.message.edit_text(text, reply_markup=InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="⬅️ Назад", callback_data="back_to_admin_menu")]
    ]))

# Обработчики для управления модераторами
@dp.callback_query(lambda c: c.data == "remove_moderator")
async def handle_remove_moderator(callback: CallbackQuery, state: FSMContext):
    """Удаление модератора"""
    await callback.answer()

    text = "🛡️ <b>Удаление модератора</b>\n\n"
    text += "Введите Telegram ID модератора для удаления:\n\n"
    text += "<i>Посмотреть ID модераторов можно в списке выше</i>"

    await callback.message.edit_text(text, reply_markup=InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="❌ Отмена", callback_data="cancel_remove_moderator")]
    ]))

    await state.set_state(ModeratorManagementStates.waiting_for_moderator_id_to_remove)

@dp.message(ModeratorManagementStates.waiting_for_moderator_id_to_remove)
async def handle_moderator_id_to_remove(message: Message, state: FSMContext):
    """Обработка ID модератора для удаления"""
    try:
        telegram_id = int(message.text.strip())
    except ValueError:
        await message.answer("❌ Введите корректный числовой Telegram ID.")
        return

    # Проверяем существование модератора
    moderator = await db.get_moderator_by_telegram_id(telegram_id)
    if not moderator:
        await message.answer(
            "❌ Модератор с таким Telegram ID не найден.",
            reply_markup=create_admin_keyboard()
        )
        await state.clear()
        return

    # Показываем подтверждение удаления
    text = "🛡️ <b>Подтверждение удаления модератора</b>\n\n"
    text += f"🆔 Telegram ID: <code>{telegram_id}</code>\n"
    text += f"👤 Имя: {moderator.get('full_name', 'N/A')}\n"
    text += f"📅 Добавлен: {datetime.fromtimestamp(moderator['created_at']).strftime('%d.%m.%Y')}\n\n"
    text += "Удалить этого модератора?"

    await message.answer(text, reply_markup=InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🗑️ Удалить", callback_data=f"confirm_remove_moderator_{telegram_id}")],
        [InlineKeyboardButton(text="❌ Отмена", callback_data="cancel_remove_moderator")]
    ]))

    await state.clear()

@dp.callback_query(lambda c: c.data.startswith("confirm_remove_moderator_"))
async def handle_confirm_remove_moderator(callback: CallbackQuery):
    """Подтверждение удаления модератора"""
    await callback.answer()
    telegram_id = int(callback.data.replace("confirm_remove_moderator_", ""))

    success = await db.remove_moderator(telegram_id)

    if success:
        await callback.message.edit_text(
            f"✅ <b>Модератор успешно удален!</b>\n\n"
            f"🆔 Telegram ID: <code>{telegram_id}</code>",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="🛡️ К управлению модераторами", callback_data="back_to_moderators")]
            ])
        )
    else:
        await callback.message.edit_text(
            "❌ Ошибка при удалении модератора.",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="⬅️ Назад", callback_data="back_to_moderators")]
            ])
        )

@dp.callback_query(lambda c: c.data == "cancel_remove_moderator")
async def handle_cancel_remove_moderator(callback: CallbackQuery, state: FSMContext):
    """Отмена удаления модератора"""
    await callback.answer()
    await callback.message.edit_text("❌ Удаление модератора отменено.")
    await state.clear()

@dp.callback_query(lambda c: c.data == "view_all_moderators")
async def handle_view_all_moderators(callback: CallbackQuery):
    """Просмотр всех модераторов"""
    await callback.answer()

    all_moderators = await db.get_moderators(active_only=False)

    text = "🛡️ <b>Все модераторы</b>\n\n"

    if all_moderators:
        active_count = sum(1 for m in all_moderators if m['is_active'])
        inactive_count = len(all_moderators) - active_count

        text += f"📊 Активных: {active_count}, Неактивных: {inactive_count}\n\n"

        for mod in all_moderators:
            status = "✅ Активен" if mod['is_active'] else "❌ Неактивен"
            username = mod.get('username', 'N/A')
            full_name = mod.get('full_name', 'N/A')
            text += f"🆔 <code>{mod['telegram_id']}</code> - {status}\n"
            text += f"   👤 {full_name} (@{username})\n"
            text += f"   📅 {datetime.fromtimestamp(mod['created_at']).strftime('%d.%m.%Y')}\n\n"
    else:
        text += "👥 Модераторов пока нет."

    await callback.message.edit_text(text, reply_markup=InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="⬅️ Назад", callback_data="back_to_moderators")]
    ]))

# Обработчики для управления блогерами
@dp.callback_query(lambda c: c.data == "remove_blogger")
async def handle_remove_blogger(callback: CallbackQuery, state: FSMContext):
    """Удаление блогера"""
    await callback.answer()

    text = "📣 <b>Удаление блогера</b>\n\n"
    text += "Введите Telegram ID блогера для удаления:\n\n"
    text += "<i>Посмотреть ID блогеров можно в списке выше</i>"

    await callback.message.edit_text(text, reply_markup=InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="❌ Отмена", callback_data="cancel_remove_blogger")]
    ]))

    await state.set_state(BloggerManagementStates.waiting_for_blogger_id_to_remove)

@dp.message(BloggerManagementStates.waiting_for_blogger_id_to_remove)
async def handle_blogger_id_to_remove(message: Message, state: FSMContext):
    """Обработка ID блогера для удаления"""
    try:
        telegram_id = int(message.text.strip())
    except ValueError:
        await message.answer("❌ Введите корректный числовой Telegram ID.")
        return

    # Проверяем существование блогера
    blogger = await db.get_blogger_by_telegram_id(telegram_id)
    if not blogger:
        await message.answer(
            "❌ Блогер с таким Telegram ID не найден.",
            reply_markup=create_admin_keyboard()
        )
        await state.clear()
        return

    # Показываем подтверждение удаления
    text = "📣 <b>Подтверждение удаления блогера</b>\n\n"
    text += f"🆔 Telegram ID: <code>{telegram_id}</code>\n"
    text += f"🔗 Реферальный код: <code>{blogger['referral_code']}</code>\n"
    text += f"👤 Имя: {blogger.get('full_name', 'N/A')}\n"
    text += f"📅 Добавлен: {datetime.fromtimestamp(blogger['created_at']).strftime('%d.%m.%Y')}\n\n"
    text += "Удалить этого блогера?"

    await message.answer(text, reply_markup=InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🗑️ Удалить", callback_data=f"confirm_remove_blogger_{telegram_id}")],
        [InlineKeyboardButton(text="❌ Отмена", callback_data="cancel_remove_blogger")]
    ]))

    await state.clear()

@dp.callback_query(lambda c: c.data.startswith("confirm_remove_blogger_"))
async def handle_confirm_remove_blogger(callback: CallbackQuery):
    """Подтверждение удаления блогера"""
    await callback.answer()
    telegram_id = int(callback.data.replace("confirm_remove_blogger_", ""))

    success = await db.remove_blogger(telegram_id)

    if success:
        await callback.message.edit_text(
            f"✅ <b>Блогер успешно удален!</b>\n\n"
            f"🆔 Telegram ID: <code>{telegram_id}</code>",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="📣 К управлению блогерами", callback_data="back_to_bloggers")]
            ])
        )
    else:
        await callback.message.edit_text(
            "❌ Ошибка при удалении блогера.",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="⬅️ Назад", callback_data="back_to_bloggers")]
            ])
        )

@dp.callback_query(lambda c: c.data == "cancel_remove_blogger")
async def handle_cancel_remove_blogger(callback: CallbackQuery, state: FSMContext):
    """Отмена удаления блогера"""
    await callback.answer()
    await callback.message.edit_text("❌ Удаление блогера отменено.")
    await state.clear()

@dp.callback_query(lambda c: c.data == "view_all_bloggers")
async def handle_view_all_bloggers(callback: CallbackQuery):
    """Просмотр всех блогеров"""
    await callback.answer()

    all_bloggers = await db.get_bloggers(active_only=False)

    text = "📣 <b>Все блогеры</b>\n\n"

    if all_bloggers:
        active_count = sum(1 for b in all_bloggers if b['is_active'])
        inactive_count = len(all_bloggers) - active_count

        text += f"📊 Активных: {active_count}, Неактивных: {inactive_count}\n\n"

        for blogger in all_bloggers:
            status = "✅ Активен" if blogger['is_active'] else "❌ Неактивен"
            username = blogger.get('username', 'N/A')
            full_name = blogger.get('full_name', 'N/A')
            text += f"🆔 <code>{blogger['telegram_id']}</code> - {status}\n"
            text += f"   🔗 Код: <code>{blogger['referral_code']}</code>\n"
            text += f"   👤 {full_name} (@{username})\n"
            text += f"   📅 {datetime.fromtimestamp(blogger['created_at']).strftime('%d.%m.%Y')}\n\n"
    else:
        text += "👥 Блогеров пока нет."

    await callback.message.edit_text(text, reply_markup=InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="⬅️ Назад", callback_data="back_to_bloggers")]
    ]))

@dp.callback_query(lambda c: c.data == "add_prize")
async def handle_add_prize(callback: CallbackQuery):
    """Добавление приза"""
    await callback.answer()
    await callback.message.answer("Функция добавления приза в разработке")

@dp.callback_query(lambda c: c.data == "detailed_stats")
async def handle_detailed_stats(callback: CallbackQuery):
    """Детальная статистика"""
    await callback.answer()
    await callback.message.answer("Детальная статистика в разработке")

@dp.callback_query(lambda c: c.data == "top_users")
async def handle_top_users(callback: CallbackQuery):
    """Топ пользователей"""
    await callback.answer()
    await callback.message.answer("Функция топа пользователей в разработке")

# Обработчики отмены
@dp.callback_query(lambda c: c.data == "cancel_approval")
async def handle_cancel_approval(callback: CallbackQuery, state: FSMContext):
    """Отмена одобрения"""
    await callback.answer()
    await callback.message.edit_text("❌ Одобрение отменено.")
    await state.clear()

@dp.callback_query(lambda c: c.data == "cancel_rejection")
async def handle_cancel_rejection(callback: CallbackQuery, state: FSMContext):
    """Отмена отклонения"""
    await callback.answer()
    await callback.message.edit_text("❌ Отклонение отменено.")
    await state.clear()

# Callback handlers для управления модераторами и блогерами

@dp.callback_query(lambda c: c.data == "add_moderator")
async def handle_add_moderator(callback: CallbackQuery, state: FSMContext):
    """Добавление модератора"""
    await callback.answer()

    text = "🛡️ <b>Добавление модератора</b>\n\n"
    text += "Отправьте Telegram ID пользователя, которого хотите назначить модератором:\n\n"
    text += "Пример: <code>123456789</code>\n\n"
    text += "<i>Убедитесь, что пользователь уже общался с основным ботом для получения его данных.</i>"

    await callback.message.edit_text(text, reply_markup=InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="❌ Отмена", callback_data="cancel_add_moderator")]
    ]))

    await state.set_state(ModeratorManagementStates.waiting_for_moderator_telegram_id)

@dp.callback_query(lambda c: c.data == "add_blogger")
async def handle_add_blogger(callback: CallbackQuery, state: FSMContext):
    """Добавление блогера"""
    await callback.answer()

    text = "📣 <b>Добавление блогера</b>\n\n"
    text += "Отправьте Telegram ID пользователя, которого хотите зарегистрировать как блогера:\n\n"
    text += "Пример: <code>123456789</code>"

    await callback.message.edit_text(text, reply_markup=InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="❌ Отмена", callback_data="cancel_add_blogger")]
    ]))

    await state.set_state(BloggerManagementStates.waiting_for_blogger_telegram_id)

@dp.message(ModeratorManagementStates.waiting_for_moderator_telegram_id)
async def handle_moderator_telegram_id_for_add(message: Message, state: FSMContext):
    """Обработка Telegram ID для добавления модератора"""
    try:
        telegram_id = int(message.text.strip())

        # Проверяем, не является ли уже модератором
        existing_mod = await db.get_moderator_by_telegram_id(telegram_id)
        if existing_mod:
            await message.answer(
                "⚠️ <b>Этот пользователь уже является модератором!</b>\n\n"
                f"Telegram ID: <code>{telegram_id}</code>",
                reply_markup=create_admin_keyboard()
            )
            await state.clear()
            return

        # Сохраняем в состоянии
        await state.update_data(telegram_id=telegram_id)

        # Получаем информацию о пользователе из основной БД (если есть)
        user_info = f"Telegram ID: <code>{telegram_id}</code>"

        text = "🛡️ <b>Подтверждение добавления модератора</b>\n\n"
        text += f"{user_info}\n\n"
        text += "Добавить этого пользователя как модератора?"

        await message.answer(text, reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="✅ Добавить", callback_data="confirm_add_moderator")],
            [InlineKeyboardButton(text="❌ Отмена", callback_data="cancel_add_moderator")]
        ]))

        await state.set_state(ModeratorManagementStates.confirming_moderator_add)

    except ValueError:
        await message.answer(
            "❌ <b>Неверный формат Telegram ID</b>\n\n"
            "Отправьте корректный числовой Telegram ID.\n"
            "Пример: <code>123456789</code>",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="❌ Отмена", callback_data="cancel_add_moderator")]
            ])
        )

@dp.message(BloggerManagementStates.waiting_for_blogger_telegram_id)
async def handle_blogger_telegram_id(message: Message, state: FSMContext):
    """Обработка Telegram ID для блогера"""
    try:
        telegram_id = int(message.text.strip())

        # Проверяем, не является ли уже блогером
        existing_blogger = await db.get_blogger_by_telegram_id(telegram_id)
        if existing_blogger:
            await message.answer(
                "⚠️ <b>Этот пользователь уже зарегистрирован как блогер!</b>\n\n"
                f"Telegram ID: <code>{telegram_id}</code>\n"
                f"Реферальный код: <code>{existing_blogger['referral_code']}</code>",
                reply_markup=create_admin_keyboard()
            )
            await state.clear()
            return

        # Сохраняем в состоянии
        await state.update_data(telegram_id=telegram_id)

        text = "📣 <b>Добавление блогера</b>\n\n"
        text += f"Telegram ID: <code>{telegram_id}</code>\n\n"
        text += "Теперь укажите реферальный код для этого блогера:\n\n"
        text += "Пример: <code>BLOGGER2024</code>\n\n"
        text += "<i>Реферальный код должен быть уникальным и использоваться подписчиками блогера.</i>"

        await message.answer(text, reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="❌ Отмена", callback_data="cancel_add_blogger")]
        ]))

        await state.set_state(BloggerManagementStates.waiting_for_blogger_referral_code)

    except ValueError:
        await message.answer(
            "❌ <b>Неверный формат Telegram ID</b>\n\n"
            "Отправьте корректный числовой Telegram ID.\n"
            "Пример: <code>123456789</code>",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="❌ Отмена", callback_data="cancel_add_blogger")]
            ])
        )

@dp.message(BloggerManagementStates.waiting_for_blogger_referral_code)
async def handle_blogger_referral_code(message: Message, state: FSMContext):
    """Обработка реферального кода для блогера"""
    referral_code = message.text.strip().upper()

    # Проверяем уникальность реферального кода
    existing_blogger = await db.get_blogger_by_referral_code(referral_code)
    if existing_blogger:
        await message.answer(
            "❌ <b>Этот реферальный код уже используется!</b>\n\n"
            f"Код: <code>{referral_code}</code>\n\n"
            "Придумайте другой уникальный код.",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="❌ Отмена", callback_data="cancel_add_blogger")]
            ])
        )
        return

    # Сохраняем в состоянии
    data = await state.get_data()
    data['referral_code'] = referral_code
    await state.update_data(data)

    text = "📣 <b>Подтверждение добавления блогера</b>\n\n"
    text += f"Telegram ID: <code>{data['telegram_id']}</code>\n"
    text += f"Реферальный код: <code>{referral_code}</code>\n\n"
    text += "Добавить этого пользователя как блогера?"

    await message.answer(text, reply_markup=InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ Добавить", callback_data="confirm_add_blogger")],
        [InlineKeyboardButton(text="❌ Отмена", callback_data="cancel_add_blogger")]
    ]))

    await state.set_state(BloggerManagementStates.confirming_blogger_add)

@dp.callback_query(lambda c: c.data == "confirm_add_moderator")
async def handle_confirm_add_moderator(callback: CallbackQuery, state: FSMContext):
    """Подтверждение добавления модератора"""
    await callback.answer()

    data = await state.get_data()
    telegram_id = data.get('telegram_id')

    if not telegram_id:
        await callback.message.edit_text("❌ Ошибка: Telegram ID не найден.")
        await state.clear()
        return

    # Добавляем модератора
    success = await db.add_moderator(telegram_id)

    if success:
        await callback.message.edit_text(
            "✅ <b>Модератор успешно добавлен!</b>\n\n"
            f"Telegram ID: <code>{telegram_id}</code>\n\n"
            "Пользователь теперь имеет доступ к функциям модератора.",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="🛡️ К управлению модераторами", callback_data="back_to_moderators")],
                [InlineKeyboardButton(text="⬅️ В меню", callback_data="back_to_admin_menu")]
            ])
        )
    else:
        await callback.message.edit_text(
            "❌ Ошибка при добавлении модератора.",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="⬅️ Назад", callback_data="back_to_moderators")]
            ])
        )

    await state.clear()

@dp.callback_query(lambda c: c.data == "confirm_add_blogger")
async def handle_confirm_add_blogger(callback: CallbackQuery, state: FSMContext):
    """Подтверждение добавления блогера"""
    await callback.answer()

    data = await state.get_data()
    telegram_id = data.get('telegram_id')
    referral_code = data.get('referral_code')

    if not telegram_id or not referral_code:
        await callback.message.edit_text("❌ Ошибка: данные не найдены.")
        await state.clear()
        return

    # Добавляем блогера
    success = await db.add_blogger(telegram_id, referral_code)

    if success:
        await callback.message.edit_text(
            "✅ <b>Блогер успешно добавлен!</b>\n\n"
            f"Telegram ID: <code>{telegram_id}</code>\n"
            f"Реферальный код: <code>{referral_code}</code>\n\n"
            "Пользователь теперь имеет доступ к функциям блогера.",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="📣 К управлению блогерами", callback_data="back_to_bloggers")],
                [InlineKeyboardButton(text="⬅️ В меню", callback_data="back_to_admin_menu")]
            ])
        )
    else:
        await callback.message.edit_text(
            "❌ Ошибка при добавлении блогера.",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="⬅️ Назад", callback_data="back_to_bloggers")]
            ])
        )

    await state.clear()

@dp.callback_query(lambda c: c.data == "back_to_moderators")
async def handle_back_to_moderators(callback: CallbackQuery):
    """Возврат к управлению модераторами"""
    await callback.answer()
    # Имитируем вызов функции handle_admin_moderators
    await handle_admin_moderators(callback.message)

@dp.callback_query(lambda c: c.data == "back_to_bloggers")
async def handle_back_to_bloggers(callback: CallbackQuery):
    """Возврат к управлению блогерами"""
    await callback.answer()
    # Имитируем вызов функции handle_admin_bloggers
    await handle_admin_bloggers(callback.message)

# Обработчики отмены для управления персоналом
@dp.callback_query(lambda c: c.data == "cancel_add_moderator")
async def handle_cancel_add_moderator(callback: CallbackQuery, state: FSMContext):
    """Отмена добавления модератора"""
    await callback.answer()
    await callback.message.edit_text("❌ Добавление модератора отменено.")
    await state.clear()
    # Возвращаемся к управлению модераторами
    await handle_admin_moderators(callback.message)

@dp.callback_query(lambda c: c.data == "cancel_add_blogger")
async def handle_cancel_add_blogger(callback: CallbackQuery, state: FSMContext):
    """Отмена добавления блогера"""
    await callback.answer()
    await callback.message.edit_text("❌ Добавление блогера отменено.")
    await state.clear()
    # Возвращаемся к управлению блогерами
    await handle_admin_bloggers(callback.message)

async def main():
    """Главная функция запуска бота"""
    # Инициализация базы данных
    await db.init_db()

    logger.info("Модераторский бот запущен")

    # Запуск бота
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
