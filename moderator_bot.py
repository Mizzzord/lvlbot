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
from models import Prize, PrizeType, Rank, Subscription, SubscriptionStatus
from subscription_config import SUBSCRIPTION_LEVELS
import datetime

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
    logger.info(f"Проверка роли для {telegram_id}: админы = {admin_ids}")
    if telegram_id in admin_ids:
        logger.info(f"Пользователь {telegram_id} определен как ADMIN")
        return ModeratorRole.ADMIN

    # Проверяем блогеров
    blogger_ids = await db.get_blogger_telegram_ids()
    logger.info(f"Проверка роли для {telegram_id}: блогеры = {blogger_ids}")
    if telegram_id in blogger_ids:
        logger.info(f"Пользователь {telegram_id} определен как BLOGGER")
        return ModeratorRole.BLOGGER

    # Проверяем модераторов
    moderator_ids = await db.get_moderator_telegram_ids()
    logger.info(f"Проверка роли для {telegram_id}: модераторы = {moderator_ids}")
    if telegram_id in moderator_ids:
        logger.info(f"Пользователь {telegram_id} определен как MODERATOR")
        return ModeratorRole.MODERATOR

    logger.info(f"Пользователь {telegram_id} не имеет роли")
    return None

async def is_authorized(telegram_id: int) -> bool:
    """Проверка авторизации пользователя"""
    role = await get_user_role(telegram_id)
    return role is not None

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
    waiting_for_custom_condition = State()  # Новое состояние для произвольных условий
    waiting_for_subscription_level = State()  # Выбор уровня подписки
    waiting_for_prize_emoji = State()
    confirming_prize = State()
    waiting_for_prize_id_to_delete = State()
    # Состояния для редактирования призов
    editing_prize_title = State()
    editing_prize_description = State()
    editing_achievement_type = State()
    editing_achievement_value = State()
    editing_custom_condition = State()  # Новое состояние для редактирования произвольных условий
    editing_prize_emoji = State()
    editing_subscription_level = State()  # Редактирование уровня подписки
    confirming_prize_edit = State()

class UserSearchStates(StatesGroup):
    waiting_for_user_id = State()

class SubscriptionGrantStates(StatesGroup):
    waiting_for_user_id = State()
    waiting_for_level_selection = State()
    confirming_subscription = State()

def create_admin_keyboard() -> ReplyKeyboardMarkup:
    """Создание клавиатуры для главного модератора"""
    keyboard = [
        [KeyboardButton(text="🎁 Управление призами")],
        [KeyboardButton(text="👥 Статистика пользователей")],
        [KeyboardButton(text="📊 Общая статистика")],
        [KeyboardButton(text="🔍 Поиск пользователя")],
        [KeyboardButton(text="💎 Выдать подписку")],
        [KeyboardButton(text="🛡️ Управление модераторами"), KeyboardButton(text="📣 Управление блогерами")]
    ]
    return ReplyKeyboardMarkup(keyboard=keyboard, resize_keyboard=True)

def create_blogger_keyboard() -> ReplyKeyboardMarkup:
    """Создание клавиатуры для блогера"""
    keyboard = [
        [KeyboardButton(text="🎁 Управление призами")],
        [KeyboardButton(text="📊 Статистика подписчиков")],
        [KeyboardButton(text="🏆 Рейтинг подписчиков")],
        [KeyboardButton(text="🔗 Мой реферальный код")]
    ]
    return ReplyKeyboardMarkup(keyboard=keyboard, resize_keyboard=True)

def create_moderator_keyboard() -> ReplyKeyboardMarkup:
    """Создание клавиатуры для обычного модератора"""
    keyboard = [
        [KeyboardButton(text="📋 Проверить задания")],
        [KeyboardButton(text="⭐ VIP очередь")],
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
    """Просмотр обычных заданий на модерацию"""
    user_id = message.from_user.id
    logger.info(f"Пользователь {user_id} нажал 'Проверить задания'")

    if await get_user_role(user_id) != ModeratorRole.MODERATOR:
        await message.answer("❌ У вас нет доступа к этой функции.")
        logger.warning(f"Пользователь {user_id} попытался получить доступ к модерации без прав")
        return

    # Получаем обычные задания на модерацию (не VIP)
    pending_tasks = await db.get_pending_tasks_for_moderation(limit=10, vip_only=False)

    if not pending_tasks:
        await message.answer(
            "📋 <b>Задания на модерацию</b>\n\n"
            "✅ Все обычные задания проверены!\n"
            "Новых заданий на модерацию нет.\n\n"
            "💡 Проверьте <b>⭐ VIP очередь</b> для приоритетных заданий.",
            parse_mode="HTML",
            reply_markup=create_moderator_keyboard()
        )
        return

    text = "📋 <b>Обычные задания на модерацию</b>\n\n"
    keyboard = InlineKeyboardMarkup(inline_keyboard=[])

    for task_data in pending_tasks[:5]:
        # Обрабатываем как старый формат (6 элементов), так и новый (7 элементов с subscription_level)
        if len(task_data) >= 6:
            task_id, task_user_id, task_desc, media_path, user_name, nickname = task_data[:6]
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
        InlineKeyboardButton(text="⭐ VIP очередь", callback_data="check_vip_tasks"),
        InlineKeyboardButton(text="⬅️ В меню", callback_data="back_to_moderator_menu")
    ])

    logger.info(f"Отправлено сообщение с клавиатурой модератору {user_id}")
    await message.answer(text, reply_markup=keyboard)

@dp.message(lambda message: message.text == "⭐ VIP очередь")
@dp.callback_query(lambda c: c.data == "check_vip_tasks")
async def handle_moderator_check_vip_tasks(message_or_callback):
    """Просмотр приоритетных VIP заданий на модерацию"""
    # Определяем, это сообщение или callback
    if isinstance(message_or_callback, CallbackQuery):
        callback = message_or_callback
        message = callback.message
        user_id = callback.from_user.id
        await callback.answer()
    else:
        message = message_or_callback
        user_id = message.from_user.id
    
    logger.info(f"Пользователь {user_id} запросил VIP очередь")

    if await get_user_role(user_id) != ModeratorRole.MODERATOR:
        if isinstance(message_or_callback, CallbackQuery):
            await message.edit_text("❌ У вас нет доступа к этой функции.")
        else:
            await message.answer("❌ У вас нет доступа к этой функции.")
        logger.warning(f"Пользователь {user_id} попытался получить доступ к VIP очереди без прав")
        return

    # Получаем VIP задания на модерацию (уровень подписки >= 2)
    vip_tasks = await db.get_vip_pending_tasks_for_moderation(limit=10)

    if not vip_tasks:
        text = (
            "⭐ <b>VIP очередь заданий</b>\n\n"
            "✅ Все приоритетные задания проверены!\n"
            "Новых VIP заданий на модерацию нет.\n\n"
            "💡 Проверьте <b>📋 Обычные задания</b>."
        )
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="📋 Обычные задания", callback_data="check_regular_tasks")],
            [InlineKeyboardButton(text="⬅️ В меню", callback_data="back_to_moderator_menu")]
        ])
        
        if isinstance(message_or_callback, CallbackQuery):
            await message.edit_text(text, reply_markup=keyboard)
        else:
            await message.answer(text, reply_markup=keyboard)
        return

    text = "⭐ <b>VIP очередь заданий</b>\n\n"
    text += "👑 <b>Приоритетные задания от пользователей с уровнем подписки 2+</b>\n\n"
    keyboard = InlineKeyboardMarkup(inline_keyboard=[])

    for task_data in vip_tasks[:5]:
        # Обрабатываем формат с subscription_level
        if len(task_data) >= 6:
            task_id, task_user_id, task_desc, media_path, user_name, nickname = task_data[:6]
            subscription_level = task_data[6] if len(task_data) > 6 else None
            
            player_name = nickname or user_name
            short_desc = task_desc[:50] + "..." if len(task_desc) > 50 else task_desc
            
            # Добавляем индикатор уровня подписки
            level_emoji = ""
            if subscription_level and subscription_level >= 2:
                if subscription_level == 3:
                    level_emoji = "👑"
                elif subscription_level == 2:
                    level_emoji = "💎"
            
            text += f"{level_emoji} <b>ID {task_id}</b>: {player_name}\n"
            text += f"   └ {short_desc}\n\n"

            keyboard.inline_keyboard.append([
                InlineKeyboardButton(
                    text=f"⭐ Проверить #{task_id}",
                    callback_data=f"check_task_{task_id}"
                )
            ])
            logger.info(f"Добавлена кнопка check_task_{task_id} для VIP очереди модератора {user_id}")

    keyboard.inline_keyboard.append([
        InlineKeyboardButton(text="📋 Обычные задания", callback_data="check_regular_tasks"),
        InlineKeyboardButton(text="⬅️ В меню", callback_data="back_to_moderator_menu")
    ])

    logger.info(f"Отправлено сообщение с VIP очередью модератору {user_id}")
    if isinstance(message_or_callback, CallbackQuery):
        await message.edit_text(text, reply_markup=keyboard)
    else:
        await message.answer(text, reply_markup=keyboard)

