from dataclasses import dataclass
from typing import Optional
from datetime import date
from enum import Enum

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
