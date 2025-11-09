import asyncio
import logging
import aiohttp
from datetime import date
from typing import Optional

from aiogram import Bot, Dispatcher, Router, F
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.filters import Command, CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import Message, ReplyKeyboardMarkup, KeyboardButton, ReplyKeyboardRemove, InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery

from config import BOT_TOKEN
from database import Database
from models import User
from openrouter_config import OPENROUTER_API_KEY, OPENROUTER_BASE_URL, DEFAULT_MODEL, SYSTEM_PROMPT

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
        async with aiohttp.ClientSession() as session:
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
            f"{goal_text}\n"
            f"Готов продолжить путь к целям? Используй /update для обновления данных."
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

    if len(goal) < 3:
        await message.answer(
            "Пожалуйста, опишите вашу цель более подробно (минимум 3 символа):"
        )
        return

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

    if action == "goal_confirm":
        # Пользователь подтвердил цель - завершаем регистрацию
        await finalize_registration(callback.message, state)

    elif action == "goal_improve":
        # Улучшаем цель с помощью ИИ
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
        await state.set_state(UserRegistration.waiting_for_goal)
        await callback.message.edit_text(
            "🎯 Хорошо, давайте переформулируем цель.\n\n"
            "Расскажите о вашей главной цели:",
            reply_markup=None
        )

async def finalize_registration(message: Message, state: FSMContext):
    """Завершение регистрации пользователя"""
    data = await state.get_data()

    # Сохраняем данные в базу
    telegram_id = message.from_user.id
    user = await db.get_user(telegram_id)
    if user:
        user.goal = data.get('goal')
        await db.save_user(user)

    # Получаем все данные для финального сообщения
    name = data.get('name', 'Пользователь')
    language = data.get('language', 'ru')
    referral_code = data.get('referral_code')

    # Очищаем состояние
    await state.clear()

    referral_text = f"📢 Реферальный код: {referral_code}\n" if referral_code else ""

    await message.edit_text(
        f"🎉 Регистрация завершена! Добро пожаловать в команду изменений!\n\n"
        f"🌐 Язык: {get_language_emoji(language)}\n"
        f"👤 Имя: {name}\n"
        f"📅 Дата рождения: {data.get('birth_date').strftime('%d.%m.%Y') if data.get('birth_date') else 'Не указана'}\n"
        f"📏 Рост: {data.get('height')} см\n"
        f"⚖️ Вес: {data.get('weight')} кг\n"
        f"🏙️ Город: {data.get('city')}\n"
        f"{referral_text}"
        f"🎯 Цель: {data.get('goal')}\n\n"
        f"🚀 Теперь я буду помогать тебе достигать своей цели! "
        f"Каждый день я буду предлагать персональные задания. Используй /help для получения дополнительной информации.",
        reply_markup=None
    )

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

async def on_startup():
    """Функция, выполняемая при запуске бота"""
    await db.init_db()
    logger.info("Бот запущен и готов к работе")

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