@dp.callback_query(lambda c: c.data == "check_regular_tasks")
async def handle_check_regular_tasks(callback: CallbackQuery):
    """Переключение на обычные задания"""
    await callback.answer()
    await handle_moderator_check_tasks(callback.message)

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
    
    # Проверяем уровень подписки пользователя для определения VIP статуса
    user_id = task_details['user_id']
    active_subscription = await db.get_active_subscription(user_id)
    is_vip = False
    vip_indicator = ""
    subscription_level = None
    
    if active_subscription and active_subscription.subscription_level >= 2:
        is_vip = True
        subscription_level = active_subscription.subscription_level
        if subscription_level == 3:
            vip_indicator = "👑 VIP (Уровень 3)"
        elif subscription_level == 2:
            vip_indicator = "💎 VIP (Уровень 2)"

    # Формируем полный текст задания
    full_text = f"📝 <b>Задание #{task_id}</b>"
    if is_vip:
        full_text += f" {vip_indicator}"
    full_text += "\n\n"
    full_text += f"👤 <b>Игрок:</b> {nickname} ({user_name})\n"
    if is_vip:
        full_text += f"⭐ <b>Приоритетное задание</b>\n"
    full_text += f"🎯 <b>Задание:</b>\n{task_desc}\n\n"

    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ Одобрить", callback_data=f"approve_task_{task_id}")],
        [InlineKeyboardButton(text="❌ Отклонить", callback_data=f"reject_task_{task_id}")],
        [InlineKeyboardButton(text="⬅️ Назад к списку", callback_data="back_to_task_list")]
    ])

    # Проверяем, есть ли медиафайл
    media_path = task_details.get('submitted_media_path')
    if media_path and os.path.exists(media_path):
        # Для медиафайлов используем короткий caption (ограничение 1024 символа)
        # Полное описание отправляем отдельным сообщением
        short_caption = f"📝 <b>Задание #{task_id}</b>"
        if is_vip:
            short_caption += f" {vip_indicator}"
        short_caption += f"\n👤 <b>Игрок:</b> {nickname}\n📎 <b>Прикреплен файл</b>"
        
        # Если caption слишком длинный, обрезаем его
        if len(short_caption) > 1000:
            short_caption = short_caption[:997] + "..."

        try:
            if media_path.endswith(('.jpg', '.jpeg', '.png')):
                photo = FSInputFile(media_path)
                await callback.message.answer_photo(photo, caption=short_caption)
            elif media_path.endswith(('.mp4', '.avi', '.mov')):
                video = FSInputFile(media_path)
                await callback.message.answer_video(video, caption=short_caption)
            else:
                await callback.message.edit_text(full_text + "\n❌ Неподдерживаемый тип файла", reply_markup=keyboard)
                return
            
            # Отправляем полное описание задания отдельным сообщением
            # Разбиваем длинный текст на части, если он превышает 4096 символов
            max_length = 4000  # Оставляем запас
            if len(full_text) > max_length:
                # Разбиваем текст на части
                parts = []
                current_part = ""
                lines = full_text.split('\n')
                
                for line in lines:
                    if len(current_part) + len(line) + 1 > max_length:
                        if current_part:
                            parts.append(current_part)
                        current_part = line + '\n'
                    else:
                        current_part += line + '\n'
                
                if current_part:
                    parts.append(current_part)
                
                # Отправляем первую часть с клавиатурой
                await callback.message.answer(parts[0], reply_markup=keyboard, parse_mode="HTML")
                
                # Отправляем остальные части
                for part in parts[1:]:
                    await callback.message.answer(part, parse_mode="HTML")
            else:
                # Отправляем полное описание одним сообщением
                await callback.message.answer(full_text, reply_markup=keyboard, parse_mode="HTML")
                
        except Exception as e:
            logger.error(f"Ошибка отправки медиафайла: {e}")
            # Если ошибка, отправляем текст без медиафайла
            if len(full_text) > 4000:
                # Разбиваем на части
                parts = []
                current_part = ""
                lines = full_text.split('\n')
                
                for line in lines:
                    if len(current_part) + len(line) + 1 > 4000:
                        if current_part:
                            parts.append(current_part)
                        current_part = line + '\n'
                    else:
                        current_part += line + '\n'
                
                if current_part:
                    parts.append(current_part)
                
                await callback.message.edit_text(parts[0], reply_markup=keyboard, parse_mode="HTML")
                for part in parts[1:]:
                    await callback.message.answer(part, parse_mode="HTML")
            else:
                await callback.message.edit_text(full_text + "\n❌ Ошибка загрузки файла", reply_markup=keyboard, parse_mode="HTML")
    else:
        full_text += "📎 <b>Файл не прикреплен</b>\n"

        # Если текст слишком длинный, разбиваем на части
        if len(full_text) > 4000:
            parts = []
            current_part = ""
            lines = full_text.split('\n')
            
            for line in lines:
                if len(current_part) + len(line) + 1 > 4000:
                    if current_part:
                        parts.append(current_part)
                    current_part = line + '\n'
                else:
                    current_part += line + '\n'
            
            if current_part:
                parts.append(current_part)
            
            # Отправляем первую часть с клавиатурой
            await callback.message.edit_text(parts[0], reply_markup=keyboard, parse_mode="HTML")
            
            # Отправляем остальные части
            for part in parts[1:]:
                await callback.message.answer(part, parse_mode="HTML")
        else:
            await callback.message.edit_text(full_text, reply_markup=keyboard, parse_mode="HTML")

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
                reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                    [InlineKeyboardButton(text="📋 К следующим заданиям", callback_data="back_to_task_list")],
                    [InlineKeyboardButton(text="⬅️ В меню", callback_data="back_to_moderator_menu")]
                ]),
                parse_mode="HTML"
            )
        else:
            await message.answer(
                "❌ Ошибка при одобрении задания.",
                reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                    [InlineKeyboardButton(text="⬅️ Назад", callback_data="back_to_task_list")]
                ])
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

    # Получаем обычные задания на модерацию
    pending_tasks = await db.get_pending_tasks_for_moderation(limit=10, vip_only=False)

    if not pending_tasks:
        await callback.message.edit_text(
            "📋 <b>Задания на модерацию</b>\n\n"
            "✅ Все обычные задания проверены!\n"
            "Новых заданий на модерацию нет.\n\n"
            "💡 Проверьте <b>⭐ VIP очередь</b> для приоритетных заданий.",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="⭐ VIP очередь", callback_data="check_vip_tasks")],
                [InlineKeyboardButton(text="⬅️ В меню", callback_data="back_to_moderator_menu")]
            ])
        )
        return

    text = "📋 <b>Обычные задания на модерацию</b>\n\n"
    keyboard = InlineKeyboardMarkup(inline_keyboard=[])

    for task_data in pending_tasks[:5]:
        if len(task_data) >= 6:
            task_id, task_user_id, task_desc, media_path, user_name, nickname = task_data[:6]
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
        InlineKeyboardButton(text="⭐ VIP очередь", callback_data="check_vip_tasks"),
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
    regular_count = len(await db.get_pending_tasks_for_moderation(limit=1000, vip_only=False))
    vip_count = len(await db.get_vip_pending_tasks_for_moderation(limit=1000))
    total_pending = regular_count + vip_count

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
    text += f"⏳ Всего заданий: {total_pending}\n"
    text += f"📋 Обычных: {regular_count}\n"
    text += f"⭐ VIP: {vip_count}"

    await message.answer(text, reply_markup=create_moderator_keyboard())

# Обработчики для управления модераторами (только для админов)

async def show_admin_moderators_menu(user_id: int, message_or_callback):
    """Показ меню управления модераторами (универсальная функция)"""
    # Проверяем доступ
    if await get_user_role(user_id) != ModeratorRole.ADMIN:
        if hasattr(message_or_callback, 'answer'):
            await message_or_callback.answer("❌ У вас нет доступа к этой функции.")
        elif hasattr(message_or_callback, 'message'):
            await message_or_callback.message.answer("❌ У вас нет доступа к этой функции.")
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

    # Определяем, как отправлять сообщение
    if isinstance(message_or_callback, Message):
        await message_or_callback.answer(text, reply_markup=keyboard)
    elif hasattr(message_or_callback, 'message'):
        # Это CallbackQuery
        await message_or_callback.message.edit_text(text, reply_markup=keyboard)
    else:
        # Fallback
        await message_or_callback.answer(text, reply_markup=keyboard)

@dp.message(F.text == "🛡️ Управление модераторами")
async def handle_admin_moderators(message: Message):
    """Управление модераторами для главного модератора"""
    await show_admin_moderators_menu(message.from_user.id, message)

async def show_admin_bloggers_menu(user_id: int, message_or_callback):
    """Показ меню управления блогерами (универсальная функция)"""
    # Проверяем доступ
    if await get_user_role(user_id) != ModeratorRole.ADMIN:
        if hasattr(message_or_callback, 'answer'):
            await message_or_callback.answer("❌ У вас нет доступа к этой функции.")
        elif hasattr(message_or_callback, 'message'):
            await message_or_callback.message.answer("❌ У вас нет доступа к этой функции.")
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

    # Определяем, как отправлять сообщение
    if isinstance(message_or_callback, Message):
        await message_or_callback.answer(text, reply_markup=keyboard)
    elif hasattr(message_or_callback, 'message'):
        # Это CallbackQuery
        await message_or_callback.message.edit_text(text, reply_markup=keyboard)
    else:
        # Fallback
        await message_or_callback.answer(text, reply_markup=keyboard)

@dp.message(F.text == "📣 Управление блогерами")
async def handle_admin_bloggers(message: Message):
    """Управление блогерами для главного модератора"""
    await show_admin_bloggers_menu(message.from_user.id, message)

# Общий обработчик для управления призами
@dp.message(F.text == "🎁 Управление призами")
async def handle_prize_management(message: Message):
    """Управление призами - перенаправление в зависимости от роли"""
    logger.info(f"🎯 DEBUG: handle_prize_management вызвана для сообщения: '{message.text}'")
    user_id = message.from_user.id
    role = await get_user_role(user_id)
    logger.info(f"Роль пользователя {user_id}: {role}")

    if role == ModeratorRole.ADMIN:
        # Админ - показываем все призы
        logger.info(f"=== Перенаправление админа {user_id} в управление призами ===")

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

    elif role == ModeratorRole.BLOGGER:
        # Блогер - показываем только свои призы
        logger.info(f"=== Перенаправление блогера {user_id} в управление призами ===")

        # Получаем реферальный код блогера
        blogger = await db.get_blogger_by_telegram_id(user_id)
        logger.info(f"Результат get_blogger_by_telegram_id для {user_id}: {blogger}")

        if not blogger:
            logger.error(f"Блогер {user_id} не найден в базе данных")
            await message.answer("❌ Вы не зарегистрированы как блогер.")
            return

        referral_code = blogger['referral_code']

        # Получаем призы блогера
        blogger_prizes = await db.get_prizes(referral_code=referral_code, is_active=True)

        text = "🎁 <b>Управление вашими призами</b>\n\n"

        if blogger_prizes:
            text += f"📊 <b>Найдено призов:</b> {len(blogger_prizes)}\n\n"
            for prize in blogger_prizes:
                text += f"{prize.emoji} <b>{prize.title}</b>\n"
                if prize.description:
                    text += f"   └ {prize.description}\n"
                text += f"   └ Достижение: {get_achievement_description(prize.achievement_type, prize.achievement_value, prize.custom_condition)}\n"
                text += f"   └ ID: {prize.id}\n\n"
        else:
            text += "У вас пока нет созданных призов.\nИспользуйте кнопку '➕ Создать приз' для создания первого приза."

        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="➕ Создать приз", callback_data="create_blogger_prize")],
            [InlineKeyboardButton(text="✏️ Редактировать призы", callback_data="edit_blogger_prize")],
            [InlineKeyboardButton(text="🗑️ Удалить приз", callback_data="delete_blogger_prize")],
            [InlineKeyboardButton(text="⬅️ Назад", callback_data="back_to_blogger_menu")]
        ])

        await message.answer(text, reply_markup=keyboard)

    else:
        # Неизвестная роль
        logger.warning(f"Пользователь {user_id} с неизвестной ролью {role} попытался получить доступ к управлению призами")
        await message.answer("❌ У вас нет доступа к этой функции.")

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
        [InlineKeyboardButton(text="⬅️ Назад", callback_data="back_to_admin_menu")]
    ])

    await message.answer(text, reply_markup=keyboard)

