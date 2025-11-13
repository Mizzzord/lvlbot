import aiosqlite
import asyncpg
import datetime
import logging
import os
from datetime import date
from typing import Optional
from models import User, Payment, PaymentStatus, Subscription, SubscriptionStatus, PlayerStats, Rank, DailyTask, UserStats, TaskStatus, Prize, PrizeType
from rank_config import get_rank_by_experience
from postgres_config import get_postgres_connection_string, validate_postgres_config

logger = logging.getLogger(__name__)

class Database:
    def __init__(self, db_path: str = "bot_database.db", use_postgres: bool = False):
        self.db_path = db_path
        self.use_postgres = use_postgres

        if self.use_postgres:
            # Проверяем конфигурацию PostgreSQL только если используется PostgreSQL
            try:
                validate_postgres_config()
                logger.info("Используется PostgreSQL база данных")
            except Exception as e:
                logger.error(f"Ошибка конфигурации PostgreSQL: {e}")
                raise
        else:
            logger.info("Используется SQLite база данных")

    async def init_db(self):
        """Инициализация базы данных и создание таблиц"""
        if self.use_postgres:
            await self._init_postgres_db()
        else:
            await self._init_sqlite_db()

    async def _init_sqlite_db(self):
        """Инициализация SQLite базы данных"""
        async with aiosqlite.connect(self.db_path) as db:
            # Создаем таблицу пользователей
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
                    subscription_active BOOLEAN DEFAULT FALSE,
                    subscription_start INTEGER,
                    subscription_end INTEGER,
                    referral_count INTEGER DEFAULT 0,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')

            # Создаем таблицу платежей с расширенными полями
            await db.execute('''
                CREATE TABLE IF NOT EXISTS payments (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER,
                    payment_id TEXT,
                    order_id TEXT UNIQUE,
                    amount REAL,
                    months INTEGER,
                    status TEXT DEFAULT 'pending',
                    created_at INTEGER,
                    paid_at INTEGER,
                    currency TEXT DEFAULT 'RUB',
                    payment_method TEXT DEFAULT 'WATA',
                    discount_code TEXT,
                    referral_used TEXT,
                    subscription_type TEXT DEFAULT 'standard',
                    FOREIGN KEY (user_id) REFERENCES users (telegram_id)
                )
            ''')

            # Создаем таблицу подписок
            await db.execute('''
                CREATE TABLE IF NOT EXISTS subscriptions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER,
                    payment_id INTEGER,
                    start_date INTEGER,
                    end_date INTEGER,
                    months INTEGER,
                    subscription_level INTEGER DEFAULT 1,
                    status TEXT DEFAULT 'pending',
                    auto_renew BOOLEAN DEFAULT FALSE,
                    created_at INTEGER,
                    updated_at INTEGER,
                    FOREIGN KEY (user_id) REFERENCES users (telegram_id),
                    FOREIGN KEY (payment_id) REFERENCES payments (id)
                )
            ''')
            
            # Добавляем колонку subscription_level если её нет (миграция для существующих БД)
            try:
                cursor = await db.execute("PRAGMA table_info(subscriptions)")
                columns = [row[1] for row in await cursor.fetchall()]
                if 'subscription_level' not in columns:
                    await db.execute('ALTER TABLE subscriptions ADD COLUMN subscription_level INTEGER DEFAULT 1')
                    await db.commit()
                    logger.info("Добавлена колонка subscription_level в таблицу subscriptions")
            except Exception as e:
                logger.warning(f"Не удалось добавить колонку subscription_level: {e}")

            # Создаем таблицу статов игрока
            await db.execute('''
                CREATE TABLE IF NOT EXISTS player_stats (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER UNIQUE,
                    nickname TEXT,
                    experience INTEGER DEFAULT 0,
                    strength INTEGER DEFAULT 50,
                    agility INTEGER DEFAULT 50,
                    endurance INTEGER DEFAULT 50,
                    intelligence INTEGER DEFAULT 50,
                    charisma INTEGER DEFAULT 50,
                    photo_path TEXT,
                    card_image_path TEXT,
                    created_at INTEGER,
                    updated_at INTEGER,
                    FOREIGN KEY (user_id) REFERENCES users (telegram_id)
                )
            ''')

            # Создаем таблицу ежедневных заданий
            await db.execute('''
                CREATE TABLE IF NOT EXISTS daily_tasks (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER,
                    task_description TEXT,
                    created_at INTEGER,
                    expires_at INTEGER,
                    status TEXT DEFAULT 'pending',
                    completed_at INTEGER,
                    submitted_media_path TEXT,
                    moderator_comment TEXT,
                    FOREIGN KEY (user_id) REFERENCES users (telegram_id)
                )
            ''')

            # Создаем таблицу пользовательских статистик
            await db.execute('''
                CREATE TABLE IF NOT EXISTS user_stats (
                    user_id INTEGER PRIMARY KEY,
                    level INTEGER DEFAULT 1,
                    experience INTEGER DEFAULT 0,
                    rank TEXT DEFAULT 'F',
                    current_streak INTEGER DEFAULT 0,
                    best_streak INTEGER DEFAULT 0,
                    total_tasks_completed INTEGER DEFAULT 0,
                    last_task_date INTEGER,
                    FOREIGN KEY (user_id) REFERENCES users (telegram_id)
                )
            ''')

            # Создаем таблицу призов
            await db.execute('''
                CREATE TABLE IF NOT EXISTS prizes (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    prize_type TEXT NOT NULL,
                    referral_code TEXT,
                    title TEXT NOT NULL,
                    description TEXT,
                    achievement_type TEXT NOT NULL,
                    achievement_value INTEGER NOT NULL,
                    custom_condition TEXT,
                    emoji TEXT DEFAULT '🎁',
                    is_active BOOLEAN DEFAULT TRUE,
                    created_at INTEGER NOT NULL,
                    updated_at INTEGER NOT NULL
                )
            ''')

            # Создаем таблицу уведомлений
            await db.execute('''
                CREATE TABLE IF NOT EXISTS notifications (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER NOT NULL,
                    type TEXT NOT NULL, -- 'task_approved', 'task_rejected', 'payment_confirmed' и т.д.
                    title TEXT NOT NULL,
                    message TEXT NOT NULL,
                    data TEXT, -- JSON с дополнительными данными
                    is_sent BOOLEAN DEFAULT FALSE,
                    created_at INTEGER NOT NULL,
                    sent_at INTEGER
                )
            ''')

            # Индекс для быстрого поиска неотправленных уведомлений
            await db.execute('''
                CREATE INDEX IF NOT EXISTS idx_notifications_unsent
                ON notifications(user_id, is_sent)
            ''')

            # Создаем таблицу модераторов
            await db.execute('''
                CREATE TABLE IF NOT EXISTS moderators (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    telegram_id INTEGER UNIQUE NOT NULL,
                    username TEXT,
                    full_name TEXT,
                    role TEXT DEFAULT 'moderator',
                    is_active BOOLEAN DEFAULT TRUE,
                    created_at INTEGER NOT NULL,
                    updated_at INTEGER NOT NULL
                )
            ''')

            # Создаем таблицу блогеров
            await db.execute('''
                CREATE TABLE IF NOT EXISTS bloggers (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    telegram_id INTEGER UNIQUE NOT NULL,
                    username TEXT,
                    full_name TEXT,
                    referral_code TEXT UNIQUE NOT NULL,
                    is_active BOOLEAN DEFAULT TRUE,
                    created_at INTEGER NOT NULL,
                    updated_at INTEGER NOT NULL
                )
            ''')

            # Создаем индексы для производительности
            await db.execute('CREATE INDEX IF NOT EXISTS idx_payments_user_id ON payments(user_id)')
            await db.execute('CREATE INDEX IF NOT EXISTS idx_payments_status ON payments(status)')
            await db.execute('CREATE INDEX IF NOT EXISTS idx_subscriptions_user_id ON subscriptions(user_id)')
            await db.execute('CREATE INDEX IF NOT EXISTS idx_subscriptions_status ON subscriptions(status)')
            await db.execute('CREATE INDEX IF NOT EXISTS idx_player_stats_user_id ON player_stats(user_id)')
            await db.execute('CREATE INDEX IF NOT EXISTS idx_daily_tasks_user_id ON daily_tasks(user_id)')
            await db.execute('CREATE INDEX IF NOT EXISTS idx_daily_tasks_expires_at ON daily_tasks(expires_at)')
            await db.execute('CREATE INDEX IF NOT EXISTS idx_user_stats_rank ON user_stats(rank)')
            await db.execute('CREATE INDEX IF NOT EXISTS idx_prizes_type ON prizes(prize_type)')
            await db.execute('CREATE INDEX IF NOT EXISTS idx_prizes_referral_code ON prizes(referral_code)')
            await db.execute('CREATE INDEX IF NOT EXISTS idx_moderators_telegram_id ON moderators(telegram_id)')
            await db.execute('CREATE INDEX IF NOT EXISTS idx_bloggers_telegram_id ON bloggers(telegram_id)')
            await db.execute('CREATE INDEX IF NOT EXISTS idx_bloggers_referral_code ON bloggers(referral_code)')

            # Добавляем недостающие колонки для существующих баз данных
            await self._add_missing_columns(db)

            # Инициализируем стандартные призы
            await self._init_default_prizes(db)

            await db.commit()
            logger.info("SQLite база данных инициализирована")

    async def _init_postgres_db(self):
        """Инициализация PostgreSQL базы данных"""
        conn_string = get_postgres_connection_string()
        conn = await asyncpg.connect(conn_string)

        try:
            # Создаем таблицу пользователей
            await conn.execute('''
                CREATE TABLE IF NOT EXISTS users (
                    telegram_id BIGINT PRIMARY KEY,
                    language TEXT,
                    name TEXT,
                    birth_date TEXT,
                    height REAL,
                    weight REAL,
                    city TEXT,
                    referral_code TEXT,
                    goal TEXT,
                    subscription_active BOOLEAN DEFAULT FALSE,
                    subscription_start BIGINT,
                    subscription_end BIGINT,
                    referral_count INTEGER DEFAULT 0,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')

            # Создаем таблицу платежей
            await conn.execute('''
                CREATE TABLE IF NOT EXISTS payments (
                    id SERIAL PRIMARY KEY,
                    user_id BIGINT,
                    payment_id TEXT,
                    order_id TEXT UNIQUE,
                    amount REAL,
                    months INTEGER,
                    status TEXT DEFAULT 'pending',
                    created_at BIGINT,
                    updated_at BIGINT,
                    payment_data TEXT,
                    FOREIGN KEY (user_id) REFERENCES users(telegram_id)
                )
            ''')

            # Создаем таблицу подписок
            await conn.execute('''
                CREATE TABLE IF NOT EXISTS subscriptions (
                    id SERIAL PRIMARY KEY,
                    user_id BIGINT,
                    payment_id TEXT,
                    months INTEGER,
                    start_date BIGINT,
                    end_date BIGINT,
                    status TEXT DEFAULT 'active',
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (user_id) REFERENCES users(telegram_id)
                )
            ''')

            # Создаем таблицу статистики игрока
            await conn.execute('''
                CREATE TABLE IF NOT EXISTS player_stats (
                    id SERIAL PRIMARY KEY,
                    user_id BIGINT UNIQUE,
                    nickname TEXT,
                    strength INTEGER DEFAULT 50,
                    agility INTEGER DEFAULT 50,
                    endurance INTEGER DEFAULT 50,
                    intelligence INTEGER DEFAULT 50,
                    charisma INTEGER DEFAULT 50,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (user_id) REFERENCES users(telegram_id) ON DELETE CASCADE
                )
            ''')

            # Создаем таблицу статистики пользователя
            await conn.execute('''
                CREATE TABLE IF NOT EXISTS user_stats (
                    id SERIAL PRIMARY KEY,
                    user_id BIGINT UNIQUE,
                    level INTEGER DEFAULT 1,
                    experience INTEGER DEFAULT 0,
                    rank TEXT DEFAULT 'F',
                    current_streak INTEGER DEFAULT 0,
                    best_streak INTEGER DEFAULT 0,
                    total_tasks_completed INTEGER DEFAULT 0,
                    last_task_date DATE,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (user_id) REFERENCES users(telegram_id) ON DELETE CASCADE
                )
            ''')

            # Создаем таблицу ежедневных заданий
            await conn.execute('''
                CREATE TABLE IF NOT EXISTS daily_tasks (
                    id SERIAL PRIMARY KEY,
                    user_id BIGINT,
                    task TEXT,
                    status TEXT DEFAULT 'active',
                    created_at DATE DEFAULT CURRENT_DATE,
                    completed_at TIMESTAMP,
                    FOREIGN KEY (user_id) REFERENCES users(telegram_id) ON DELETE CASCADE
                )
            ''')

            # Создаем таблицу призов
            await conn.execute('''
                CREATE TABLE IF NOT EXISTS prizes (
                    id SERIAL PRIMARY KEY,
                    prize_type TEXT,
                    title TEXT,
                    description TEXT,
                    referral_code TEXT,
                    is_active BOOLEAN DEFAULT TRUE,
                    created_by BIGINT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')

            # Инициализируем стандартные призы
            await self._init_default_prizes_postgres(conn)

            logger.info("PostgreSQL база данных инициализирована")

        finally:
            await conn.close()

    async def _execute_sqlite(self, query: str, *args):
        """Выполнение запроса к SQLite"""
        if self.use_postgres:
            raise Exception("Этот метод доступен только для SQLite")

        async with aiosqlite.connect(self.db_path) as conn:
            if query.strip().upper().startswith('SELECT'):
                cursor = await conn.execute(query, args)
                result = await cursor.fetchall()
                return result
            else:
                await conn.execute(query, args if args else ())
                await conn.commit()
                return None

    async def _execute_postgres(self, query: str, *args):
        """Выполнение запроса к PostgreSQL"""
        if not self.use_postgres:
            raise Exception("Этот метод доступен только для PostgreSQL")

        conn_string = get_postgres_connection_string()
        conn = await asyncpg.connect(conn_string)

        try:
            if query.strip().upper().startswith('SELECT'):
                result = await conn.fetch(query, *args)
                return result
            else:
                result = await conn.execute(query, *args)
                return result
        finally:
            await conn.close()

    async def _init_default_prizes_postgres(self, conn):
        """Инициализация стандартных призов для PostgreSQL"""
        import time
        current_time = int(time.time())

        # Проверяем, есть ли уже призы
        count = await conn.fetchval('SELECT COUNT(*) FROM prizes')

        if count > 0:
            return  # Призы уже инициализированы

        # Стандартные призы от главного модератора
        default_prizes = [
            {
                'prize_type': PrizeType.ADMIN.value,
                'referral_code': None,
                'title': "Бронзовая медаль",
                'description': "За последовательность в достижении целей",
                'achievement_type': "streak",
                'achievement_value': 7,
                'emoji': "🥉",
                'is_active': True,
                'created_at': current_time,
                'updated_at': current_time
            },
            {
                'prize_type': PrizeType.ADMIN.value,
                'referral_code': None,
                'title': "Серебряная медаль",
                'description': "За настойчивость и дисциплину",
                'achievement_type': "streak",
                'achievement_value': 14,
                'emoji': "🥈",
                'is_active': True,
                'created_at': current_time,
                'updated_at': current_time
            },
            {
                'prize_type': PrizeType.ADMIN.value,
                'referral_code': None,
                'title': "Золотая медаль",
                'description': "За выдающуюся последовательность",
                'achievement_type': "streak",
                'achievement_value': 30,
                'emoji': "🥇",
                'is_active': True,
                'created_at': current_time,
                'updated_at': current_time
            },
            {
                'prize_type': PrizeType.ADMIN.value,
                'referral_code': None,
                'title': "Кристалл мотивации",
                'description': "За активное участие в программе",
                'achievement_type': "tasks",
                'achievement_value': 50,
                'emoji': "💎",
                'is_active': True,
                'created_at': current_time,
                'updated_at': current_time
            },
            {
                'prize_type': PrizeType.ADMIN.value,
                'referral_code': None,
                'title': "Почетная грамота",
                'description': "За достижение ранга специалиста",
                'achievement_type': "rank",
                'achievement_value': 4,
                'emoji': "🎖️",
                'is_active': True,
                'created_at': current_time,
                'updated_at': current_time
            },
            {
                'prize_type': PrizeType.ADMIN.value,
                'referral_code': None,
                'title': "Специальный значок",
                'description': "За достижение ранга профессионала",
                'achievement_type': "rank",
                'achievement_value': 5,
                'emoji': "🏅",
                'is_active': True,
                'created_at': current_time,
                'updated_at': current_time
            },
            {
                'prize_type': PrizeType.ADMIN.value,
                'referral_code': None,
                'title': "Корона чемпиона",
                'description': "За достижение ранга мастера",
                'achievement_type': "rank",
                'achievement_value': 6,
                'emoji': "👑",
                'is_active': True,
                'created_at': current_time,
                'updated_at': current_time
            },
            {
                'prize_type': PrizeType.ADMIN.value,
                'referral_code': None,
                'title': "Звезда легенды",
                'description': "За достижение высшего ранга",
                'achievement_type': "rank",
                'achievement_value': 7,
                'emoji': "🌟",
                'is_active': True,
                'created_at': current_time,
                'updated_at': current_time
            }
        ]

        # Добавляем призы в базу данных
        for prize in default_prizes:
            await conn.execute('''
                INSERT INTO prizes (prize_type, referral_code, title, description, achievement_type, achievement_value, emoji, is_active, created_at, updated_at)
                VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10)
            ''',
                prize['prize_type'],
                prize['referral_code'],
                prize['title'],
                prize['description'],
                prize['achievement_type'],
                prize['achievement_value'],
                prize['emoji'],
                prize['is_active'],
                prize['created_at'],
                prize['updated_at']
            )

    async def _add_missing_columns(self, db):
        """Добавляет недостающие колонки для совместимости с существующими базами данных"""
        # Поля для таблицы users
        user_columns = [
            ('language', 'TEXT'),
            ('referral_code', 'TEXT'),
            ('goal', 'TEXT'),
            ('subscription_active', 'BOOLEAN DEFAULT FALSE'),
            ('subscription_start', 'INTEGER'),
            ('subscription_end', 'INTEGER'),
            ('referral_count', 'INTEGER DEFAULT 0')
        ]

        for column_name, column_type in user_columns:
            try:
                await db.execute(f'ALTER TABLE users ADD COLUMN {column_name} {column_type}')
                logger.info(f"Колонка {column_name} добавлена в таблицу users")
            except aiosqlite.OperationalError:
                # Колонка уже существует
                pass

        # Поля для таблицы payments
        payment_columns = [
            ('currency', "TEXT DEFAULT 'RUB'"),
            ('payment_method', "TEXT DEFAULT 'WATA'"),
            ('discount_code', 'TEXT'),
            ('referral_used', 'TEXT'),
            ('subscription_type', "TEXT DEFAULT 'standard'")
        ]

        for column_name, column_type in payment_columns:
            try:
                await db.execute(f'ALTER TABLE payments ADD COLUMN {column_name} {column_type}')
                logger.info(f"Колонка {column_name} добавлена в таблицу payments")
            except aiosqlite.OperationalError:
                # Колонка уже существует
                pass

        # Поля для таблицы player_stats
        player_stats_columns = [
            ('nickname', 'TEXT'),
            ('experience', 'INTEGER DEFAULT 0'),
            ('intelligence', 'INTEGER DEFAULT 50'),
            ('charisma', 'INTEGER DEFAULT 50'),
            ('card_image_path', 'TEXT')
        ]

        for column_name, column_type in player_stats_columns:
            try:
                await db.execute(f'ALTER TABLE player_stats ADD COLUMN {column_name} {column_type}')
                logger.info(f"Колонка {column_name} добавлена в таблицу player_stats")
            except aiosqlite.OperationalError:
                # Колонка уже существует
                pass

        # Поля для таблицы daily_tasks
        daily_tasks_columns = [
            ('status', "TEXT DEFAULT 'pending'"),
            ('submitted_media_path', 'TEXT'),
            ('moderator_comment', 'TEXT')
        ]

        for column_name, column_type in daily_tasks_columns:
            try:
                await db.execute(f'ALTER TABLE daily_tasks ADD COLUMN {column_name} {column_type}')
                logger.info(f"Колонка {column_name} добавлена в таблицу daily_tasks")
            except aiosqlite.OperationalError:
                # Колонка уже существует
                pass

        # Поля для таблицы user_stats
        user_stats_columns = [
            ('referral_rank', 'TEXT')
        ]

        for column_name, column_type in user_stats_columns:
            try:
                await db.execute(f'ALTER TABLE user_stats ADD COLUMN {column_name} {column_type}')
                logger.info(f"Колонка {column_name} добавлена в таблицу user_stats")
            except aiosqlite.OperationalError:
                # Колонка уже существует
                pass

    async def _init_default_prizes(self, db):
        """Инициализация стандартных призов"""
        import time
        current_time = int(time.time())

        # Проверяем, есть ли уже призы
        cursor = await db.execute('SELECT COUNT(*) FROM prizes')
        count = (await cursor.fetchone())[0]

        if count > 0:
            return  # Призы уже инициализированы

        # Стандартные призы от главного модератора
        default_prizes = [
            Prize(
                prize_type=PrizeType.ADMIN,
                title="Бронзовая медаль",
                description="За последовательность в достижении целей",
                achievement_type="streak",
                achievement_value=7,
                emoji="🥉",
                is_active=True,
                created_at=current_time,
                updated_at=current_time
            ),
            Prize(
                prize_type=PrizeType.ADMIN,
                title="Серебряная медаль",
                description="За настойчивость и дисциплину",
                achievement_type="streak",
                achievement_value=14,
                emoji="🥈",
                is_active=True,
                created_at=current_time,
                updated_at=current_time
            ),
            Prize(
                prize_type=PrizeType.ADMIN,
                title="Золотая медаль",
                description="За выдающуюся последовательность",
                achievement_type="streak",
                achievement_value=30,
                emoji="🥇",
                is_active=True,
                created_at=current_time,
                updated_at=current_time
            ),
            Prize(
                prize_type=PrizeType.ADMIN,
                title="Кристалл мотивации",
                description="За активное участие в программе",
                achievement_type="tasks",
                achievement_value=50,
                emoji="💎",
                is_active=True,
                created_at=current_time,
                updated_at=current_time
            ),
            Prize(
                prize_type=PrizeType.ADMIN,
                title="Почетная грамота",
                description="За достижение ранга специалиста",
                achievement_type="rank",
                achievement_value=4,  # Ранг C (индекс 3 в списке, но значение 4 для отображения)
                emoji="🎖️",
                is_active=True,
                created_at=current_time,
                updated_at=current_time
            ),
            Prize(
                prize_type=PrizeType.ADMIN,
                title="Специальный значок",
                description="За достижение ранга профессионала",
                achievement_type="rank",
                achievement_value=5,  # Ранг B (индекс 4 в списке, но значение 5 для отображения)
                emoji="🏅",
                is_active=True,
                created_at=current_time,
                updated_at=current_time
            ),
            Prize(
                prize_type=PrizeType.ADMIN,
                title="Корона чемпиона",
                description="За достижение ранга мастера",
                achievement_type="rank",
                achievement_value=6,  # Ранг A (индекс 5 в списке, но значение 6 для отображения)
                emoji="👑",
                is_active=True,
                created_at=current_time,
                updated_at=current_time
            ),
            Prize(
                prize_type=PrizeType.ADMIN,
                title="Звезда легенды",
                description="За достижение высшего ранга",
                achievement_type="rank",
                achievement_value=7,  # Ранг S (индекс 6 в списке, но значение 7 для отображения)
                emoji="🌟",
                is_active=True,
                created_at=current_time,
                updated_at=current_time
            )
        ]

        # Добавляем призы в базу данных
        for prize in default_prizes:
            await db.execute('''
                INSERT INTO prizes (prize_type, referral_code, title, description, achievement_type, achievement_value, emoji, is_active, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                prize.prize_type.value,
                prize.referral_code,
                prize.title,
                prize.description,
                prize.achievement_type,
                prize.achievement_value,
                prize.emoji,
                prize.is_active,
                prize.created_at,
                prize.updated_at
            ))

        logger.info(f"Инициализировано {len(default_prizes)} стандартных призов")

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
                    goal=row['goal'],
                    subscription_active=bool(row['subscription_active']),
                    subscription_start=row['subscription_start'],
                    subscription_end=row['subscription_end'],
                    referral_count=row['referral_count']
                )
            return None

    async def save_user(self, user: User):
        """Сохранение или обновление пользователя"""
        async with aiosqlite.connect(self.db_path) as db:
            # Преобразование даты в строку для хранения
            birth_date_str = user.birth_date.isoformat() if user.birth_date else None

            await db.execute('''
                INSERT INTO users (telegram_id, language, name, birth_date, height, weight, city, referral_code, goal,
                                  subscription_active, subscription_start, subscription_end, referral_count, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
                ON CONFLICT(telegram_id) DO UPDATE SET
                    language = excluded.language,
                    name = excluded.name,
                    birth_date = excluded.birth_date,
                    height = excluded.height,
                    weight = excluded.weight,
                    city = excluded.city,
                    referral_code = excluded.referral_code,
                    goal = excluded.goal,
                    subscription_active = excluded.subscription_active,
                    subscription_start = excluded.subscription_start,
                    subscription_end = excluded.subscription_end,
                    referral_count = excluded.referral_count,
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
                user.goal,
                user.subscription_active,
                user.subscription_start,
                user.subscription_end,
                user.referral_count
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
                    goal=row['goal'],
                    subscription_active=bool(row['subscription_active']),
                    subscription_start=row['subscription_start'],
                    subscription_end=row['subscription_end'],
                    referral_count=row['referral_count']
                ))
            return users

    async def save_payment(self, payment: Payment) -> int:
        """Сохранение платежа в базу данных"""
        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute('''
                INSERT INTO payments (user_id, payment_id, order_id, amount, months, status, created_at, paid_at,
                                     currency, payment_method, discount_code, referral_used, subscription_type)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                payment.user_id,
                payment.payment_id,
                payment.order_id,
                payment.amount,
                payment.months,
                payment.status.value,
                payment.created_at,
                payment.paid_at,
                payment.currency,
                payment.payment_method,
                payment.discount_code,
                payment.referral_used,
                payment.subscription_type
            ))
            payment_id = cursor.lastrowid
            await db.commit()
            logger.info(f"Платеж {payment.order_id} сохранен")
            return payment_id

    async def get_payment_by_order_id(self, order_id: str) -> Optional[Payment]:
        """Получение платежа по order_id"""
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute(
                "SELECT * FROM payments WHERE order_id = ?",
                (order_id,)
            )
            row = await cursor.fetchone()

        if row:
            return Payment(
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
            return None

    async def get_pending_payments(self) -> list[Payment]:
        """Получение всех неоплаченных платежей"""
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute(
                "SELECT * FROM payments WHERE status = 'pending' ORDER BY created_at DESC"
            )
            rows = await cursor.fetchall()

            payments = []
            for row in rows:
                payments.append(Payment(
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
                ))
            return payments

    async def update_payment_status(self, payment_id: int, status: str, paid_at: Optional[int] = None):
        """Обновление статуса платежа"""
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute('''
                UPDATE payments
                SET status = ?, paid_at = ?
                WHERE id = ?
            ''', (status, paid_at, payment_id))
            await db.commit()
            logger.info(f"Статус платежа {payment_id} обновлен на {status}")

    # Методы для работы с подписками

    async def save_subscription(self, subscription: Subscription) -> int:
        """Сохранение подписки в базу данных"""
        async with aiosqlite.connect(self.db_path) as db:
            # Проверяем наличие колонки subscription_level
            cursor = await db.execute("PRAGMA table_info(subscriptions)")
            columns = [row[1] for row in await cursor.fetchall()]
            has_subscription_level = 'subscription_level' in columns
            
            if has_subscription_level:
                cursor = await db.execute('''
                    INSERT INTO subscriptions (user_id, payment_id, start_date, end_date, months, subscription_level, status,
                                              auto_renew, created_at, updated_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', (
                    subscription.user_id,
                    subscription.payment_id,
                    subscription.start_date,
                    subscription.end_date,
                    subscription.months,
                    subscription.subscription_level,
                    subscription.status.value,
                    subscription.auto_renew,
                    subscription.created_at,
                    subscription.updated_at
                ))
            else:
                # Fallback для старых версий БД
                cursor = await db.execute('''
                    INSERT INTO subscriptions (user_id, payment_id, start_date, end_date, months, status,
                                              auto_renew, created_at, updated_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', (
                    subscription.user_id,
                    subscription.payment_id,
                    subscription.start_date,
                    subscription.end_date,
                    subscription.months,
                    subscription.status.value,
                    subscription.auto_renew,
                    subscription.created_at,
                    subscription.updated_at
                ))
            subscription_id = cursor.lastrowid
            await db.commit()
            logger.info(f"Подписка {subscription_id} для пользователя {subscription.user_id} сохранена")
            return subscription_id

    async def get_active_subscription(self, user_id: int) -> Optional[Subscription]:
        """Получение активной подписки пользователя"""
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute('''
                SELECT * FROM subscriptions
                WHERE user_id = ? AND status = 'active' AND end_date > ?
                ORDER BY end_date DESC
                LIMIT 1
            ''', (user_id, int(datetime.datetime.now().timestamp())))

            row = await cursor.fetchone()
            if row:
                # Проверяем наличие колонки subscription_level
                subscription_level = 1  # По умолчанию
                try:
                    subscription_level = row['subscription_level'] if row['subscription_level'] else 1
                except (KeyError, IndexError):
                    # Колонка отсутствует в старых версиях БД, определяем по месяцам
                    months = row['months']
                    if months >= 12:
                        subscription_level = 3
                    elif months >= 3:
                        subscription_level = 2
                    else:
                        subscription_level = 1
                
                return Subscription(
                    id=row['id'],
                    user_id=row['user_id'],
                    payment_id=row['payment_id'],
                    start_date=row['start_date'],
                    end_date=row['end_date'],
                    months=row['months'],
                    subscription_level=subscription_level,
                    status=SubscriptionStatus(row['status']),
                    auto_renew=bool(row['auto_renew']),
                    created_at=row['created_at'],
                    updated_at=row['updated_at']
                )
            return None

    async def get_user_subscriptions(self, user_id: int) -> list[Subscription]:
        """Получение всех подписок пользователя"""
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute('''
                SELECT * FROM subscriptions
                WHERE user_id = ?
                ORDER BY created_at DESC
            ''', (user_id,))

            rows = await cursor.fetchall()
            subscriptions = []

            for row in rows:
                # Проверяем наличие колонки subscription_level
                subscription_level = 1  # По умолчанию
                try:
                    subscription_level = row['subscription_level'] if row['subscription_level'] else 1
                except (KeyError, IndexError):
                    # Колонка отсутствует в старых версиях БД, определяем по месяцам
                    months = row['months']
                    if months >= 12:
                        subscription_level = 3
                    elif months >= 3:
                        subscription_level = 2
                    else:
                        subscription_level = 1
                
                subscriptions.append(Subscription(
                    id=row['id'],
                    user_id=row['user_id'],
                    payment_id=row['payment_id'],
                    start_date=row['start_date'],
                    end_date=row['end_date'],
                    months=row['months'],
                    subscription_level=subscription_level,
                    status=SubscriptionStatus(row['status']),
                    auto_renew=bool(row['auto_renew']),
                    created_at=row['created_at'],
                    updated_at=row['updated_at']
                ))

            return subscriptions

    async def update_subscription_status(self, subscription_id: int, status: str):
        """Обновление статуса подписки"""
        async with aiosqlite.connect(self.db_path) as db:
            current_time = int(datetime.datetime.now().timestamp())
            await db.execute('''
                UPDATE subscriptions
                SET status = ?, updated_at = ?
                WHERE id = ?
            ''', (status, current_time, subscription_id))
            await db.commit()
            logger.info(f"Статус подписки {subscription_id} обновлен на {status}")

    async def activate_user_subscription(self, user_id: int, subscription_start: int, subscription_end: int):
        """Активация подписки пользователя"""
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute('''
                UPDATE users
                SET subscription_active = TRUE, subscription_start = ?, subscription_end = ?, updated_at = CURRENT_TIMESTAMP
                WHERE telegram_id = ?
            ''', (subscription_start, subscription_end, user_id))
            await db.commit()
            logger.info(f"Подписка пользователя {user_id} активирована")

    async def deactivate_user_subscription(self, user_id: int):
        """Деактивация подписки пользователя"""
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute('''
                UPDATE users
                SET subscription_active = FALSE, subscription_start = NULL, subscription_end = NULL, updated_at = CURRENT_TIMESTAMP
                WHERE telegram_id = ?
            ''', (user_id,))
            await db.commit()
            logger.info(f"Подписка пользователя {user_id} деактивирована")

    # Методы для работы со статами игрока

    async def save_player_stats(self, stats: PlayerStats) -> int:
        """Сохранение или обновление статов игрока"""
        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute('''
                INSERT INTO player_stats (user_id, nickname, experience, strength, agility, endurance, intelligence, charisma, photo_path, card_image_path, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(user_id) DO UPDATE SET
                    nickname = excluded.nickname,
                    experience = excluded.experience,
                    strength = excluded.strength,
                    agility = excluded.agility,
                    endurance = excluded.endurance,
                    intelligence = excluded.intelligence,
                    charisma = excluded.charisma,
                    photo_path = excluded.photo_path,
                    card_image_path = excluded.card_image_path,
                    updated_at = excluded.updated_at
            ''', (
                stats.user_id,
                stats.nickname,
                stats.experience,
                stats.strength,
                stats.agility,
                stats.endurance,
                stats.intelligence,
                stats.charisma,
                stats.photo_path,
                stats.card_image_path,
                stats.created_at,
                stats.updated_at
            ))
            stats_id = cursor.lastrowid or stats.id
            await db.commit()
            logger.info(f"Стати игрока для пользователя {stats.user_id} сохранены")
            return stats_id

    async def get_player_stats(self, user_id: int) -> Optional[PlayerStats]:
        """Получение статов игрока"""
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute('''
                SELECT * FROM player_stats WHERE user_id = ?
            ''', (user_id,))

            row = await cursor.fetchone()
            if row:
                return PlayerStats(
                    id=row['id'],
                    user_id=row['user_id'],
                    nickname=row['nickname'],
                    experience=row['experience'],
                    strength=row['strength'],
                    agility=row['agility'],
                    endurance=row['endurance'],
                    intelligence=row['intelligence'],
                    charisma=row['charisma'],
                    photo_path=row['photo_path'],
                    card_image_path=row['card_image_path'],
                    created_at=row['created_at'],
                    updated_at=row['updated_at']
                )
            return None

    # Методы для работы с ежедневными заданиями

    async def save_daily_task(self, task: DailyTask) -> int:
        """Сохранение ежедневного задания"""
        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute('''
                INSERT INTO daily_tasks (user_id, task_description, created_at, expires_at, status, completed_at, submitted_media_path, moderator_comment)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                task.user_id,
                task.task_description,
                task.created_at,
                task.expires_at,
                task.status.value,
                task.completed_at,
                task.submitted_media_path,
                task.moderator_comment
            ))
            task_id = cursor.lastrowid
            await db.commit()
            logger.info(f"Ежедневное задание для пользователя {task.user_id} сохранено")
            return task_id

    async def get_active_daily_task(self, user_id: int) -> Optional[DailyTask]:
        """Получение активного ежедневного задания пользователя (ожидающего выполнения)"""
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute('''
                SELECT * FROM daily_tasks
                WHERE user_id = ? AND status = 'pending' AND expires_at > ?
                ORDER BY created_at DESC
                LIMIT 1
            ''', (user_id, int(datetime.datetime.now().timestamp())))

            row = await cursor.fetchone()
            if row:
                return DailyTask(
                    id=row['id'],
                    user_id=row['user_id'],
                    task_description=row['task_description'],
                    created_at=row['created_at'],
                    expires_at=row['expires_at'],
                    status=TaskStatus(row['status']),
                    completed_at=row['completed_at'],
                    submitted_media_path=row['submitted_media_path'],
                    moderator_comment=row['moderator_comment']
                )
            return None

    async def submit_daily_task_media(self, task_id: int, media_path: str) -> bool:
        """Отправить медиафайл для задания на модерацию"""
        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute('''
                UPDATE daily_tasks
                SET status = 'submitted', submitted_media_path = ?
                WHERE id = ? AND status = 'pending'
            ''', (media_path, task_id))
            await db.commit()

            if cursor.rowcount > 0:
                logger.info(f"Медиафайл для задания {task_id} отправлен на модерацию")
                return True
            return False

    async def approve_daily_task(self, task_id: int, moderator_comment: str = None) -> bool:
        """Одобрить задание модератором"""
        async with aiosqlite.connect(self.db_path) as db:
            current_time = int(datetime.datetime.now().timestamp())
            cursor = await db.execute('''
                UPDATE daily_tasks
                SET status = 'approved', completed_at = ?, moderator_comment = ?
                WHERE id = ? AND status = 'submitted'
            ''', (current_time, moderator_comment, task_id))
            await db.commit()

            if cursor.rowcount > 0:
                logger.info(f"Задание {task_id} одобрено модератором")
                return True
            return False

    async def reject_daily_task(self, task_id: int, moderator_comment: str) -> bool:
        """Отклонить задание модератором"""
        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute('''
                UPDATE daily_tasks
                SET status = 'rejected', moderator_comment = ?
                WHERE id = ? AND status = 'submitted'
            ''', (moderator_comment, task_id))
            await db.commit()

            if cursor.rowcount > 0:
                logger.info(f"Задание {task_id} отклонено модератором")
                return True
            return False

    async def get_pending_moderation_tasks(self) -> list[DailyTask]:
        """Получить задания, ожидающие модерации"""
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute('''
                SELECT * FROM daily_tasks
                WHERE status = 'submitted'
                ORDER BY created_at ASC
            ''')

            rows = await cursor.fetchall()
            tasks = []

            for row in rows:
                tasks.append(DailyTask(
                    id=row['id'],
                    user_id=row['user_id'],
                    task_description=row['task_description'],
                    created_at=row['created_at'],
                    expires_at=row['expires_at'],
                    status=TaskStatus(row['status']),
                    completed_at=row['completed_at'],
                    submitted_media_path=row['submitted_media_path'],
                    moderator_comment=row['moderator_comment']
                ))

            return tasks

    # Методы для работы со статистикой пользователей

    async def save_user_stats(self, stats: UserStats):
        """Сохранение или обновление статистики пользователя"""
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute('''
                INSERT INTO user_stats (user_id, level, experience, rank, referral_rank, current_streak, best_streak, total_tasks_completed, last_task_date)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(user_id) DO UPDATE SET
                    level = excluded.level,
                    experience = excluded.experience,
                    rank = excluded.rank,
                    referral_rank = excluded.referral_rank,
                    current_streak = excluded.current_streak,
                    best_streak = excluded.best_streak,
                    total_tasks_completed = excluded.total_tasks_completed,
                    last_task_date = excluded.last_task_date
            ''', (
                stats.user_id,
                stats.level,
                stats.experience,
                stats.rank.value,
                stats.referral_rank.value if stats.referral_rank else None,
                stats.current_streak,
                stats.best_streak,
                stats.total_tasks_completed,
                stats.last_task_date
            ))
            await db.commit()
            logger.info(f"Статистика пользователя {stats.user_id} сохранена")

    async def get_user_stats(self, user_id: int) -> Optional[UserStats]:
        """Получение статистики пользователя"""
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute('''
                SELECT * FROM user_stats WHERE user_id = ?
            ''', (user_id,))

            row = await cursor.fetchone()
            if row:
                return UserStats(
                    user_id=row['user_id'],
                    level=row['level'],
                    experience=row['experience'],
                    rank=Rank(row['rank']),
                    referral_rank=Rank(row['referral_rank']) if row['referral_rank'] else None,
                    current_streak=row['current_streak'],
                    best_streak=row['best_streak'],
                    total_tasks_completed=row['total_tasks_completed'],
                    last_task_date=row['last_task_date']
                )
            return None

    async def get_top_users_by_city(self, city: str, limit: int = 10) -> list[tuple]:
        """Получение топ пользователей по городу (по уровню)"""
        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute('''
                SELECT u.name, us.level, us.experience, us.rank
                FROM users u
                JOIN user_stats us ON u.telegram_id = us.user_id
                WHERE u.city = ? AND u.subscription_active = TRUE
                ORDER BY us.level DESC, us.experience DESC
                LIMIT ?
            ''', (city, limit))

            rows = await cursor.fetchall()
            return [(row[0], row[1], row[2], row[3]) for row in rows]

    async def get_top_users_by_rank(self, rank: str, limit: int = 10) -> list[tuple]:
        """Получение топ пользователей по рангу"""
        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute('''
                SELECT u.name, us.level, us.experience, u.city
                FROM users u
                JOIN user_stats us ON u.telegram_id = us.user_id
                WHERE us.rank = ? AND u.subscription_active = TRUE
                ORDER BY us.level DESC, us.experience DESC
                LIMIT ?
            ''', (rank, limit))

            rows = await cursor.fetchall()
            return [(row[0], row[1], row[2], row[3]) for row in rows]

    async def get_top_users_by_referral_code(self, referral_code: str, limit: int = 10) -> list[tuple]:
        """Получение топ пользователей среди подписчиков блогера (по реферальному коду)"""
        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute('''
                SELECT u.name, us.level, us.experience, us.referral_rank, u.city
                FROM users u
                JOIN user_stats us ON u.telegram_id = us.user_id
                WHERE u.referral_code = ? AND u.subscription_active = TRUE
                ORDER BY us.level DESC, us.experience DESC
                LIMIT ?
            ''', (referral_code, limit))

            rows = await cursor.fetchall()
            return [(row[0], row[1], row[2], row[3], row[4]) for row in rows]

    async def update_user_referral_rank(self, user_id: int):
        """Обновление рейтинга среди подписчиков блогера для пользователя"""
        # Получаем текущую статистику пользователя
        user_stats = await self.get_user_stats(user_id)
        if not user_stats:
            return

        # Получаем данные пользователя
        user = await self.get_user(user_id)
        if not user or not user.referral_code:
            # Если нет реферального кода, очищаем referral_rank
            user_stats.referral_rank = None
            await self.save_user_stats(user_stats)
            return

        # Если есть реферальный код, referral_rank равен обычному rank
        user_stats.referral_rank = user_stats.rank
        await self.save_user_stats(user_stats)

    async def reset_user_experience(self, user_id: int):
        """Сброс опыта пользователя до 0"""
        async with aiosqlite.connect(self.db_path) as db:
            # Сбрасываем опыт в user_stats
            await db.execute('''
                UPDATE user_stats
                SET experience = 0, level = 1, rank = 'F', updated_at = ?
                WHERE user_id = ?
            ''', (int(datetime.datetime.now().timestamp()), user_id))
            
            # Сбрасываем опыт в player_stats
            await db.execute('''
                UPDATE player_stats
                SET experience = 0, updated_at = ?
                WHERE user_id = ?
            ''', (int(datetime.datetime.now().timestamp()), user_id))
            
            await db.commit()
            logger.info(f"Опыт пользователя {user_id} сброшен до 0")

    async def get_subscriptions_expiring_soon(self, days_before: int = 3) -> list[dict]:
        """Получение подписок, которые истекают через указанное количество дней"""
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            current_time = int(datetime.datetime.now().timestamp())
            target_time = current_time + (days_before * 24 * 60 * 60)
            
            # Получаем подписки, которые истекают через указанное количество дней (±1 день для точности)
            cursor = await db.execute('''
                SELECT DISTINCT 
                    u.telegram_id,
                    s.end_date,
                    s.subscription_level
                FROM users u
                JOIN subscriptions s ON u.telegram_id = s.user_id
                WHERE u.subscription_active = 1 
                AND s.status = 'active'
                AND s.end_date > ?
                AND s.end_date <= ?
                AND s.id = (
                    SELECT id FROM subscriptions s2 
                    WHERE s2.user_id = u.telegram_id 
                    AND s2.status = 'active' 
                    AND s2.end_date > ?
                    ORDER BY s2.end_date DESC 
                    LIMIT 1
                )
            ''', (current_time, target_time, current_time))
            
            rows = await cursor.fetchall()
            result = []
            for row in rows:
                subscription_level = 1
                try:
                    subscription_level = row['subscription_level'] if row['subscription_level'] else 1
                except (KeyError, IndexError):
                    subscription_level = 1
                
                result.append({
                    'user_id': row['telegram_id'],
                    'end_date': row['end_date'],
                    'subscription_level': subscription_level
                })
            return result

    async def get_all_active_subscribed_users(self) -> list[dict]:
        """Получение всех пользователей с активной подпиской"""
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            current_time = int(datetime.datetime.now().timestamp())
            # Получаем пользователей с активной подпиской, используя самую актуальную подписку
            cursor = await db.execute('''
                SELECT DISTINCT 
                    u.telegram_id, 
                    s.subscription_level,
                    us.last_task_date
                FROM users u
                JOIN subscriptions s ON u.telegram_id = s.user_id
                LEFT JOIN user_stats us ON u.telegram_id = us.user_id
                WHERE u.subscription_active = 1 
                AND s.status = 'active'
                AND s.end_date > ?
                AND s.id = (
                    SELECT id FROM subscriptions s2 
                    WHERE s2.user_id = u.telegram_id 
                    AND s2.status = 'active' 
                    AND s2.end_date > ?
                    ORDER BY s2.end_date DESC 
                    LIMIT 1
                )
            ''', (current_time, current_time))
            
            rows = await cursor.fetchall()
            result = []
            for row in rows:
                # Проверяем наличие колонки subscription_level
                subscription_level = 1  # По умолчанию
                try:
                    subscription_level = row['subscription_level'] if row['subscription_level'] else 1
                except (KeyError, IndexError):
                    # Колонка отсутствует в старых версиях БД, определяем по месяцам
                    try:
                        months = row['months']
                        if months >= 12:
                            subscription_level = 3
                        elif months >= 3:
                            subscription_level = 2
                        else:
                            subscription_level = 1
                    except (KeyError, IndexError):
                        subscription_level = 1
                
                result.append({
                    'user_id': row['telegram_id'],
                    'subscription_level': subscription_level,
                    'last_task_date': row['last_task_date']
                })
            return result

    # Методы для работы с рангами

    async def get_user_rank_info(self, user_id: int) -> dict | None:
        """Получение детальной информации о ранге пользователя"""
        from rank_config import get_rank_progress, get_next_rank_experience, RANK_NAMES, RANK_DESCRIPTIONS, RANK_EMOJIS

        user_stats = await self.get_user_stats(user_id)
        if not user_stats:
            return None

        current_rank, exp_in_rank, exp_to_next, progress_percent = get_rank_progress(user_stats.experience)

        next_rank_info = get_next_rank_experience(user_stats.experience)

        return {
            'current_rank': current_rank,
            'current_rank_name': RANK_NAMES.get(current_rank, str(current_rank)),
            'current_rank_description': RANK_DESCRIPTIONS.get(current_rank, ""),
            'current_rank_emoji': RANK_EMOJIS.get(current_rank, ""),
            'experience': user_stats.experience,
            'experience_in_rank': exp_in_rank,
            'experience_to_next_rank': exp_to_next,
            'progress_percentage': progress_percent,
            'next_rank_info': next_rank_info,  # (next_rank, required_exp) или None
            'level': user_stats.level
        }

    async def get_users_by_rank_distribution(self) -> dict:
        """Получение распределения пользователей по рангам"""
        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute('''
                SELECT us.rank, COUNT(*) as count
                FROM user_stats us
                JOIN users u ON us.user_id = u.telegram_id
                WHERE u.subscription_active = 1
                GROUP BY us.rank
                ORDER BY count DESC
            ''')

            rows = await cursor.fetchall()
            return {row[0]: row[1] for row in rows}

    async def get_rank_achievement_stats(self) -> list[tuple]:
        """Статистика достижений рангов (сколько пользователей достигло каждого ранга)"""
        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute('''
                SELECT us.rank, COUNT(*) as count,
                       AVG(us.experience) as avg_experience,
                       MAX(us.experience) as max_experience
                FROM user_stats us
                JOIN users u ON us.user_id = u.telegram_id
                WHERE u.subscription_active = 1
                GROUP BY us.rank
                ORDER BY us.rank
            ''')

            rows = await cursor.fetchall()
            return [(row[0], row[1], row[2], row[3]) for row in rows]

    # Методы для работы с призами

    async def save_prize(self, prize: Prize) -> int:
        """Сохранение или обновление приза"""
        async with aiosqlite.connect(self.db_path) as db:
            if prize.id is None:
                # Создание нового приза
                # Проверяем наличие колонки custom_condition
                cursor = await db.execute("PRAGMA table_info(prizes)")
                columns = [row[1] for row in await cursor.fetchall()]
                has_custom_condition = 'custom_condition' in columns
                
                if has_custom_condition:
                    cursor = await db.execute('''
                        INSERT INTO prizes (prize_type, referral_code, title, description, achievement_type, achievement_value, custom_condition, emoji, is_active, created_at, updated_at)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ''', (
                        prize.prize_type.value,
                        prize.referral_code,
                        prize.title,
                        prize.description,
                        prize.achievement_type,
                        prize.achievement_value,
                        prize.custom_condition,
                        prize.emoji,
                        prize.is_active,
                        prize.created_at,
                        prize.updated_at
                    ))
                else:
                    # Добавляем колонку если её нет
                    await db.execute('ALTER TABLE prizes ADD COLUMN custom_condition TEXT')
                    cursor = await db.execute('''
                        INSERT INTO prizes (prize_type, referral_code, title, description, achievement_type, achievement_value, custom_condition, emoji, is_active, created_at, updated_at)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ''', (
                        prize.prize_type.value,
                        prize.referral_code,
                        prize.title,
                        prize.description,
                        prize.achievement_type,
                        prize.achievement_value,
                        prize.custom_condition,
                        prize.emoji,
                        prize.is_active,
                        prize.created_at,
                        prize.updated_at
                    ))
                prize.id = cursor.lastrowid
            else:
                # Обновление существующего приза
                # Проверяем наличие колонки custom_condition
                cursor = await db.execute("PRAGMA table_info(prizes)")
                columns = [row[1] for row in await cursor.fetchall()]
                has_custom_condition = 'custom_condition' in columns
                
                if not has_custom_condition:
                    await db.execute('ALTER TABLE prizes ADD COLUMN custom_condition TEXT')
                
                await db.execute('''
                    UPDATE prizes SET
                        prize_type = ?,
                        referral_code = ?,
                        title = ?,
                        description = ?,
                        achievement_type = ?,
                        achievement_value = ?,
                        custom_condition = ?,
                        emoji = ?,
                        is_active = ?,
                        updated_at = ?
                    WHERE id = ?
                ''', (
                    prize.prize_type.value,
                    prize.referral_code,
                    prize.title,
                    prize.description,
                    prize.achievement_type,
                    prize.achievement_value,
                    prize.custom_condition,
                    prize.emoji,
                    prize.is_active,
                    prize.updated_at,
                    prize.id
                ))
            await db.commit()
            logger.info(f"Приз '{prize.title}' сохранен (ID: {prize.id})")
            return prize.id

    async def get_prizes(self, prize_type: Optional[PrizeType] = None, referral_code: Optional[str] = None, is_active: bool = True) -> list[Prize]:
        """Получение списка призов"""
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row

            conditions = []
            params = []

            if prize_type is not None:
                conditions.append("prize_type = ?")
                params.append(prize_type.value)

            if referral_code is not None:
                conditions.append("referral_code = ?")
                params.append(referral_code)

            if is_active is not None:
                conditions.append("is_active = ?")
                params.append(is_active)

            where_clause = " AND ".join(conditions) if conditions else "1=1"

            cursor = await db.execute(f'''
                SELECT * FROM prizes WHERE {where_clause}
                ORDER BY created_at DESC
            ''', params)

            rows = await cursor.fetchall()
            prizes = []

            for row in rows:
                # Проверяем наличие колонки custom_condition (для совместимости со старыми БД)
                custom_condition = None
                try:
                    # Пытаемся получить значение, если колонка существует
                    custom_condition = row['custom_condition'] if row['custom_condition'] else None
                except (KeyError, IndexError):
                    # Колонка отсутствует в старых версиях БД
                    custom_condition = None
                
                prizes.append(Prize(
                    id=row['id'],
                    prize_type=PrizeType(row['prize_type']),
                    referral_code=row['referral_code'],
                    title=row['title'],
                    description=row['description'],
                    achievement_type=row['achievement_type'],
                    achievement_value=row['achievement_value'],
                    custom_condition=custom_condition,
                    emoji=row['emoji'],
                    is_active=row['is_active'],
                    created_at=row['created_at'],
                    updated_at=row['updated_at']
                ))

            return prizes

    async def get_prize_by_id(self, prize_id: int) -> Optional[Prize]:
        """Получение приза по ID"""
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute('SELECT * FROM prizes WHERE id = ?', (prize_id,))

            row = await cursor.fetchone()
            if row:
                # Проверяем наличие колонки custom_condition (для совместимости со старыми БД)
                custom_condition = None
                try:
                    # Пытаемся получить значение, если колонка существует
                    custom_condition = row['custom_condition'] if row['custom_condition'] else None
                except (KeyError, IndexError):
                    # Колонка отсутствует в старых версиях БД
                    custom_condition = None
                
                return Prize(
                    id=row['id'],
                    prize_type=PrizeType(row['prize_type']),
                    referral_code=row['referral_code'],
                    title=row['title'],
                    description=row['description'],
                    achievement_type=row['achievement_type'],
                    achievement_value=row['achievement_value'],
                    custom_condition=custom_condition,
                    emoji=row['emoji'],
                    is_active=row['is_active'],
                    created_at=row['created_at'],
                    updated_at=row['updated_at']
                )
            return None

    async def delete_prize(self, prize_id: int) -> bool:
        """Удаление приза"""
        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute('DELETE FROM prizes WHERE id = ?', (prize_id,))
            await db.commit()
            deleted = cursor.rowcount > 0
            if deleted:
                logger.info(f"Приз с ID {prize_id} удален")
            return deleted

    # Методы для модераторского бота

    async def get_total_users_count(self) -> int:
        """Получение общего количества пользователей"""
        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute('SELECT COUNT(*) FROM users')
            result = await cursor.fetchone()
            return result[0] if result else 0

    async def get_active_users_count(self) -> int:
        """Получение количества пользователей с активной подпиской"""
        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute('SELECT COUNT(*) FROM users WHERE subscription_active = 1')
            result = await cursor.fetchone()
            return result[0] if result else 0

    async def get_total_completed_tasks(self) -> int:
        """Получение общего количества выполненных заданий"""
        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute('SELECT SUM(total_tasks_completed) FROM user_stats')
            result = await cursor.fetchone()
            return result[0] if result and result[0] else 0

    async def get_users_by_city_stats(self) -> list[tuple]:
        """Статистика пользователей по городам"""
        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute('''
                SELECT u.city, COUNT(*) as count
                FROM users u
                JOIN user_stats us ON u.telegram_id = us.user_id
                WHERE u.city IS NOT NULL AND u.city != ''
                GROUP BY u.city
                ORDER BY count DESC
                LIMIT 20
            ''')
            rows = await cursor.fetchall()
            return [(row[0], row[1]) for row in rows]

    async def get_users_by_rank_stats(self) -> list[tuple]:
        """Статистика пользователей по рангам"""
        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute('''
                SELECT us.rank, COUNT(*) as count
                FROM user_stats us
                GROUP BY us.rank
                ORDER BY count DESC
            ''')
            rows = await cursor.fetchall()
            return [(row[0], row[1]) for row in rows]

    async def get_users_by_referral_code_stats(self, referral_code: str) -> list[tuple]:
        """Получение статистики подписчиков блогера"""
        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute('''
                SELECT u.name, us.level, us.experience, us.rank
                FROM users u
                JOIN user_stats us ON u.telegram_id = us.user_id
                WHERE u.referral_code = ? AND u.subscription_active = 1
                ORDER BY us.level DESC, us.experience DESC
                LIMIT 50
            ''', (referral_code,))
            rows = await cursor.fetchall()
            return [(row[0], row[1], row[2], row[3]) for row in rows]

    # Методы для модерации заданий

    async def get_pending_tasks_for_moderation(self, limit: int = 50) -> list[tuple]:
        """Получение заданий, ожидающих модерации"""
        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute('''
                SELECT dt.id, dt.user_id, dt.task_description, dt.submitted_media_path,
                       u.name, ps.nickname
                FROM daily_tasks dt
                JOIN users u ON dt.user_id = u.telegram_id
                LEFT JOIN player_stats ps ON dt.user_id = ps.user_id
                WHERE dt.status = 'submitted'
                ORDER BY dt.created_at ASC
                LIMIT ?
            ''', (limit,))
            rows = await cursor.fetchall()
            return [(row[0], row[1], row[2], row[3], row[4], row[5]) for row in rows]

    async def get_task_details(self, task_id: int) -> Optional[dict]:
        """Получение детальной информации о задании"""
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute('''
                SELECT dt.*, u.name, ps.nickname, ps.photo_path
                FROM daily_tasks dt
                JOIN users u ON dt.user_id = u.telegram_id
                LEFT JOIN player_stats ps ON dt.user_id = ps.user_id
                WHERE dt.id = ?
            ''', (task_id,))
            row = await cursor.fetchone()
            if row:
                return dict(row)
            return None

    async def approve_task(self, task_id: int, moderator_id: int, experience_reward: int = 10,
                          stat_rewards: dict = None) -> bool:
        """Одобрение задания с начислением наград"""
        if stat_rewards is None:
            stat_rewards = {'strength': 0, 'agility': 0, 'endurance': 0, 'intelligence': 0, 'charisma': 0}

        async with aiosqlite.connect(self.db_path) as db:
            try:
                # Получаем информацию о задании
                cursor = await db.execute('SELECT user_id, submitted_media_path FROM daily_tasks WHERE id = ?', (task_id,))
                task_row = await cursor.fetchone()
                if not task_row:
                    return False

                user_id = task_row[0]
                media_path = task_row[1]

                # Обновляем статус задания
                await db.execute('''
                    UPDATE daily_tasks
                    SET status = 'approved', completed_at = ?, moderator_comment = ?
                    WHERE id = ?
                ''', (int(datetime.datetime.now().timestamp()), f"Одобрено модератором {moderator_id}", task_id))

                # Начисляем опыт пользователю
                await db.execute('''
                    UPDATE user_stats
                    SET experience = experience + ?, total_tasks_completed = total_tasks_completed + 1
                    WHERE user_id = ?
                ''', (experience_reward, user_id))

                # Начисляем характеристики игроку
                await db.execute('''
                    UPDATE player_stats
                    SET strength = strength + ?,
                        agility = agility + ?,
                        endurance = endurance + ?,
                        intelligence = intelligence + ?,
                        charisma = charisma + ?,
                        experience = experience + ?
                    WHERE user_id = ?
                ''', (
                    stat_rewards.get('strength', 0),
                    stat_rewards.get('agility', 0),
                    stat_rewards.get('endurance', 0),
                    stat_rewards.get('intelligence', 0),
                    stat_rewards.get('charisma', 0),
                    experience_reward,
                    user_id
                ))

                # Обновляем уровень пользователя на основе нового опыта
                await self._update_user_level(user_id, db)

                await db.commit()

                # Отправляем уведомление пользователю (после commit)
                await self.send_task_result_notification(task_id, True, experience_reward, stat_rewards)

                # Удаляем медиафайл для экономии места на сервере
                if media_path:
                    self._delete_task_media_file(media_path)

                logger.info(f"Задание {task_id} одобрено модератором {moderator_id}, начислено опыта: {experience_reward}")
                return True

            except Exception as e:
                await db.rollback()
                logger.error(f"Ошибка при одобрении задания {task_id}: {e}")
                return False

    async def reject_task(self, task_id: int, moderator_id: int, reason: str = "") -> bool:
        """Отклонение задания"""
        async with aiosqlite.connect(self.db_path) as db:
            try:
                # Получаем информацию о задании для удаления файла
                cursor = await db.execute('SELECT submitted_media_path FROM daily_tasks WHERE id = ?', (task_id,))
                task_row = await cursor.fetchone()
                media_path = task_row[0] if task_row else None

                await db.execute('''
                    UPDATE daily_tasks
                    SET status = 'rejected', moderator_comment = ?
                    WHERE id = ?
                ''', (f"Отклонено модератором {moderator_id}: {reason}", task_id))

                await db.commit()

                # Отправляем уведомление пользователю (после commit)
                await self.send_task_result_notification(task_id, False, reason=reason)

                # Удаляем медиафайл для экономии места на сервере
                if media_path:
                    self._delete_task_media_file(media_path)

                logger.info(f"Задание {task_id} отклонено модератором {moderator_id}")
                return True

            except Exception as e:
                await db.rollback()
                logger.error(f"Ошибка при отклонении задания {task_id}: {e}")
                return False

    async def _update_user_level(self, user_id: int, db):
        """Обновление уровня и ранга пользователя на основе опыта"""
        cursor = await db.execute('SELECT experience FROM user_stats WHERE user_id = ?', (user_id,))
        row = await cursor.fetchone()
        if row:
            experience = row[0]
            new_level = experience // 100 + 1  # Каждый 100 опыта = 1 уровень
            new_rank = get_rank_by_experience(experience)  # Получаем ранг по опыту

            await db.execute('UPDATE user_stats SET level = ?, rank = ? WHERE user_id = ?', (new_level, new_rank.value, user_id))

    def _delete_task_media_file(self, media_path: str) -> bool:
        """Удаление медиафайла задания для экономии места"""
        if not media_path:
            return False

        try:
            if os.path.exists(media_path):
                os.remove(media_path)
                logger.info(f"Медиафайл задания удален: {media_path}")
                return True
            else:
                logger.warning(f"Медиафайл не найден для удаления: {media_path}")
                return False
        except Exception as e:
            logger.error(f"Ошибка при удалении медиафайла {media_path}: {e}")
            return False

    # Методы для работы с уведомлениями
    async def create_notification(self, user_id: int, notification_type: str, title: str, message: str, data: str = None) -> bool:
        """Создание уведомления для пользователя"""
        async with aiosqlite.connect(self.db_path) as db:
            try:
                await db.execute('''
                    INSERT INTO notifications (user_id, type, title, message, data, created_at)
                    VALUES (?, ?, ?, ?, ?, ?)
                ''', (user_id, notification_type, title, message, data, int(datetime.datetime.now().timestamp())))

                await db.commit()
                logger.info(f"Уведомление типа '{notification_type}' создано для пользователя {user_id}")
                return True

            except Exception as e:
                await db.rollback()
                logger.error(f"Ошибка при создании уведомления для пользователя {user_id}: {e}")
                return False

    async def get_unsent_notifications(self, user_id: int = None, limit: int = 50) -> list[dict]:
        """Получение неотправленных уведомлений"""
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row

            if user_id:
                cursor = await db.execute('''
                    SELECT * FROM notifications
                    WHERE user_id = ? AND is_sent = FALSE
                    ORDER BY created_at ASC
                    LIMIT ?
                ''', (user_id, limit))
            else:
                cursor = await db.execute('''
                    SELECT * FROM notifications
                    WHERE is_sent = FALSE
                    ORDER BY created_at ASC
                    LIMIT ?
                ''', (limit,))

            rows = await cursor.fetchall()
            return [dict(row) for row in rows]

    async def mark_notification_sent(self, notification_id: int) -> bool:
        """Отметить уведомление как отправленное"""
        async with aiosqlite.connect(self.db_path) as db:
            try:
                await db.execute('''
                    UPDATE notifications
                    SET is_sent = TRUE, sent_at = ?
                    WHERE id = ?
                ''', (int(datetime.datetime.now().timestamp()), notification_id))

                await db.commit()
                return True

            except Exception as e:
                await db.rollback()
                logger.error(f"Ошибка при отметке уведомления {notification_id} как отправленного: {e}")
                return False

    async def send_task_result_notification(self, task_id: int, approved: bool, experience_reward: int = 0,
                                          stat_rewards: dict = None, reason: str = "") -> bool:
        """Отправка уведомления о результате проверки задания"""
        if stat_rewards is None:
            stat_rewards = {}

        async with aiosqlite.connect(self.db_path) as db:
            try:
                # Получаем информацию о задании и пользователе
                cursor = await db.execute('''
                    SELECT dt.user_id, dt.task_description, u.name
                    FROM daily_tasks dt
                    JOIN users u ON dt.user_id = u.telegram_id
                    WHERE dt.id = ?
                ''', (task_id,))
                task_info = await cursor.fetchone()

                if not task_info:
                    logger.error(f"Задание {task_id} не найдено при отправке уведомления")
                    return False

                user_id, task_desc, user_name = task_info

                if approved:
                    # Уведомление об одобрении
                    title = "🎉 Задание одобрено!"

                    # Формируем сообщение с наградами
                    message = f"✅ <b>Ваше задание было одобрено модератором!</b>\n\n"
                    message += f"📝 <b>Задание:</b>\n{task_desc}\n\n"
                    message += f"🎉 <b>Награды:</b>\n"
                    message += f"⭐ Опыт: +{experience_reward}\n"

                    if any(stat_rewards.values()):
                        message += "💪 Характеристики:\n"
                        stat_display_names = {
                            'strength': '💪 Сила',
                            'agility': '🤸 Ловкость',
                            'endurance': '🏃 Выносливость',
                            'intelligence': '🧠 Интеллект',
                            'charisma': '✨ Харизма'
                        }
                        for stat_name, value in stat_rewards.items():
                            if value > 0:
                                message += f"{stat_display_names[stat_name]}: +{value}\n"

                    notification_type = "task_approved"
                    data = f'{{"experience": {experience_reward}, "stats": {stat_rewards}}}'

                else:
                    # Уведомление об отклонении
                    title = "❌ Задание отклонено"

                    message = f"❌ <b>Ваше задание было отклонено модератором</b>\n\n"
                    message += f"📝 <b>Задание:</b>\n{task_desc}\n\n"
                    if reason and reason != "Без указания причины":
                        message += f"📋 <b>Причина:</b>\n{reason}\n\n"
                    message += "💡 Попробуйте выполнить задание лучше и отправьте снова!"

                    notification_type = "task_rejected"
                    data = f'{{"reason": "{reason}"}}'

                # Создаем уведомление
                success = await self.create_notification(user_id, notification_type, title, message, data)
                if success:
                    logger.info(f"Уведомление о результате задания {task_id} создано для пользователя {user_id}")
                return success

            except Exception as e:
                logger.error(f"Ошибка при создании уведомления о задании {task_id}: {e}")
                return False

    # Методы для работы с блогерами
    async def get_blogger_stats(self, blogger_telegram_id: int) -> dict:
        """Получение статистики блогера"""
        async with aiosqlite.connect(self.db_path) as db:
            # Получаем реферальный код блогера
            blogger = await self.get_blogger_by_telegram_id(blogger_telegram_id)
            if not blogger:
                return {'error': 'Блогер не найден'}

            referral_code = blogger['referral_code']

            # Статистика подписчиков
            cursor = await db.execute('''
                SELECT COUNT(*) as total_subscribers
                FROM users
                WHERE referral_code = ?
            ''', (referral_code,))

            subscribers_row = await cursor.fetchone()
            total_subscribers = subscribers_row[0] if subscribers_row else 0

            # Статистика активных подписчиков (с подпиской)
            cursor = await db.execute('''
                SELECT COUNT(*) as active_subscribers
                FROM users
                WHERE referral_code = ? AND subscription_active = 1
            ''', (referral_code,))

            active_row = await cursor.fetchone()
            active_subscribers = active_row[0] if active_row else 0

            # Количество выполненных заданий подписчиками
            cursor = await db.execute('''
                SELECT COUNT(*) as total_tasks
                FROM daily_tasks dt
                JOIN users u ON dt.user_id = u.telegram_id
                WHERE u.referral_code = ? AND dt.status IN ('approved', 'completed')
            ''', (referral_code,))

            tasks_row = await cursor.fetchone()
            total_tasks = tasks_row[0] if tasks_row else 0

            return {
                'referral_code': referral_code,
                'total_subscribers': total_subscribers,
                'active_subscribers': active_subscribers,
                'inactive_subscribers': total_subscribers - active_subscribers,
                'total_tasks_completed': total_tasks
            }

    async def get_blogger_top_subscribers(self, blogger_telegram_id: int, limit: int = 10) -> list[dict]:
        """Получение топ-10 подписчиков блогера по опыту"""
        async with aiosqlite.connect(self.db_path) as db:
            # Получаем реферальный код блогера
            blogger = await self.get_blogger_by_telegram_id(blogger_telegram_id)
            if not blogger:
                return []

            referral_code = blogger['referral_code']

            # Получаем топ подписчиков по опыту
            cursor = await db.execute('''
                SELECT
                    u.telegram_id,
                    u.name,
                    ps.nickname,
                    us.experience,
                    us.level,
                    COUNT(dt.id) as tasks_completed
                FROM users u
                LEFT JOIN user_stats us ON u.telegram_id = us.user_id
                LEFT JOIN player_stats ps ON u.telegram_id = ps.user_id
                LEFT JOIN daily_tasks dt ON u.telegram_id = dt.user_id AND dt.status IN ('approved', 'completed')
                WHERE u.referral_code = ?
                GROUP BY u.telegram_id, u.name, ps.nickname, us.experience, us.level
                ORDER BY us.experience DESC, tasks_completed DESC
                LIMIT ?
            ''', (referral_code, limit))

            rows = await cursor.fetchall()

            result = []
            for row in rows:
                telegram_id, name, nickname, experience, level, tasks_completed = row
                display_name = nickname or name or f"User_{telegram_id}"

                result.append({
                    'telegram_id': telegram_id,
                    'display_name': display_name,
                    'experience': experience or 0,
                    'level': level or 1,
                    'tasks_completed': tasks_completed or 0
                })

            return result

    # Методы для статистики модерации
    async def get_moderator_stats(self, moderator_id: int) -> dict:
        """Получение статистики модерации для конкретного модератора"""
        async with aiosqlite.connect(self.db_path) as db:
            # Статистика за все время
            cursor = await db.execute('''
                SELECT COUNT(*) as total_moderated
                FROM daily_tasks
                WHERE moderator_comment LIKE ?
            ''', (f"Одобрено модератором {moderator_id}%",))

            total_row = await cursor.fetchone()
            total_moderated = total_row[0] if total_row else 0

            # Статистика за сегодня
            today_start = int(datetime.datetime.now().replace(hour=0, minute=0, second=0, microsecond=0).timestamp())
            today_end = today_start + 86400  # 24 часа

            cursor = await db.execute('''
                SELECT COUNT(*) as today_moderated
                FROM daily_tasks
                WHERE moderator_comment LIKE ?
                AND completed_at >= ? AND completed_at < ?
            ''', (f"Одобрено модератором {moderator_id}%", today_start, today_end))

            today_row = await cursor.fetchone()
            today_moderated = today_row[0] if today_row else 0

            # Статистика отклоненных заданий за все время
            cursor = await db.execute('''
                SELECT COUNT(*) as total_rejected
                FROM daily_tasks
                WHERE moderator_comment LIKE ?
            ''', (f"Отклонено модератором {moderator_id}%",))

            rejected_row = await cursor.fetchone()
            total_rejected = rejected_row[0] if rejected_row else 0

            # Статистика отклоненных заданий за сегодня
            cursor = await db.execute('''
                SELECT COUNT(*) as today_rejected
                FROM daily_tasks
                WHERE moderator_comment LIKE ?
                AND completed_at >= ? AND completed_at < ?
            ''', (f"Отклонено модератором {moderator_id}%", today_start, today_end))

            today_rejected_row = await cursor.fetchone()
            today_rejected = today_rejected_row[0] if today_rejected_row else 0

            return {
                'total_moderated': total_moderated,
                'today_moderated': today_moderated,
                'total_rejected': total_rejected,
                'today_rejected': today_rejected,
                'total_tasks': total_moderated + total_rejected,
                'today_tasks': today_moderated + today_rejected
            }

    # Методы для управления модераторами

    async def add_moderator(self, telegram_id: int, username: str = None, full_name: str = None) -> bool:
        """Добавление модератора"""
        async with aiosqlite.connect(self.db_path) as db:
            try:
                current_time = int(datetime.datetime.now().timestamp())
                await db.execute('''
                    INSERT INTO moderators (telegram_id, username, full_name, created_at, updated_at)
                    VALUES (?, ?, ?, ?, ?)
                    ON CONFLICT(telegram_id) DO UPDATE SET
                        username = excluded.username,
                        full_name = excluded.full_name,
                        is_active = 1,
                        updated_at = excluded.updated_at
                ''', (telegram_id, username, full_name, current_time, current_time))
                await db.commit()
                logger.info(f"Модератор {telegram_id} добавлен/обновлен")
                return True
            except Exception as e:
                await db.rollback()
                logger.error(f"Ошибка добавления модератора {telegram_id}: {e}")
                return False

    async def remove_moderator(self, telegram_id: int) -> bool:
        """Удаление модератора"""
        async with aiosqlite.connect(self.db_path) as db:
            try:
                cursor = await db.execute('DELETE FROM moderators WHERE telegram_id = ?', (telegram_id,))
                deleted = cursor.rowcount > 0
                await db.commit()
                if deleted:
                    logger.info(f"Модератор {telegram_id} удален")
                return deleted
            except Exception as e:
                await db.rollback()
                logger.error(f"Ошибка удаления модератора {telegram_id}: {e}")
                return False

    async def get_moderators(self, active_only: bool = True) -> list[dict]:
        """Получение списка модераторов"""
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row

            query = 'SELECT * FROM moderators'
            params = []

            if active_only:
                query += ' WHERE is_active = 1'

            query += ' ORDER BY created_at DESC'

            cursor = await db.execute(query, params)
            rows = await cursor.fetchall()
            return [dict(row) for row in rows]

    async def get_moderator_by_telegram_id(self, telegram_id: int) -> Optional[dict]:
        """Получение модератора по Telegram ID"""
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute('SELECT * FROM moderators WHERE telegram_id = ?', (telegram_id,))
            row = await cursor.fetchone()
            return dict(row) if row else None

    # Методы для управления блогерами

    async def add_blogger(self, telegram_id: int, referral_code: str, username: str = None, full_name: str = None) -> bool:
        """Добавление блогера"""
        async with aiosqlite.connect(self.db_path) as db:
            try:
                current_time = int(datetime.datetime.now().timestamp())
                await db.execute('''
                    INSERT INTO bloggers (telegram_id, username, full_name, referral_code, created_at, updated_at)
                    VALUES (?, ?, ?, ?, ?, ?)
                    ON CONFLICT(telegram_id) DO UPDATE SET
                        username = excluded.username,
                        full_name = excluded.full_name,
                        referral_code = excluded.referral_code,
                        is_active = 1,
                        updated_at = excluded.updated_at
                ''', (telegram_id, username, full_name, referral_code, current_time, current_time))
                await db.commit()
                logger.info(f"Блогер {telegram_id} с реферальным кодом {referral_code} добавлен/обновлен")
                return True
            except Exception as e:
                await db.rollback()
                logger.error(f"Ошибка добавления блогера {telegram_id}: {e}")
                return False

    async def remove_blogger(self, telegram_id: int) -> bool:
        """Удаление блогера"""
        async with aiosqlite.connect(self.db_path) as db:
            try:
                cursor = await db.execute('DELETE FROM bloggers WHERE telegram_id = ?', (telegram_id,))
                deleted = cursor.rowcount > 0
                await db.commit()
                if deleted:
                    logger.info(f"Блогер {telegram_id} удален")
                return deleted
            except Exception as e:
                await db.rollback()
                logger.error(f"Ошибка удаления блогера {telegram_id}: {e}")
                return False

    async def get_bloggers(self, active_only: bool = True) -> list[dict]:
        """Получение списка блогеров"""
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row

            query = 'SELECT * FROM bloggers'
            params = []

            if active_only:
                query += ' WHERE is_active = 1'

            query += ' ORDER BY created_at DESC'

            cursor = await db.execute(query, params)
            rows = await cursor.fetchall()
            return [dict(row) for row in rows]

    async def get_blogger_by_telegram_id(self, telegram_id: int) -> Optional[dict]:
        """Получение блогера по Telegram ID"""
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute('SELECT * FROM bloggers WHERE telegram_id = ?', (telegram_id,))
            row = await cursor.fetchone()
            return dict(row) if row else None

    async def get_blogger_by_referral_code(self, referral_code: str) -> Optional[dict]:
        """Получение блогера по реферальному коду"""
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute('SELECT * FROM bloggers WHERE referral_code = ? AND is_active = 1', (referral_code,))
            row = await cursor.fetchone()
            return dict(row) if row else None

    # Методы для получения списков ID для авторизации

    async def get_moderator_telegram_ids(self) -> list[int]:
        """Получение списка Telegram ID модераторов"""
        moderators = await self.get_moderators(active_only=True)
        return [m['telegram_id'] for m in moderators]

    async def get_blogger_telegram_ids(self) -> list[int]:
        """Получение списка Telegram ID блогеров"""
        bloggers = await self.get_bloggers(active_only=True)
        return [b['telegram_id'] for b in bloggers]

    async def get_admin_telegram_ids(self) -> list[int]:
        """Получение списка Telegram ID админов (из переменных окружения)"""
        try:
            from moderator_config import ADMIN_TELEGRAM_IDS
            return ADMIN_TELEGRAM_IDS
        except ImportError:
            # Fallback на случай если moderator_config не доступен
            return []
