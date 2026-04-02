# bought_models.py - Модели для покупок

from sqlmodel import Field, SQLModel
from pydantic import BaseModel
from typing import Optional
from datetime import datetime
from enum import Enum

# Статусы заказа
class OrderStatus(str, Enum):
    AWAITING_SHIPMENT = "Ждет отправки"
    SHIPPING = "Отправляется"
    AWAITING_RECEIPT = "Ждёт получения"
    RECEIVED = "Получен"
    APPROVED = "Одобрен"
    RETURN = "Возврат"

# Модель для базы данных
class BoughtItem(SQLModel, table=True):
    __tablename__ = "bought"
    
    id: Optional[int] = Field(default=None, primary_key=True)
    
    # ID объявления и покупателя
    post_id: int = Field(index=True, foreign_key="products.id")
    buyer_id: int = Field(index=True)  # ID пользователя из auth
    
    # Контактная информация покупателя
    buyer_name: str = Field(max_length=150)
    buyer_surname: str = Field(max_length=150)
    buyer_phone: str = Field(max_length=20)
    buyer_email: str = Field(max_length=150)
    
    # Способ доставки
    delivery_method: str = Field(max_length=50)  # "personal_pickup", "dpd", "omniva"
    
    # === ФАЗА 2: Новые поля доставки ===
    delivery_cost: float = Field(default=0, ge=0)  # Стоимость доставки
    selected_locker_id: Optional[str] = Field(default=None, max_length=100)  # ID выбранного паковомата
    selected_locker_name: Optional[str] = Field(default=None, max_length=255)  # Название паковомата
    
    # === ФАЗА 4: Подтверждение состояния ===
    order_confirmed_at: Optional[datetime] = Field(default=None)  # Когда покупатель подтвердил состояние
    
    # === ФАЗА 5: Скидки и возвраты ===
    discount_offered: Optional[float] = Field(default=None, ge=0)  # Сумма скидки предложенной продавцом
    discount_status: Optional[str] = Field(default=None, max_length=50)  # "pending", "accepted", "rejected"
    
    # Статус заказа
    status: str = Field(default=OrderStatus.AWAITING_SHIPMENT, max_length=50)
    
    # Даты
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)

# Схема для создания заказа (POST)
class BoughtItemCreate(BaseModel):
    post_id: int
    buyer_name: Optional[str] = None
    buyer_surname: Optional[str] = None
    buyer_phone: Optional[str] = None
    buyer_email: Optional[str] = None
    delivery_method: str
    # === ФАЗА 2: Новые поля ===
    delivery_cost: float = 0
    selected_locker_id: Optional[str] = None
    selected_locker_name: Optional[str] = None

# Схема для ответа
class BoughtItemPublic(BaseModel):
    id: int
    post_id: int
    buyer_id: int
    buyer_name: str
    buyer_surname: str
    buyer_phone: str
    buyer_email: str
    delivery_method: str
    # === ФАЗА 2: Новые поля ===
    delivery_cost: float = 0
    selected_locker_id: Optional[str] = None
    selected_locker_name: Optional[str] = None
    order_confirmed_at: Optional[datetime] = None
    discount_offered: Optional[float] = None
    discount_status: Optional[str] = None
    status: str
    created_at: datetime
    updated_at: datetime
    
    class Config:
        from_attributes = True