@dp.message(F.text == "🔍 Поиск пользователя")
async def handle_admin_user_search(message: Message, state: FSMContext):
    """Поиск пользователя по Telegram ID для главного модератора"""
    user_id = message.from_user.id

    if await get_user_role(user_id) != ModeratorRole.ADMIN:
        await message.answer("❌ У вас нет доступа к этой функции.")
        return

    text = "🔍 <b>Поиск пользователя</b>\n\n"
    text += "Введите Telegram ID пользователя для поиска:"

    await message.answer(text, reply_markup=InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="⬅️ Назад", callback_data="back_to_admin_menu")]
    ]))

    await state.set_state(UserSearchStates.waiting_for_user_id)

@dp.message(UserSearchStates.waiting_for_user_id)
async def handle_user_id_input(message: Message, state: FSMContext):
    """Обработка введенного Telegram ID для поиска пользователя"""
    user_id = message.from_user.id

    if await get_user_role(user_id) != ModeratorRole.ADMIN:
        await state.clear()
        return

    try:
        search_user_id = int(message.text.strip())
    except ValueError:
        await message.answer("❌ Неверный формат Telegram ID. Введите число.",
                           reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                               [InlineKeyboardButton(text="⬅️ Назад", callback_data="back_to_admin_menu")]
                           ]))
        return

    # Ищем пользователя в базе данных
    user_stats = await db.get_user_stats(search_user_id)
    user_info = await db.get_user(search_user_id)

    if not user_info and not user_stats:
        await message.answer(f"❌ Пользователь с Telegram ID {search_user_id} не найден в системе.",
                           reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                               [InlineKeyboardButton(text="🔍 Искать другого", callback_data="search_another_user")],
                               [InlineKeyboardButton(text="⬅️ Назад", callback_data="back_to_admin_menu")]
                           ]))
        await state.clear()
        return

    # Формируем информацию о пользователе
    text = f"🔍 <b>Информация о пользователе</b>\n\n"
    text += f"🆔 <b>Telegram ID:</b> {search_user_id}\n"

    if user_info:
        text += f"👤 <b>Имя:</b> {user_info.name or 'Не указано'}\n"
        text += f"🏙️ <b>Город:</b> {user_info.city or 'Не указан'}\n"
        text += f"🎯 <b>Цель:</b> {user_info.goal or 'Не указана'}\n"
        text += f"🔗 <b>Реферальный код:</b> {user_info.referral_code or 'Нет'}\n"
        text += f"👥 <b>Приглашенных:</b> {user_info.referral_count}\n"

        if user_info.subscription_active:
            text += f"✅ <b>Подписка:</b> Активна\n"
            if user_info.subscription_end:
                import time
                end_date = time.strftime('%d.%m.%Y', time.localtime(user_info.subscription_end))
                text += f"📅 <b>Истекает:</b> {end_date}\n"
        else:
            text += f"❌ <b>Подписка:</b> Неактивна\n"

    if user_stats:
        text += f"\n📊 <b>Статистика:</b>\n"
        text += f"⭐ <b>Уровень:</b> {user_stats.level}\n"
        text += f"⚡ <b>Опыт:</b> {user_stats.experience}\n"
        text += f"🎯 <b>Выполнено заданий:</b> {user_stats.total_tasks_completed}\n"
        text += f"🔥 <b>Текущий стрик:</b> {user_stats.current_streak} дней\n"
        text += f"🏆 <b>Лучший стрик:</b> {user_stats.best_streak} дней\n"
        text += f"🎖️ <b>Ранг:</b> {user_stats.rank.value if user_stats.rank else 'Не определен'}\n"

        if user_stats.referral_rank:
            text += f"👥 <b>Реферальный ранг:</b> {user_stats.referral_rank.value}\n"

    await message.answer(text, reply_markup=InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔍 Искать другого", callback_data="search_another_user")],
        [InlineKeyboardButton(text="⬅️ Назад", callback_data="back_to_admin_menu")]
    ]))

    await state.clear()

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

# Обработчики для блогеров объявлены выше

@dp.message(F.text == "📊 Статистика подписчиков")
async def handle_blogger_stats(message: Message):
    """Статистика подписчиков блогера"""
    user_id = message.from_user.id
    role = await get_user_role(user_id)

    if role != ModeratorRole.BLOGGER:
        await message.answer("❌ У вас нет доступа к этой функции.")
        return

    # Получаем статистику блогера
    stats = await db.get_blogger_stats(user_id)

    if 'error' in stats:
        await message.answer(f"❌ {stats['error']}")
        return

    text = "📊 <b>Статистика ваших подписчиков</b>\n\n"
    text += f"🔗 <b>Реферальный код:</b> <code>{stats['referral_code']}</code>\n\n"
    text += f"👥 <b>Всего подписчиков:</b> {stats['total_subscribers']}\n"
    text += f"✅ <b>Активных (с подпиской):</b> {stats['active_subscribers']}\n"
    text += f"⏸️ <b>Неактивных:</b> {stats['inactive_subscribers']}\n\n"
    text += f"📈 <b>Заданий выполнено подписчиками:</b> {stats['total_tasks_completed']}\n\n"

    if stats['total_subscribers'] > 0:
        active_percentage = (stats['active_subscribers'] / stats['total_subscribers']) * 100
        text += f"📊 <b>Активность:</b> {active_percentage:.1f}% подписчиков имеют активную подписку"
    else:
        text += "💡 Поделитесь вашим реферальным кодом, чтобы привлечь первых подписчиков!"

    await message.answer(text, reply_markup=create_blogger_keyboard())

@dp.message(F.text == "🏆 Рейтинг подписчиков")
async def handle_blogger_ranking(message: Message):
    """Рейтинг топ-10 подписчиков блогера"""
    user_id = message.from_user.id
    role = await get_user_role(user_id)

    if role != ModeratorRole.BLOGGER:
        await message.answer("❌ У вас нет доступа к этой функции.")
        return

    # Получаем топ подписчиков блогера
    top_subscribers = await db.get_blogger_top_subscribers(user_id, limit=10)

    text = "🏆 <b>Рейтинг ваших подписчиков</b>\n\n"

    if top_subscribers:
        text += f"📊 <b>Топ {len(top_subscribers)} подписчиков по опыту:</b>\n\n"

        for i, subscriber in enumerate(top_subscribers, 1):
            medal = {1: "🥇", 2: "🥈", 3: "🥉"}.get(i, f"{i}.")
            text += f"{medal} <b>{subscriber['display_name']}</b>\n"
            text += f"   🆔 ID: <code>{subscriber['telegram_id']}</code>\n"
            text += f"   ⭐ Опыт: {subscriber['experience']}\n"
            text += f"   📊 Уровень: {subscriber['level']}\n"
            text += f"   ✅ Заданий: {subscriber['tasks_completed']}\n\n"
    else:
        text += "👥 У вас пока нет подписчиков с выполненными заданиями.\n\n"
        text += "💡 Поделитесь вашим реферальным кодом, чтобы подписчики начали выполнять задания!"

    # Получаем реферальный код для отображения внизу
    blogger = await db.get_blogger_by_telegram_id(user_id)
    if blogger:
        text += f"🔗 <b>Ваш реферальный код:</b> <code>{blogger['referral_code']}</code>\n"
        text += "📋 <i>Скопируйте код выше, чтобы поделиться им</i>"

    await message.answer(text, reply_markup=create_blogger_keyboard())

@dp.message(F.text == "🔗 Мой реферальный код")
async def handle_blogger_referral_code(message: Message):
    """Показать реферальный код блогера"""
    user_id = message.from_user.id
    role = await get_user_role(user_id)

    if role != ModeratorRole.BLOGGER:
        await message.answer("❌ У вас нет доступа к этой функции.")
        return

    # Получаем данные блогера
    blogger = await db.get_blogger_by_telegram_id(user_id)
    if not blogger:
        await message.answer("❌ Вы не зарегистрированы как блогер.")
        return

    referral_code = blogger['referral_code']

    text = "🔗 <b>Ваш реферальный код</b>\n\n"
    text += f"📋 <b>Код для подписчиков:</b>\n"
    text += f"<code>{referral_code}</code>\n\n"
    text += "📱 <b>Как использовать:</b>\n"
    text += "1. Скопируйте код выше\n"
    text += "2. Поделитесь им со своей аудиторией\n"
    text += "3. Ваши подписчики введут этот код в боте\n"
    text += "4. Вы будете получать статистику их активности\n\n"
    text += "🎁 <b>Преимущества для ваших подписчиков:</b>\n"
    text += "• Доступ к специальным призам от вас\n"
    text += "• Возможность соревноваться в вашем рейтинге\n"
    text += "• Отслеживание прогресса в вашем сообществе"

    await message.answer(text, reply_markup=create_blogger_keyboard())

# Обработчики для управления призами блогера

