import aiosqlite
import logging
from datetime import date
from typing import Optional
from models import User

logger = logging.getLogger(__name__)

class Database:
    def __init__(self, db_path: str = "bot_database.db"):
        self.db_path = db_path

    async def init_db(self):
        """Инициализация базы данных и создание таблиц"""
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute('''
                CREATE TABLE IF NOT EXISTS users (
                    telegram_id INTEGER PRIMARY KEY,
                    language TEXT,
                    name TEXT,
                    birth_date TEXT,
                    height REAL,
                    weight REAL,
                    city TEXT,
                    referral_code TEXT,
                    goal TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')

            # Добавляем недостающие колонки (для существующих баз данных)
            try:
                await db.execute('ALTER TABLE users ADD COLUMN language TEXT')
                logger.info("Колонка language добавлена в таблицу")
            except aiosqlite.OperationalError:
                # Колонка уже существует
                pass

            try:
                await db.execute('ALTER TABLE users ADD COLUMN referral_code TEXT')
                logger.info("Колонка referral_code добавлена в таблицу")
            except aiosqlite.OperationalError:
                # Колонка уже существует
                pass

            try:
                await db.execute('ALTER TABLE users ADD COLUMN goal TEXT')
                logger.info("Колонка goal добавлена в таблицу")
            except aiosqlite.OperationalError:
                # Колонка уже существует
                pass

            await db.commit()
            logger.info("База данных инициализирована")

    async def get_user(self, telegram_id: int) -> Optional[User]:
        """Получение пользователя по telegram_id"""
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute(
                "SELECT * FROM users WHERE telegram_id = ?",
                (telegram_id,)
            )
            row = await cursor.fetchone()

            if row:
                # Преобразование строки даты в объект date
                birth_date = None
                if row['birth_date']:
                    try:
                        birth_date = date.fromisoformat(row['birth_date'])
                    except ValueError:
                        logger.warning(f"Неверный формат даты для пользователя {telegram_id}")

                return User(
                    telegram_id=row['telegram_id'],
                    language=row['language'],
                    name=row['name'],
                    birth_date=birth_date,
                    height=row['height'],
                    weight=row['weight'],
                    city=row['city'],
                    referral_code=row['referral_code'],
                    goal=row['goal']
                )
            return None

    async def save_user(self, user: User):
        """Сохранение или обновление пользователя"""
        async with aiosqlite.connect(self.db_path) as db:
            # Преобразование даты в строку для хранения
            birth_date_str = user.birth_date.isoformat() if user.birth_date else None

            await db.execute('''
                INSERT INTO users (telegram_id, language, name, birth_date, height, weight, city, referral_code, goal, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
                ON CONFLICT(telegram_id) DO UPDATE SET
                    language = excluded.language,
                    name = excluded.name,
                    birth_date = excluded.birth_date,
                    height = excluded.height,
                    weight = excluded.weight,
                    city = excluded.city,
                    referral_code = excluded.referral_code,
                    goal = excluded.goal,
                    updated_at = CURRENT_TIMESTAMP
            ''', (
                user.telegram_id,
                user.language,
                user.name,
                birth_date_str,
                user.height,
                user.weight,
                user.city,
                user.referral_code,
                user.goal
            ))
            await db.commit()
            logger.info(f"Пользователь {user.telegram_id} сохранен")

    async def update_user_field(self, telegram_id: int, field: str, value):
        """Обновление конкретного поля пользователя"""
        async with aiosqlite.connect(self.db_path) as db:
            # Преобразование значения в зависимости от типа
            if field == 'birth_date' and isinstance(value, date):
                value = value.isoformat()

            await db.execute(f'''
                UPDATE users
                SET {field} = ?, updated_at = CURRENT_TIMESTAMP
                WHERE telegram_id = ?
            ''', (value, telegram_id))
            await db.commit()
            logger.info(f"Поле {field} пользователя {telegram_id} обновлено")

    async def get_all_users(self) -> list[User]:
        """Получение всех пользователей"""
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute("SELECT * FROM users ORDER BY created_at DESC")
            rows = await cursor.fetchall()

            users = []
            for row in rows:
                birth_date = None
                if row['birth_date']:
                    try:
                        birth_date = date.fromisoformat(row['birth_date'])
                    except ValueError:
                        logger.warning(f"Неверный формат даты для пользователя {row['telegram_id']}")

                users.append(User(
                    telegram_id=row['telegram_id'],
                    language=row['language'],
                    name=row['name'],
                    birth_date=birth_date,
                    height=row['height'],
                    weight=row['weight'],
                    city=row['city'],
                    referral_code=row['referral_code'],
                    goal=row['goal']
                ))
            return users
