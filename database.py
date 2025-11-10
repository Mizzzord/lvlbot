import aiosqlite
import datetime
import logging
from datetime import date
from typing import Optional
from models import User, Payment, PaymentStatus, Subscription, SubscriptionStatus, PlayerStats, Rank, DailyTask, UserStats

logger = logging.getLogger(__name__)

class Database:
    def __init__(self, db_path: str = "bot_database.db"):
        self.db_path = db_path

    async def init_db(self):
        """Инициализация базы данных и создание таблиц"""
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
                    status TEXT DEFAULT 'pending',
                    auto_renew BOOLEAN DEFAULT FALSE,
                    created_at INTEGER,
                    updated_at INTEGER,
                    FOREIGN KEY (user_id) REFERENCES users (telegram_id),
                    FOREIGN KEY (payment_id) REFERENCES payments (id)
                )
            ''')

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
                    completed BOOLEAN DEFAULT FALSE,
                    completed_at INTEGER,
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

            # Создаем индексы для производительности
            await db.execute('CREATE INDEX IF NOT EXISTS idx_payments_user_id ON payments(user_id)')
            await db.execute('CREATE INDEX IF NOT EXISTS idx_payments_status ON payments(status)')
            await db.execute('CREATE INDEX IF NOT EXISTS idx_subscriptions_user_id ON subscriptions(user_id)')
            await db.execute('CREATE INDEX IF NOT EXISTS idx_subscriptions_status ON subscriptions(status)')
            await db.execute('CREATE INDEX IF NOT EXISTS idx_player_stats_user_id ON player_stats(user_id)')
            await db.execute('CREATE INDEX IF NOT EXISTS idx_daily_tasks_user_id ON daily_tasks(user_id)')
            await db.execute('CREATE INDEX IF NOT EXISTS idx_daily_tasks_expires_at ON daily_tasks(expires_at)')
            await db.execute('CREATE INDEX IF NOT EXISTS idx_user_stats_rank ON user_stats(rank)')

            # Добавляем недостающие колонки для существующих баз данных
            await self._add_missing_columns(db)

            await db.commit()
            logger.info("База данных инициализирована")

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
                return Subscription(
                    id=row['id'],
                    user_id=row['user_id'],
                    payment_id=row['payment_id'],
                    start_date=row['start_date'],
                    end_date=row['end_date'],
                    months=row['months'],
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
                subscriptions.append(Subscription(
                    id=row['id'],
                    user_id=row['user_id'],
                    payment_id=row['payment_id'],
                    start_date=row['start_date'],
                    end_date=row['end_date'],
                    months=row['months'],
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
                INSERT INTO daily_tasks (user_id, task_description, created_at, expires_at, completed, completed_at)
                VALUES (?, ?, ?, ?, ?, ?)
            ''', (
                task.user_id,
                task.task_description,
                task.created_at,
                task.expires_at,
                task.completed,
                task.completed_at
            ))
            task_id = cursor.lastrowid
            await db.commit()
            logger.info(f"Ежедневное задание для пользователя {task.user_id} сохранено")
            return task_id

    async def get_active_daily_task(self, user_id: int) -> Optional[DailyTask]:
        """Получение активного ежедневного задания пользователя"""
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute('''
                SELECT * FROM daily_tasks
                WHERE user_id = ? AND completed = FALSE AND expires_at > ?
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
                    completed=row['completed'],
                    completed_at=row['completed_at']
                )
            return None

    async def complete_daily_task(self, task_id: int) -> bool:
        """Отметить задание как выполненное"""
        async with aiosqlite.connect(self.db_path) as db:
            current_time = int(datetime.datetime.now().timestamp())
            cursor = await db.execute('''
                UPDATE daily_tasks
                SET completed = TRUE, completed_at = ?
                WHERE id = ?
            ''', (current_time, task_id))
            await db.commit()

            if cursor.rowcount > 0:
                logger.info(f"Задание {task_id} отмечено как выполненное")
                return True
            return False

    # Методы для работы со статистикой пользователей

    async def save_user_stats(self, stats: UserStats):
        """Сохранение или обновление статистики пользователя"""
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute('''
                INSERT INTO user_stats (user_id, level, experience, rank, current_streak, best_streak, total_tasks_completed, last_task_date)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(user_id) DO UPDATE SET
                    level = excluded.level,
                    experience = excluded.experience,
                    rank = excluded.rank,
                    current_streak = excluded.current_streak,
                    best_streak = excluded.best_streak,
                    total_tasks_completed = excluded.total_tasks_completed,
                    last_task_date = excluded.last_task_date
            ''', (
                stats.user_id,
                stats.level,
                stats.experience,
                stats.rank.value,
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