@dp.callback_query(lambda c: c.data == "create_blogger_prize")
async def handle_create_blogger_prize(callback: CallbackQuery, state: FSMContext):
    """Создание нового приза блогером"""
    await callback.answer()

    user_id = callback.from_user.id
    blogger = await db.get_blogger_by_telegram_id(user_id)
    if not blogger:
        await callback.message.edit_text("❌ Вы не зарегистрированы как блогер.")
        return

    # Начинаем процесс создания приза
    text = "🎁 <b>Создание нового приза</b>\n\n"
    text += "Введите название приза:"

    await callback.message.edit_text(text, reply_markup=InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="❌ Отмена", callback_data="cancel_blogger_prize")]
    ]))

    # Сохраняем информацию о блогере в состоянии
    await state.update_data(
        blogger_referral_code=blogger['referral_code'],
        prize_type='blogger'
    )
    await state.set_state(PrizeManagementStates.waiting_for_prize_title)

@dp.callback_query(lambda c: c.data == "edit_blogger_prize")
async def handle_edit_blogger_prize(callback: CallbackQuery):
    """Редактирование призов блогера"""
    await callback.answer()

    user_id = callback.from_user.id
    blogger = await db.get_blogger_by_telegram_id(user_id)
    if not blogger:
        await callback.message.edit_text("❌ Вы не зарегистрированы как блогер.")
        return

    prizes = await db.get_prizes(referral_code=blogger['referral_code'], is_active=True)

    if not prizes:
        await callback.message.edit_text(
            "❌ У вас нет призов для редактирования.",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="⬅️ Назад", callback_data="back_to_blogger_menu")]
            ])
        )
        return

    text = "✏️ <b>Выберите приз для редактирования:</b>\n\n"

    keyboard = []
    for prize in prizes:
        keyboard.append([
            InlineKeyboardButton(
                text=f"{prize.emoji} {prize.title}",
                callback_data=f"edit_prize_{prize.id}"
            )
        ])

    keyboard.append([InlineKeyboardButton(text="❌ Отмена", callback_data="cancel_blogger_prize")])

    await callback.message.edit_text(text, reply_markup=InlineKeyboardMarkup(inline_keyboard=keyboard))

@dp.callback_query(lambda c: c.data == "delete_blogger_prize")
async def handle_delete_blogger_prize(callback: CallbackQuery):
    """Удаление приза блогера"""
    await callback.answer()

    user_id = callback.from_user.id
    blogger = await db.get_blogger_by_telegram_id(user_id)
    if not blogger:
        await callback.message.edit_text("❌ Вы не зарегистрированы как блогер.")
        return

    prizes = await db.get_prizes(referral_code=blogger['referral_code'], is_active=True)

    if not prizes:
        await callback.message.edit_text(
            "❌ У вас нет призов для удаления.",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="⬅️ Назад", callback_data="back_to_blogger_menu")]
            ])
        )
        return

    text = "🗑️ <b>Выберите приз для удаления:</b>\n\n"

    keyboard = []
    for prize in prizes:
        keyboard.append([
            InlineKeyboardButton(
                text=f"{prize.emoji} {prize.title}",
                callback_data=f"delete_prize_{prize.id}"
            )
        ])

    keyboard.append([InlineKeyboardButton(text="❌ Отмена", callback_data="cancel_blogger_prize")])

    await callback.message.edit_text(text, reply_markup=InlineKeyboardMarkup(inline_keyboard=keyboard))

@dp.callback_query(lambda c: c.data.startswith("edit_admin_prize_"))
async def handle_edit_admin_prize_specific(callback: CallbackQuery, state: FSMContext):
    """Редактирование конкретного приза для главного модератора"""
    await callback.answer()
    prize_id = int(callback.data.replace("edit_admin_prize_", ""))

    # Проверяем права доступа
    user_id = callback.from_user.id
    if await get_user_role(user_id) != ModeratorRole.ADMIN:
        await callback.message.edit_text("❌ Доступ запрещен.")
        return

    prize = await db.get_prize_by_id(prize_id)
    if not prize:
        await callback.message.edit_text("❌ Приз не найден.")
        return

    # Сохраняем информацию о призе в состоянии
    await state.update_data(
        editing_prize_id=prize_id,
        editing_prize=prize,
        is_admin_edit=True  # Флаг для определения, что это редактирование админом
    )

    text = f"✏️ <b>Редактирование приза</b>\n\n"
    text += f"🎁 <b>{prize.title}</b>\n"
    text += f"📝 {prize.description or 'Без описания'}\n"
    text += f"🎯 {get_achievement_description(prize.achievement_type, prize.achievement_value, prize.custom_condition)}\n"
    text += f"😊 Эмодзи: {prize.emoji}\n"
    
    # Показываем уровень подписки, если установлен
    if prize.subscription_level:
        level_names = {1: "BASIC", 2: "PRIME", 3: "BASIC + PRIME"}
        text += f"💎 Уровень подписки: {prize.subscription_level} ({level_names.get(prize.subscription_level, 'Неизвестно')})\n"
    else:
        text += f"💎 Уровень подписки: Для всех уровней\n"
    
    text += f"👑 Тип: {'Главный модератор' if prize.prize_type == PrizeType.ADMIN else 'Блогер'}\n"
    if prize.referral_code:
        text += f"📣 Реферальный код: {prize.referral_code}\n"
    text += "\nЧто вы хотите изменить?"

    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🏷️ Название", callback_data="edit_title")],
        [InlineKeyboardButton(text="📝 Описание", callback_data="edit_description")],
        [InlineKeyboardButton(text="🎯 Условие", callback_data="edit_achievement")],
        [InlineKeyboardButton(text="😊 Эмодзи", callback_data="edit_emoji")],
        [InlineKeyboardButton(text="💎 Уровень подписки", callback_data="edit_subscription_level")],
        [InlineKeyboardButton(text="❌ Отмена", callback_data="cancel_admin_prize_edit")]
    ])

    await callback.message.edit_text(text, reply_markup=keyboard)

@dp.callback_query(lambda c: c.data.startswith("edit_prize_"))
async def handle_edit_specific_prize(callback: CallbackQuery, state: FSMContext):
    """Редактирование конкретного приза блогера"""
    await callback.answer()
    prize_id = int(callback.data.replace("edit_prize_", ""))

    # Проверяем, что приз принадлежит блогеру
    user_id = callback.from_user.id
    blogger = await db.get_blogger_by_telegram_id(user_id)
    if not blogger:
        await callback.message.edit_text("❌ Доступ запрещен.")
        return

    prize = await db.get_prize_by_id(prize_id)
    if not prize or prize.referral_code != blogger['referral_code']:
        await callback.message.edit_text("❌ Приз не найден или доступ запрещен.")
        return

    # Сохраняем информацию о призе в состоянии
    await state.update_data(
        editing_prize_id=prize_id,
        editing_prize=prize,
        is_admin_edit=False  # Флаг для определения, что это редактирование блогером
    )

    text = f"✏️ <b>Редактирование приза</b>\n\n"
    text += f"🎁 <b>{prize.title}</b>\n"
    text += f"📝 {prize.description or 'Без описания'}\n"
    text += f"🎯 {get_achievement_description(prize.achievement_type, prize.achievement_value, prize.custom_condition)}\n"
    text += f"😊 Эмодзи: {prize.emoji}\n\n"
    text += "Что вы хотите изменить?"

    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🏷️ Название", callback_data="edit_title")],
        [InlineKeyboardButton(text="📝 Описание", callback_data="edit_description")],
        [InlineKeyboardButton(text="🎯 Условие", callback_data="edit_achievement")],
        [InlineKeyboardButton(text="😊 Эмодзи", callback_data="edit_emoji")],
        [InlineKeyboardButton(text="❌ Отмена", callback_data="cancel_blogger_prize")]
    ])

    await callback.message.edit_text(text, reply_markup=keyboard)

# Обработчики редактирования призов
@dp.callback_query(lambda c: c.data == "edit_title")
async def handle_edit_title(callback: CallbackQuery, state: FSMContext):
    """Редактирование названия приза"""
    await callback.answer()

    data = await state.get_data()
    prize = data.get('editing_prize')
    if not prize:
        await callback.message.edit_text("❌ Ошибка: приз не найден.")
        await state.clear()
        return

    text = f"✏️ <b>Редактирование названия</b>\n\n"
    text += f"Текущее название: <b>{prize.title}</b>\n\n"
    text += "Введите новое название приза:"

    await callback.message.edit_text(text, reply_markup=InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="❌ Отмена", callback_data="cancel_edit")]
    ]))

    await state.set_state(PrizeManagementStates.editing_prize_title)

@dp.callback_query(lambda c: c.data == "edit_description")
async def handle_edit_description(callback: CallbackQuery, state: FSMContext):
    """Редактирование описания приза"""
    await callback.answer()

    data = await state.get_data()
    prize = data.get('editing_prize')
    if not prize:
        await callback.message.edit_text("❌ Ошибка: приз не найден.")
        await state.clear()
        return

    text = f"✏️ <b>Редактирование описания</b>\n\n"
    text += f"Текущее описание: {prize.description or 'Без описания'}\n\n"
    text += "Введите новое описание приза (или 'удалить' чтобы убрать описание):"

    await callback.message.edit_text(text, reply_markup=InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="⏭️ Пропустить", callback_data="skip_edit_description")],
        [InlineKeyboardButton(text="❌ Отмена", callback_data="cancel_edit")]
    ]))

    await state.set_state(PrizeManagementStates.editing_prize_description)

@dp.callback_query(lambda c: c.data == "edit_achievement")
async def handle_edit_achievement(callback: CallbackQuery, state: FSMContext):
    """Редактирование условия получения приза"""
    await callback.answer()

    data = await state.get_data()
    prize = data.get('editing_prize')
    if not prize:
        await callback.message.edit_text("❌ Ошибка: приз не найден.")
        await state.clear()
        return

    text = f"✏️ <b>Редактирование условия</b>\n\n"
    text += f"Текущее условие: {get_achievement_description(prize.achievement_type, prize.achievement_value, prize.custom_condition)}\n\n"
    text += "Выберите новый тип достижения:"

    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔥 Стрик (дни подряд)", callback_data="edit_achievement_streak")],
        [InlineKeyboardButton(text="🏅 Ранг", callback_data="edit_achievement_rank")],
        [InlineKeyboardButton(text="📊 Уровень", callback_data="edit_achievement_level")],
        [InlineKeyboardButton(text="✅ Задания", callback_data="edit_achievement_tasks")],
        [InlineKeyboardButton(text="⭐ Опыт", callback_data="edit_achievement_experience")],
        [InlineKeyboardButton(text="✏️ Произвольное условие", callback_data="edit_achievement_custom")],
        [InlineKeyboardButton(text="❌ Отмена", callback_data="cancel_edit")]
    ])

    await callback.message.edit_text(text, reply_markup=keyboard)

