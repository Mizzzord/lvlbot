from dataclasses import dataclass
from typing import Optional
from datetime import date
from enum import Enum

class PrizeType(Enum):
    ADMIN = "admin"        # призы от главного модератора
    BLOGGER = "blogger"    # призы от блогера

@dataclass
class User:
    telegram_id: int
    language: Optional[str] = None
    name: Optional[str] = None
    birth_date: Optional[date] = None
    height: Optional[float] = None
    weight: Optional[float] = None
    city: Optional[str] = None
    referral_code: Optional[str] = None
    goal: Optional[str] = None
    subscription_active: bool = False
    subscription_start: Optional[int] = None  # timestamp
    subscription_end: Optional[int] = None  # timestamp
    referral_count: int = 0  # количество приглашенных пользователей

    @property
    def is_complete(self) -> bool:
        """Проверяет, заполнены ли все поля пользователя"""
        return all([
            self.language is not None,
            self.name is not None,
            self.birth_date is not None,
            self.height is not None,
            self.weight is not None,
            self.city is not None
        ])

class PaymentStatus(Enum):
    PENDING = "pending"
    PAID = "paid"
    CANCELLED = "cancelled"
    EXPIRED = "expired"
    FAILED = "failed"

class SubscriptionStatus(Enum):
    ACTIVE = "active"
    EXPIRED = "expired"
    CANCELLED = "cancelled"
    PENDING = "pending"

@dataclass
class Payment:
    id: Optional[int] = None
    user_id: int = 0
    payment_id: str = ""  # ID платежа от WATA
    order_id: str = ""  # Уникальный orderId для поиска
    amount: float = 0.0
    months: int = 0
    status: PaymentStatus = PaymentStatus.PENDING
    created_at: int = 0  # timestamp
    paid_at: Optional[int] = None  # timestamp оплаты
    currency: str = "RUB"
    payment_method: str = "WATA"
    discount_code: Optional[str] = None
    referral_used: Optional[str] = None
    subscription_type: str = "standard"  # standard, premium, etc.
    subscription_level: int = 1  # уровень подписки (1, 2 или 3)

@dataclass
class Subscription:
    id: Optional[int] = None
    user_id: int = 0
    payment_id: Optional[int] = None  # ссылка на платеж
    start_date: int = 0  # timestamp начала
    end_date: int = 0  # timestamp окончания
    months: int = 0
    subscription_level: int = 1  # уровень подписки (1, 2 или 3)
    status: SubscriptionStatus = SubscriptionStatus.PENDING
    auto_renew: bool = False
    created_at: int = 0  # timestamp создания
    updated_at: int = 0  # timestamp обновления

@dataclass
class PlayerStats:
    id: Optional[int] = None
    user_id: int = 0
    nickname: Optional[str] = None  # ник игрока
    experience: int = 0  # опыт игрока
    strength: int = 50  # сила (0-100)
    agility: int = 50    # ловкость (0-100)
    endurance: int = 50  # выносливость (0-100)
    intelligence: int = 50  # интеллект (0-100)
    charisma: int = 50    # харизма (0-100)
    photo_path: Optional[str] = None  # путь к фото
    card_image_path: Optional[str] = None  # путь к изображению карточки
    created_at: int = 0  # timestamp создания
    updated_at: int = 0  # timestamp обновления

class Rank(Enum):
    F = "F"
    E = "E"
    D = "D"
    C = "C"
    B = "B"
    A = "A"
    S = "S"
    S_PLUS = "S+"

class TaskStatus(Enum):
    PENDING = "pending"      # задание выдано, ожидает выполнения
    SUBMITTED = "submitted"  # пользователь отправил медиафайл, ожидает модерации
    APPROVED = "approved"    # задание одобрено модератором
    REJECTED = "rejected"    # задание отклонено модератором
    EXPIRED = "expired"      # время на выполнение вышло

@dataclass
class DailyTask:
    id: Optional[int] = None
    user_id: int = 0
    task_description: str = ""
    created_at: int = 0  # timestamp создания
    expires_at: int = 0   # timestamp окончания (24 часа)
    status: TaskStatus = TaskStatus.PENDING
    completed_at: Optional[int] = None  # timestamp выполнения
    submitted_media_path: Optional[str] = None  # путь к загруженному медиафайлу
    moderator_comment: Optional[str] = None  # комментарий модератора

@dataclass
class UserStats:
    user_id: int = 0
    level: int = 1
    experience: int = 0
    rank: Rank = Rank.F
    referral_rank: Optional[Rank] = None  # рейтинг среди подписчиков блогера (активен только если указан реферальный код)
    current_streak: int = 0  # дней подряд выполнения целей
    best_streak: int = 0     # лучший стрик
    total_tasks_completed: int = 0
    last_task_date: Optional[int] = None  # timestamp последнего выполненного задания

@dataclass
class Prize:
    id: Optional[int] = None
    prize_type: PrizeType = PrizeType.ADMIN  # тип приза: admin или blogger
    referral_code: Optional[str] = None  # реферальный код блогера (только для blogger типа)
    title: str = ""  # название приза
    description: str = ""  # описание приза
    achievement_type: str = ""  # тип достижения (streak, rank, level, tasks, experience, custom)
    achievement_value: int = 0  # значение достижения (число для стандартных типов)
    custom_condition: Optional[str] = None  # произвольное текстовое описание условия (для типа "custom")
    subscription_level: Optional[int] = None  # уровень подписки (None - для всех, 2 - для уровня 2, 3 - для уровня 3)
    emoji: str = "🎁"  # эмодзи приза
    is_active: bool = True  # активен ли приз
    created_at: int = 0  # timestamp создания
    updated_at: int = 0  # timestamp обновления
