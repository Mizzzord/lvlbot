from dataclasses import dataclass
from typing import Optional
from datetime import date

@dataclass
class User:
    telegram_id: int
    language: Optional[str] = None
    name: Optional[str] = None
    birth_date: Optional[date] = None
    height: Optional[float] = None
    weight: Optional[float] = None
    city: Optional[str] = None

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