@dp.callback_query(lambda c: c.data == "edit_emoji")
async def handle_edit_emoji(callback: CallbackQuery, state: FSMContext):
    """Редактирование эмодзи приза"""
    await callback.answer()

    data = await state.get_data()
    prize = data.get('editing_prize')
    if not prize:
        await callback.message.edit_text("❌ Ошибка: приз не найден.")
        await state.clear()
        return

    text = f"✏️ <b>Редактирование эмодзи</b>\n\n"
    text += f"Текущий эмодзи: {prize.emoji}\n\n"
    text += "Введите новый эмодзи для приза:"

    await callback.message.edit_text(text, reply_markup=InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🎁 По умолчанию", callback_data="default_edit_emoji")],
        [InlineKeyboardButton(text="❌ Отмена", callback_data="cancel_edit")]
    ]))

    await state.set_state(PrizeManagementStates.editing_prize_emoji)

@dp.callback_query(lambda c: c.data == "cancel_edit")
async def handle_cancel_edit(callback: CallbackQuery, state: FSMContext):
    """Отмена редактирования приза"""
    await callback.answer()
    data = await state.get_data()
    is_admin_edit = data.get('is_admin_edit', False)
    await state.clear()

    # Возвращаемся к выбору приза для редактирования в зависимости от роли
    if is_admin_edit:
        await handle_edit_prize(callback)
    else:
        await handle_edit_blogger_prize(callback)

@dp.callback_query(lambda c: c.data == "cancel_admin_prize_edit")
async def handle_cancel_admin_prize_edit(callback: CallbackQuery, state: FSMContext):
    """Отмена редактирования приза админом"""
    await callback.answer()
    await state.clear()
    await handle_edit_prize(callback)

@dp.callback_query(lambda c: c.data == "edit_subscription_level")
async def handle_edit_subscription_level(callback: CallbackQuery, state: FSMContext):
    """Редактирование уровня подписки приза"""
    await callback.answer()
    
    data = await state.get_data()
    prize = data.get('editing_prize')
    is_admin_edit = data.get('is_admin_edit', False)
    
    if not prize:
        await callback.message.edit_text("❌ Ошибка: приз не найден.")
        await state.clear()
        return
    
    # Проверяем права доступа (только админ может редактировать уровень подписки)
    if not is_admin_edit:
        user_id = callback.from_user.id
        if await get_user_role(user_id) != ModeratorRole.ADMIN:
            await callback.message.edit_text("❌ Только главный модератор может редактировать уровень подписки.")
            return
    
    current_level = prize.subscription_level
    level_text = "Для всех уровней"
    if current_level == 2:
        level_text = "Для уровня 2 (PRIME)"
    elif current_level == 3:
        level_text = "Для уровня 3 (BASIC + PRIME)"
    
    text = f"✏️ <b>Редактирование уровня подписки</b>\n\n"
    text += f"Текущий уровень: <b>{level_text}</b>\n\n"
    text += "Выберите новый уровень подписки для приза:"
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🌐 Для всех уровней", callback_data="edit_sub_level_none")],
        [InlineKeyboardButton(text="💎 Уровень 2 (PRIME)", callback_data="edit_sub_level_2")],
        [InlineKeyboardButton(text="👑 Уровень 3 (BASIC + PRIME)", callback_data="edit_sub_level_3")],
        [InlineKeyboardButton(text="❌ Отмена", callback_data="cancel_edit")]
    ])
    
    await callback.message.edit_text(text, reply_markup=keyboard)

@dp.callback_query(lambda c: c.data.startswith("edit_sub_level_"))
async def handle_edit_subscription_level_selection(callback: CallbackQuery, state: FSMContext):
    """Обработка выбора уровня подписки при редактировании"""
    await callback.answer()
    
    level_data = callback.data.replace("edit_sub_level_", "")
    subscription_level = None
    if level_data == "2":
        subscription_level = 2
    elif level_data == "3":
        subscription_level = 3
    
    await state.update_data(editing_subscription_level=subscription_level)
    await confirm_prize_edit(callback.message, state)

@dp.callback_query(lambda c: c.data.startswith("edit_achievement_"))
async def handle_edit_achievement_type(callback: CallbackQuery, state: FSMContext):
    """Выбор типа достижения при редактировании"""
    await callback.answer()
    achievement_type = callback.data.replace("edit_achievement_", "")

    await state.update_data(editing_achievement_type=achievement_type)

    # Если выбрано произвольное условие, переходим к вводу текста
    if achievement_type == "custom":
        text = f"✏️ <b>Редактирование условия</b>\n\n"
        text += "✏️ <b>Произвольное условие</b>\n\n"
        text += "Введите описание условия получения приза:\n\n"
        text += "Примеры:\n"
        text += "• Стрик 7 дней И уровень 5\n"
        text += "• Выполнить 10 заданий за неделю\n"
        text += "• Достичь ранга B или выше\n"
        text += "• Набрать 1000 опыта за месяц"

        await callback.message.edit_text(text, reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="❌ Отмена", callback_data="cancel_edit")]
        ]))

        await state.set_state(PrizeManagementStates.editing_custom_condition)
        return

    # Показываем примеры значений для разных типов
    examples = {
        "streak": "Примеры: 7, 14, 30 (дни подряд)",
        "rank": "Примеры: 3 (Ранг C), 4 (Ранг B), 5 (Ранг A), 6 (Ранг S)",
        "level": "Примеры: 5, 10, 25 (уровень игрока)",
        "tasks": "Примеры: 10, 50, 100 (выполненных заданий)",
        "experience": "Примеры: 100, 500, 1000 (единиц опыта)"
    }

    text = f"✏️ <b>Редактирование условия</b>\n\n"
    text += f"Тип достижения: {achievement_type.title()}\n"
    text += f"{examples.get(achievement_type, '')}\n\n"
    text += "Введите новое значение достижения:"

    await callback.message.edit_text(text, reply_markup=InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="❌ Отмена", callback_data="cancel_edit")]
    ]))

    await state.set_state(PrizeManagementStates.editing_achievement_value)

@dp.callback_query(lambda c: c.data == "skip_edit_description")
async def handle_skip_edit_description(callback: CallbackQuery, state: FSMContext):
    """Пропуск редактирования описания"""
    await callback.answer()
    await state.update_data(editing_description="")

    # Переходим к подтверждению изменений
    await confirm_prize_edit(callback.message, state)

# Обработчики состояний редактирования
@dp.message(PrizeManagementStates.editing_prize_title)
async def handle_editing_prize_title(message: Message, state: FSMContext):
    """Обработка нового названия приза"""
    title = message.text.strip()
    if len(title) < 3:
        await message.answer("❌ Название приза должно содержать минимум 3 символа.")
        return

    await state.update_data(editing_title=title)
    await confirm_prize_edit(message, state)

@dp.message(PrizeManagementStates.editing_prize_description)
async def handle_editing_prize_description(message: Message, state: FSMContext):
    """Обработка нового описания приза"""
    description = message.text.strip()
    if description.lower() == 'удалить':
        description = ""

    await state.update_data(editing_description=description)
    await confirm_prize_edit(message, state)

@dp.message(PrizeManagementStates.editing_custom_condition)
async def handle_editing_custom_condition(message: Message, state: FSMContext):
    """Обработка произвольного условия при редактировании"""
    custom_condition = message.text.strip()
    
    if len(custom_condition) < 5:
        await message.answer("❌ Описание условия должно содержать минимум 5 символов.")
        return
    
    if len(custom_condition) > 500:
        await message.answer("❌ Описание условия слишком длинное (максимум 500 символов).")
        return
    
    await state.update_data(editing_custom_condition=custom_condition, editing_achievement_value=0)
    await confirm_prize_edit(message, state)

@dp.message(PrizeManagementStates.editing_achievement_value)
async def handle_editing_achievement_value(message: Message, state: FSMContext):
    """Обработка нового значения достижения"""
    try:
        value = int(message.text.strip())
        if value <= 0:
            await message.answer("❌ Значение должно быть положительным числом.")
            return
    except ValueError:
        await message.answer("❌ Введите корректное число.")
        return

    await state.update_data(editing_achievement_value=value, editing_custom_condition=None)
    await confirm_prize_edit(message, state)

@dp.message(PrizeManagementStates.editing_prize_emoji)
async def handle_editing_prize_emoji(message: Message, state: FSMContext):
    """Обработка нового эмодзи приза"""
    emoji = message.text.strip()
    if len(emoji) > 10:  # Проверка на слишком длинный ввод
        await message.answer("❌ Эмодзи слишком длинное. Введите 1-10 символов.")
        return

    await state.update_data(editing_emoji=emoji)
    await confirm_prize_edit(message, state)

@dp.callback_query(lambda c: c.data == "default_edit_emoji")
async def handle_default_edit_emoji(callback: CallbackQuery, state: FSMContext):
    """Использование эмодзи по умолчанию при редактировании"""
    await callback.answer()
    await state.update_data(editing_emoji="🎁")
    await confirm_prize_edit(callback.message, state)

async def confirm_prize_edit(message, state: FSMContext):
    """Подтверждение изменений приза"""
    data = await state.get_data()
    original_prize = data.get('editing_prize')

    if not original_prize:
        await message.answer("❌ Ошибка: приз не найден.")
        await state.clear()
        return

    # Собираем измененные данные
    changes = {}
    if 'editing_title' in data:
        changes['title'] = data['editing_title']
    if 'editing_description' in data:
        changes['description'] = data['editing_description']
    if 'editing_achievement_type' in data:
        changes['achievement_type'] = data['editing_achievement_type']
    if 'editing_achievement_value' in data:
        changes['achievement_value'] = data['editing_achievement_value']
    if 'editing_emoji' in data:
        changes['emoji'] = data['editing_emoji']

    if not changes:
        await message.answer("❌ Нет изменений для применения.")
        await state.clear()
        return

    # Показываем что изменится
    text = "✏️ <b>Подтверждение изменений</b>\n\n"
    text += f"🎁 <b>{original_prize.title}</b>\n\n"

    if 'editing_title' in data:
        text += f"🏷️ Название: {original_prize.title} → <b>{data['editing_title']}</b>\n"
    if 'editing_description' in data:
        old_desc = original_prize.description or 'Без описания'
        new_desc = data['editing_description'] or 'Без описания'
        text += f"📝 Описание: {old_desc} → <b>{new_desc}</b>\n"
    if 'editing_achievement_type' in data or 'editing_achievement_value' in data:
        new_type = data.get('editing_achievement_type', original_prize.achievement_type)
        new_value = data.get('editing_achievement_value', original_prize.achievement_value)
        old_achievement = get_achievement_description(original_prize.achievement_type, original_prize.achievement_value, original_prize.custom_condition)
        new_custom_condition = data.get('editing_custom_condition', original_prize.custom_condition)
        new_achievement = get_achievement_description(new_type, new_value, new_custom_condition)
        text += f"🎯 Условие: {old_achievement} → <b>{new_achievement}</b>\n"
    if 'editing_emoji' in data:
        text += f"😊 Эмодзи: {original_prize.emoji} → <b>{data['editing_emoji']}</b>\n"
    if 'editing_subscription_level' in data:
        level_names = {None: "Для всех уровней", 2: "Уровень 2 (PRIME)", 3: "Уровень 3 (BASIC + PRIME)"}
        old_level = level_names.get(original_prize.subscription_level, "Для всех уровней")
        new_level = level_names.get(data['editing_subscription_level'], "Для всех уровней")
        text += f"💎 Уровень подписки: {old_level} → <b>{new_level}</b>\n"

    text += "\nПрименить эти изменения?"

    await message.answer(text, reply_markup=InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ Применить", callback_data="confirm_prize_edit")],
        [InlineKeyboardButton(text="❌ Отмена", callback_data="cancel_edit")]
    ]))

    await state.set_state(PrizeManagementStates.confirming_prize_edit)

@dp.callback_query(lambda c: c.data == "confirm_prize_edit")
async def handle_confirm_prize_edit(callback: CallbackQuery, state: FSMContext):
    """Применение изменений приза"""
    await callback.answer()

    data = await state.get_data()
    prize_id = data.get('editing_prize_id')
    original_prize = data.get('editing_prize')
    is_admin_edit = data.get('is_admin_edit', False)

    if not prize_id or not original_prize:
        await callback.message.edit_text("❌ Ошибка: данные приза не найдены.")
        await state.clear()
        return

    # Проверяем права доступа
    user_id = callback.from_user.id
    if is_admin_edit:
        # Для админа проверяем, что он действительно админ
        if await get_user_role(user_id) != ModeratorRole.ADMIN:
            await callback.message.edit_text("❌ Доступ запрещен.")
            await state.clear()
            return
    else:
        # Для блогера проверяем, что приз принадлежит ему
        blogger = await db.get_blogger_by_telegram_id(user_id)
        if not blogger or original_prize.referral_code != blogger['referral_code']:
            await callback.message.edit_text("❌ Доступ запрещен.")
            await state.clear()
            return

    # Создаем обновленный объект приза
    updated_prize = Prize(
        id=prize_id,
        prize_type=original_prize.prize_type,
        referral_code=original_prize.referral_code,
        title=data.get('editing_title', original_prize.title),
        description=data.get('editing_description', original_prize.description),
        achievement_type=data.get('editing_achievement_type', original_prize.achievement_type),
        achievement_value=data.get('editing_achievement_value', original_prize.achievement_value),
        custom_condition=data.get('editing_custom_condition', original_prize.custom_condition),
        emoji=data.get('editing_emoji', original_prize.emoji),
        subscription_level=data.get('editing_subscription_level', original_prize.subscription_level),  # Добавляем уровень подписки
        is_active=original_prize.is_active,
        created_at=original_prize.created_at,
        updated_at=int(datetime.datetime.now().timestamp())
    )

    # Сохраняем изменения
    success = await db.save_prize(updated_prize)

    if success:
        # Определяем callback для возврата в зависимости от роли
        if is_admin_edit:
            back_callback = "back_to_admin_menu"
            edit_another_callback = "edit_prize"
        else:
            back_callback = "back_to_blogger_menu"
            edit_another_callback = "edit_blogger_prize"
        
        await callback.message.edit_text(
            f"✅ <b>Приз успешно обновлен!</b>\n\n"
            f"🎁 <b>{updated_prize.title}</b>\n"
            f"✏️ Изменения применены",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="🎁 К управлению призами", callback_data=back_callback)],
                [InlineKeyboardButton(text="✏️ Редактировать еще", callback_data=edit_another_callback)]
            ])
        )
    else:
        # Определяем callback для возврата в зависимости от роли
        if is_admin_edit:
            back_callback = "edit_prize"
        else:
            back_callback = "edit_blogger_prize"
        
        await callback.message.edit_text(
            "❌ Ошибка при обновлении приза.",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="⬅️ Назад", callback_data=back_callback)]
            ])
        )

    await state.clear()

@dp.callback_query(lambda c: c.data.startswith("delete_prize_"))
async def handle_delete_specific_prize(callback: CallbackQuery):
    """Удаление конкретного приза"""
    await callback.answer()
    prize_id = int(callback.data.replace("delete_prize_", ""))

    # Проверяем, что приз принадлежит блогеру
    user_id = callback.from_user.id
    blogger = await db.get_blogger_by_telegram_id(user_id)
    if not blogger:
        await callback.message.edit_text("❌ Доступ запрещен.")
        return

    prize = await db.get_prize_by_id(prize_id)
    if not prize or prize.referral_code != blogger['referral_code']:
        await callback.message.edit_text("❌ Приз не найден или доступ запрещен.")
        return

    # Удаляем приз
    success = await db.delete_prize(prize_id)

    if success:
        await callback.message.edit_text(
            f"✅ <b>Приз удален!</b>\n\n"
            f"🎁 {prize.title}\n\n"
            f"Приз больше не доступен для ваших подписчиков.",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="⬅️ К управлению призами", callback_data="back_to_blogger_menu")]
            ])
        )
    else:
        await callback.message.edit_text(
            "❌ Ошибка при удалении приза.",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="⬅️ Назад", callback_data="delete_blogger_prize")]
            ])
        )

@dp.callback_query(lambda c: c.data == "cancel_blogger_prize")
async def handle_cancel_blogger_prize(callback: CallbackQuery, state: FSMContext):
    """Отмена операций с призами блогера"""
    await callback.answer()
    await state.clear()

    # Возвращаемся к управлению призами
    await handle_blogger_prizes(callback.message)

# Вспомогательные функции

def get_achievement_description(achievement_type: str, achievement_value: int, custom_condition: Optional[str] = None) -> str:
    """Получение описания достижения"""
    # Если это произвольное условие, возвращаем его текст
    if achievement_type == 'custom' and custom_condition:
        return custom_condition
    
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

@dp.callback_query(lambda c: c.data == "search_another_user")
async def handle_search_another_user(callback: CallbackQuery, state: FSMContext):
    """Перезапуск поиска пользователя"""
    await callback.answer()

    user_id = callback.from_user.id
    if await get_user_role(user_id) != ModeratorRole.ADMIN:
        return

    text = "🔍 <b>Поиск пользователя</b>\n\n"
    text += "Введите Telegram ID пользователя для поиска:"

    await callback.message.edit_text(text, reply_markup=InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="⬅️ Назад", callback_data="back_to_admin_menu")]
    ]))

    await state.set_state(UserSearchStates.waiting_for_user_id)


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
        [InlineKeyboardButton(text="✏️ Произвольное условие", callback_data="achievement_custom")],
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
        [InlineKeyboardButton(text="✏️ Произвольное условие", callback_data="achievement_custom")],
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

    # Если выбрано произвольное условие, переходим к вводу текста
    if achievement_type == "custom":
        text = "🎁 <b>Создание приза</b>\n\n"
        text += "✏️ <b>Произвольное условие</b>\n\n"
        text += "Введите описание условия получения приза:\n\n"
        text += "Примеры:\n"
        text += "• Стрик 7 дней И уровень 5\n"
        text += "• Выполнить 10 заданий за неделю\n"
        text += "• Достичь ранга B или выше\n"
        text += "• Набрать 1000 опыта за месяц"

        await callback.message.edit_text(text, reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="❌ Отмена", callback_data="cancel_prize_creation")]
        ]))

        await state.set_state(PrizeManagementStates.waiting_for_custom_condition)
        return

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

@dp.message(PrizeManagementStates.waiting_for_custom_condition)
async def handle_custom_condition(message: Message, state: FSMContext):
    """Обработка произвольного условия"""
    custom_condition = message.text.strip()
    
    if len(custom_condition) < 5:
        await message.answer("❌ Описание условия должно содержать минимум 5 символов.")
        return
    
    if len(custom_condition) > 500:
        await message.answer("❌ Описание условия слишком длинное (максимум 500 символов).")
        return
    
    await state.update_data(custom_condition=custom_condition, achievement_value=0)
    
    text = "🎁 <b>Создание приза</b>\n\n"
    text += f"Условие: {custom_condition}\n\n"
    text += "Выберите уровень подписки для приза:"
    
    await message.answer(text, reply_markup=InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🌐 Для всех уровней", callback_data="sub_level_all")],
        [InlineKeyboardButton(text="⭐ Для уровня 2 (Продвинутый)", callback_data="sub_level_2")],
        [InlineKeyboardButton(text="💎 Для уровня 3 (Мастер)", callback_data="sub_level_3")],
        [InlineKeyboardButton(text="❌ Отмена", callback_data="cancel_prize_creation")]
    ]))
    
    await state.set_state(PrizeManagementStates.waiting_for_subscription_level)

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
    text += "Выберите уровень подписки для приза:"

    await message.answer(text, reply_markup=InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🌐 Для всех уровней", callback_data="sub_level_all")],
        [InlineKeyboardButton(text="⭐ Для уровня 2 (Продвинутый)", callback_data="sub_level_2")],
        [InlineKeyboardButton(text="💎 Для уровня 3 (Мастер)", callback_data="sub_level_3")],
        [InlineKeyboardButton(text="❌ Отмена", callback_data="cancel_prize_creation")]
    ]))

    await state.set_state(PrizeManagementStates.waiting_for_subscription_level)

@dp.message(PrizeManagementStates.waiting_for_prize_emoji)
async def handle_prize_emoji(message: Message, state: FSMContext):
    """Обработка эмодзи приза"""
    emoji = message.text.strip()
    if len(emoji) > 10:  # Проверка на слишком длинный ввод
        await message.answer("❌ Эмодзи слишком длинное. Введите 1-10 символов.")
        return

    await state.update_data(prize_emoji=emoji)
    await confirm_prize_creation(message, state)

@dp.callback_query(lambda c: c.data.startswith("sub_level_"))
async def handle_subscription_level_selection(callback: CallbackQuery, state: FSMContext):
    """Обработка выбора уровня подписки для приза"""
    await callback.answer()
    
    level_data = callback.data.replace("sub_level_", "")
    subscription_level = None
    if level_data == "2":
        subscription_level = 2
    elif level_data == "3":
        subscription_level = 3
    
    await state.update_data(prize_subscription_level=subscription_level)
    
    text = "🎁 <b>Создание приза</b>\n\n"
    level_text = "Для всех уровней"
    if subscription_level == 2:
        level_text = "Для уровня 2 (Продвинутый)"
    elif subscription_level == 3:
        level_text = "Для уровня 3 (Мастер)"
    text += f"Уровень подписки: {level_text}\n\n"
    text += "Введите эмодзи для приза (или нажмите '🎁 По умолчанию'):"
    
    await callback.message.edit_text(text, reply_markup=InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🎁 По умолчанию", callback_data="default_emoji")],
        [InlineKeyboardButton(text="❌ Отмена", callback_data="cancel_prize_creation")]
    ]))
    
    await state.set_state(PrizeManagementStates.waiting_for_prize_emoji)

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
    achievement_desc = get_achievement_description(
        data['achievement_type'], 
        data.get('achievement_value', 0),
        data.get('custom_condition')
    )

    subscription_level = data.get('prize_subscription_level')
    level_text = "Для всех уровней"
    if subscription_level == 2:
        level_text = "Для уровня 2 (Продвинутый)"
    elif subscription_level == 3:
        level_text = "Для уровня 3 (Мастер)"

    text = "🎁 <b>Подтверждение создания приза</b>\n\n"
    text += f"🏷️ <b>Название:</b> {data['prize_title']}\n"
    text += f"📝 <b>Описание:</b> {data.get('prize_description', 'Без описания')}\n"
    text += f"🎯 <b>Условие:</b> {achievement_desc}\n"
    text += f"😊 <b>Эмодзи:</b> {data.get('prize_emoji', '🎁')}\n"
    text += f"👑 <b>Тип:</b> {'Главный модератор' if data['prize_type'] == 'admin' else 'Блогер'}\n"
    text += f"⭐ <b>Уровень подписки:</b> {level_text}\n\n"
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
    logger.info(f"handle_confirm_create_prize вызвана. User: {user_id}, Data keys: {list(data.keys())}")
    logger.info(f"FSM Data: {data}")

    # Проверяем роль пользователя
    user_role = await get_user_role(user_id)
    if user_role not in [ModeratorRole.ADMIN, ModeratorRole.BLOGGER]:
        await callback.message.edit_text("❌ У вас нет доступа к этой функции.")
        await state.clear()
        return

    # Определяем referral_code
    referral_code = None
    prize_type = data.get('prize_type')

    if not prize_type:
        logger.error(f"prize_type не найден в данных FSM state. Data: {data}")
        await callback.message.edit_text("❌ Ошибка: тип приза не определен. Попробуйте создать приз заново.")
        await state.clear()
        return

    if prize_type == 'blogger':
        referral_code = data.get('blogger_referral_code')
        if not referral_code:
            await callback.message.edit_text("❌ Ошибка: реферальный код не найден.")
            await state.clear()
            return

    # Создаем объект приза
    prize = Prize(
        prize_type=PrizeType.ADMIN if prize_type == 'admin' else PrizeType.BLOGGER,
        referral_code=referral_code,
        title=data['prize_title'],
        description=data.get('prize_description', ''),
        achievement_type=data['achievement_type'],
        achievement_value=data.get('achievement_value', 0),
        custom_condition=data.get('custom_condition'),  # Произвольное условие
        subscription_level=data.get('prize_subscription_level'),  # Уровень подписки (None, 2 или 3)
        emoji=data.get('prize_emoji', '🎁'),
        is_active=True,
        created_at=int(datetime.datetime.now().timestamp()),
        updated_at=int(datetime.datetime.now().timestamp())
    )

    # Сохраняем в БД
    prize_id = await db.save_prize(prize)

    if prize_id:
        # Определяем кнопки возврата в зависимости от роли
        if prize_type == 'blogger':
            back_callback = "back_to_blogger_menu"
            create_another_callback = "create_blogger_prize"
            user_description = "вашим подписчикам"
        else:
            back_callback = "back_to_admin_menu"
            create_another_callback = "create_prize_admin"
            user_description = "пользователям"

        await callback.message.edit_text(
            f"✅ <b>Приз успешно создан!</b>\n\n"
            f"🏷️ <b>{prize.title}</b>\n"
            f"🆔 ID: {prize_id}\n\n"
            f"Приз теперь доступен для получения {user_description}.",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="🎁 К управлению призами", callback_data=back_callback)],
                [InlineKeyboardButton(text="➕ Создать еще один", callback_data=create_another_callback)]
            ])
        )
    else:
        back_callback = "back_to_blogger_menu" if prize_type == 'blogger' else "back_to_admin_menu"
        await callback.message.edit_text(
            "❌ Ошибка при создании приза.",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="⬅️ Назад", callback_data=back_callback)]
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
    """Редактирование приза - выбор приза для главного модератора"""
    await callback.answer()
    
    user_id = callback.from_user.id
    if await get_user_role(user_id) != ModeratorRole.ADMIN:
        await callback.message.edit_text("❌ У вас нет доступа к этой функции.")
        return
    
    # Получаем все призы (админские и блогерские)
    admin_prizes = await db.get_prizes(prize_type=PrizeType.ADMIN, is_active=True)
    blogger_prizes = await db.get_prizes(prize_type=PrizeType.BLOGGER, is_active=True)
    
    if not admin_prizes and not blogger_prizes:
        await callback.message.edit_text(
            "❌ Нет призов для редактирования.",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="⬅️ Назад", callback_data="back_to_admin_menu")]
            ])
        )
        return
    
    text = "✏️ <b>Выберите приз для редактирования:</b>\n\n"
    
    keyboard = []
    
    # Добавляем админские призы
    if admin_prizes:
        text += f"👑 <b>Призы главного модератора:</b>\n"
        for prize in admin_prizes[:10]:  # Ограничиваем до 10 для удобства
            level_text = ""
            if prize.subscription_level:
                level_text = f" [Ур.{prize.subscription_level}]"
            keyboard.append([
                InlineKeyboardButton(
                    text=f"{prize.emoji} {prize.title}{level_text}",
                    callback_data=f"edit_admin_prize_{prize.id}"
                )
            ])
        if len(admin_prizes) > 10:
            text += f"... и еще {len(admin_prizes) - 10} призов\n"
        text += "\n"
    
    # Добавляем блогерские призы
    if blogger_prizes:
        text += f"📣 <b>Призы блогеров:</b>\n"
        for prize in blogger_prizes[:10]:  # Ограничиваем до 10 для удобства
            level_text = ""
            if prize.subscription_level:
                level_text = f" [Ур.{prize.subscription_level}]"
            keyboard.append([
                InlineKeyboardButton(
                    text=f"{prize.emoji} {prize.title} ({prize.referral_code}){level_text}",
                    callback_data=f"edit_admin_prize_{prize.id}"
                )
            ])
        if len(blogger_prizes) > 10:
            text += f"... и еще {len(blogger_prizes) - 10} призов\n"
    
    keyboard.append([InlineKeyboardButton(text="⬅️ Назад", callback_data="back_to_admin_menu")])
    
    await callback.message.edit_text(text, reply_markup=InlineKeyboardMarkup(inline_keyboard=keyboard))

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
            text += f"• {prize.emoji} <b>{prize.title}</b> (ID: {prize.id}) - {get_achievement_description(prize.achievement_type, prize.achievement_value, prize.custom_condition)}\n"
    else:
        text += "   Нет активных призов\n"

    text += f"\n📣 <b>Призы блогеров ({len(blogger_prizes)}):</b>\n"
    if blogger_prizes:
        for prize in blogger_prizes:
            text += f"• {prize.emoji} <b>{prize.title}</b> (ID: {prize.id}, Код: {prize.referral_code}) - {get_achievement_description(prize.achievement_type, prize.achievement_value, prize.custom_condition)}\n"
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
    await show_admin_moderators_menu(callback.from_user.id, callback)

@dp.callback_query(lambda c: c.data == "back_to_bloggers")
async def handle_back_to_bloggers(callback: CallbackQuery):
    """Возврат к управлению блогерами"""
    await callback.answer()
    await show_admin_bloggers_menu(callback.from_user.id, callback)

# Обработчики отмены для управления персоналом
@dp.callback_query(lambda c: c.data == "cancel_add_moderator")
async def handle_cancel_add_moderator(callback: CallbackQuery, state: FSMContext):
    """Отмена добавления модератора"""
    await callback.answer()
    await callback.message.edit_text("❌ Добавление модератора отменено.")
    await state.clear()
    # Возвращаемся к управлению модераторами
    await show_admin_moderators_menu(callback.from_user.id, callback)

@dp.callback_query(lambda c: c.data == "cancel_add_blogger")
async def handle_cancel_add_blogger(callback: CallbackQuery, state: FSMContext):
    """Отмена добавления блогера"""
    await callback.answer()
    await callback.message.edit_text("❌ Добавление блогера отменено.")
    await state.clear()
    # Возвращаемся к управлению блогерами
    await show_admin_bloggers_menu(callback.from_user.id, callback)

# Обработчики для выдачи подписки
@dp.message(F.text == "💎 Выдать подписку")
async def handle_grant_subscription(message: Message, state: FSMContext):
    """Обработка выдачи подписки пользователю"""
    user_id = message.from_user.id
    
    # Проверяем, что это главный модератор
    role = await get_user_role(user_id)
    if role != ModeratorRole.ADMIN:
        await message.answer("❌ У вас нет доступа к этой функции.")
        return
    
    await state.set_state(SubscriptionGrantStates.waiting_for_user_id)
    await message.answer(
        "💎 <b>Выдача подписки пользователю</b>\n\n"
        "Введите Telegram ID пользователя, которому хотите выдать подписку:",
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="❌ Отмена", callback_data="cancel_grant_subscription")]
        ])
    )

@dp.message(SubscriptionGrantStates.waiting_for_user_id)
async def handle_subscription_user_id_input(message: Message, state: FSMContext):
    """Обработка ввода Telegram ID для выдачи подписки"""
    try:
        target_user_id = int(message.text.strip())
        
        # Проверяем, существует ли пользователь
        user = await db.get_user(target_user_id)
        if not user:
            await message.answer(
                f"❌ Пользователь с ID {target_user_id} не найден в базе данных.\n\n"
                "Попробуйте еще раз или отмените операцию:",
                reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                    [InlineKeyboardButton(text="❌ Отмена", callback_data="cancel_grant_subscription")]
                ])
            )
            return
        
        # Сохраняем ID пользователя в состоянии
        await state.update_data(target_user_id=target_user_id)
        await state.set_state(SubscriptionGrantStates.waiting_for_level_selection)
        
        # Показываем информацию о пользователе и выбор уровня подписки
        user_info = (
            f"👤 <b>Пользователь:</b> {user.name or 'Без имени'}\n"
            f"🆔 <b>Telegram ID:</b> {target_user_id}\n"
            f"🏙️ <b>Город:</b> {user.city or 'Не указан'}\n"
            f"💎 <b>Текущая подписка:</b> {'Активна' if user.subscription_active else 'Не активна'}\n\n"
        )
        
        if user.subscription_active and user.subscription_end:
            end_date = datetime.datetime.fromtimestamp(user.subscription_end).strftime('%d.%m.%Y')
            user_info += f"📅 <b>Истекает:</b> {end_date}\n\n"
        
        user_info += "Выберите уровень подписки для выдачи:"
        
        # Создаем клавиатуру с уровнями подписки
        keyboard = []
        for level in SUBSCRIPTION_LEVELS:
            keyboard.append([
                InlineKeyboardButton(
                    text=f"{level['name']} - {level['description']} ({level['price']} ₽)",
                    callback_data=f"grant_sub_level_{level['level'] - 1}"
                )
            ])
        keyboard.append([InlineKeyboardButton(text="❌ Отмена", callback_data="cancel_grant_subscription")])
        
        await message.answer(
            user_info,
            parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=keyboard)
        )
        
    except ValueError:
        await message.answer(
            "❌ Неверный формат Telegram ID. Введите числовое значение:\n\n"
            "Пример: 123456789",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="❌ Отмена", callback_data="cancel_grant_subscription")]
            ])
        )

@dp.callback_query(SubscriptionGrantStates.waiting_for_level_selection, lambda c: c.data.startswith("grant_sub_level_"))
async def handle_subscription_level_selection(callback: CallbackQuery, state: FSMContext):
    """Обработка выбора уровня подписки для выдачи"""
    await callback.answer()
    
    # Получаем индекс уровня из callback_data
    level_index = int(callback.data.replace("grant_sub_level_", ""))
    
    if level_index < 0 or level_index >= len(SUBSCRIPTION_LEVELS):
        await callback.answer("Неверный уровень", show_alert=True)
        return
    
    level = SUBSCRIPTION_LEVELS[level_index]
    data = await state.get_data()
    target_user_id = data.get('target_user_id')
    
    if not target_user_id:
        await callback.message.answer("❌ Ошибка: не найден ID пользователя. Начните заново.")
        await state.clear()
        return
    
    # Получаем информацию о пользователе
    user = await db.get_user(target_user_id)
    if not user:
        await callback.message.answer("❌ Пользователь не найден.")
        await state.clear()
        return
    
    # Сохраняем выбранный уровень
    await state.update_data(selected_level_index=level_index)
    await state.set_state(SubscriptionGrantStates.confirming_subscription)
    
    # Вычисляем даты подписки
    current_time = int(datetime.datetime.now().timestamp())
    subscription_start = current_time
    
    # Если есть активная подписка, суммируем время
    if user.subscription_active and user.subscription_end and user.subscription_end > current_time:
        remaining_time = user.subscription_end - current_time
        new_subscription_duration = level['months'] * 30 * 24 * 60 * 60  # в секундах
        subscription_end = subscription_start + new_subscription_duration + remaining_time
        action_text = "продлена"
    else:
        new_subscription_duration = level['months'] * 30 * 24 * 60 * 60  # в секундах
        subscription_end = subscription_start + new_subscription_duration
        action_text = "выдана"
    
    end_date = datetime.datetime.fromtimestamp(subscription_end).strftime('%d.%m.%Y')
    
    # Сохраняем данные для подтверждения
    await state.update_data(
        subscription_start=subscription_start,
        subscription_end=subscription_end,
        months=level['months'],
        level_name=level['name'],
        subscription_level=level['level']  # Сохраняем уровень подписки
    )
    
    # Показываем информацию для подтверждения
    confirmation_text = (
        f"💎 <b>Подтверждение выдачи подписки</b>\n\n"
        f"👤 <b>Пользователь:</b> {user.name or 'Без имени'}\n"
        f"🆔 <b>Telegram ID:</b> {target_user_id}\n\n"
        f"📦 <b>Уровень подписки:</b> {level['name']}\n"
        f"⏱ <b>Период:</b> {level['description']}\n"
        f"💰 <b>Стоимость:</b> {level['price']} ₽\n\n"
        f"📅 <b>Дата окончания:</b> {end_date}\n\n"
        f"Подписка будет {action_text} пользователю."
    )
    
    await callback.message.edit_text(
        confirmation_text,
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="✅ Подтвердить", callback_data="confirm_grant_subscription")],
            [InlineKeyboardButton(text="❌ Отмена", callback_data="cancel_grant_subscription")]
        ])
    )

@dp.callback_query(lambda c: c.data == "confirm_grant_subscription")
async def handle_confirm_grant_subscription(callback: CallbackQuery, state: FSMContext):
    """Подтверждение выдачи подписки"""
    await callback.answer()
    
    data = await state.get_data()
    target_user_id = data.get('target_user_id')
    subscription_start = data.get('subscription_start')
    subscription_end = data.get('subscription_end')
    months = data.get('months')
    level_name = data.get('level_name')
    
    if not all([target_user_id, subscription_start, subscription_end, months]):
        await callback.message.answer("❌ Ошибка: неполные данные. Начните заново.")
        await state.clear()
        return
    
    try:
        # Получаем уровень подписки из данных состояния
        subscription_level = data.get('subscription_level', 1)
        
        # Создаем запись о подписке
        subscription = Subscription(
            user_id=target_user_id,
            payment_id=None,  # Нет платежа, так как выдано администратором
            start_date=subscription_start,
            end_date=subscription_end,
            months=months,
            subscription_level=subscription_level,
            status=SubscriptionStatus.ACTIVE,
            auto_renew=False,
            created_at=subscription_start,
            updated_at=subscription_start
        )
        
        subscription_id = await db.save_subscription(subscription)
        
        # Активируем подписку пользователя
        await db.activate_user_subscription(target_user_id, subscription_start, subscription_end)
        
        # Получаем информацию о пользователе для уведомления
        user = await db.get_user(target_user_id)
        user_name = user.name if user else f"Пользователь {target_user_id}"
        
        end_date_str = datetime.datetime.fromtimestamp(subscription_end).strftime('%d.%m.%Y')
        
        await callback.message.edit_text(
            f"✅ <b>Подписка успешно выдана!</b>\n\n"
            f"👤 <b>Пользователь:</b> {user_name}\n"
            f"🆔 <b>Telegram ID:</b> {target_user_id}\n"
            f"📦 <b>Уровень:</b> {level_name}\n"
            f"⏱ <b>Период:</b> {months} месяцев\n"
            f"📅 <b>Дата окончания:</b> {end_date_str}\n\n"
            f"Подписка активирована.",
            parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="⬅️ Назад в меню", callback_data="back_to_admin_menu")]
            ])
        )
        
        logger.info(f"Администратор {callback.from_user.id} выдал подписку уровня '{level_name}' пользователю {target_user_id}")
        
        # Уведомляем пользователя о выдаче подписки через основной бот
        try:
            import os
            from dotenv import load_dotenv
            load_dotenv()
            main_bot_token = os.getenv("BOT_TOKEN")
            if main_bot_token:
                from aiogram import Bot as UserBot
                user_bot = UserBot(token=main_bot_token, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
                await user_bot.send_message(
                    target_user_id,
                    f"🎉 <b>Вам выдана подписка!</b>\n\n"
                    f"📦 <b>Уровень:</b> {level_name}\n"
                    f"⏱ <b>Период:</b> {months} месяцев\n"
                    f"📅 <b>Дата окончания:</b> {end_date_str}\n\n"
                    f"🚀 Теперь вы можете пользоваться всеми функциями бота!",
                    parse_mode="HTML"
                )
                await user_bot.session.close()
        except Exception as e:
            logger.error(f"Не удалось отправить уведомление пользователю {target_user_id}: {e}")
        
        await state.clear()
        
    except Exception as e:
        logger.error(f"Ошибка при выдаче подписки: {e}")
        await callback.message.answer(
            f"❌ Ошибка при выдаче подписки: {e}\n\n"
            "Попробуйте еще раз.",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="⬅️ Назад в меню", callback_data="back_to_admin_menu")]
            ])
        )
        await state.clear()

@dp.callback_query(lambda c: c.data == "cancel_grant_subscription")
async def handle_cancel_grant_subscription(callback: CallbackQuery, state: FSMContext):
    """Отмена выдачи подписки"""
    await callback.answer()
    await callback.message.edit_text("❌ Выдача подписки отменена.")
    await state.clear()
    # Возвращаемся в главное меню админа
    await callback.message.answer(
        "💎 Выдача подписки отменена.\n\n"
        "Используйте меню для продолжения работы.",
        reply_markup=create_admin_keyboard()
    )

async def main():
    """Главная функция запуска бота"""
    # Инициализация базы данных
    await db.init_db()

    logger.info("Модераторский бот запущен")

    # Запуск бота
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
