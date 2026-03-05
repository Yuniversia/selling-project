# models.py - Модели для delivery service

from sqlmodel import Field, SQLModel
from pydantic import BaseModel, Field as PydanticField
from typing import Optional
from datetime import datetime
from enum import Enum


# =============================================================================
# ENUMS
# =============================================================================

class DeliveryProvider(str, Enum):
    """Провайдеры доставки"""
    OMNIVA = "omniva"
    DPD = "dpd"
    PICKUP = "pickup"  # Самовывоз


class DeliveryStatus(str, Enum):
    """Статусы доставки"""
    CREATED = "created"  # Доставка создана
    IN_TRANSIT = "in_transit"  # В пути
    AT_PICKUP_POINT = "at_pickup_point"  # В пункте выдачи/покамате
    PICKED_UP = "picked_up"  # Получено покупателем
    CANCELLED = "cancelled"  # Отменено
    RETURNED = "returned"  # Возвращено отправителю


# =============================================================================
# DATABASE MODELS
# =============================================================================

class Delivery(SQLModel, table=True):
    """Таблица доставок"""
    id: Optional[int] = Field(default=None, primary_key=True)
    
    # Связь с заказом (без foreign key - микросервисная архитектура)
    order_id: int = Field(index=True, unique=True)
    
    # Провайдер доставки
    provider: str = Field(max_length=20, index=True)  # omniva, dpd, pickup
    
    # Трекинг номер (генерируется автоматически)
    tracking_number: str = Field(max_length=100, unique=True, index=True)
    
    # Код получения из пакомата (6 цифр, генерируется при статусе at_pickup_point)
    pickup_code: Optional[str] = Field(default=None, max_length=6)
    
    # Статус доставки
    status: str = Field(default="created", max_length=30, index=True)
    
    # Адрес доставки
    delivery_address: Optional[str] = Field(default=None, max_length=500)
    delivery_city: Optional[str] = Field(default=None, max_length=100)
    delivery_zip: Optional[str] = Field(default=None, max_length=20)
    delivery_country: Optional[str] = Field(default="Latvia", max_length=100)
    
    # Пункт выдачи (для Omniva/DPD)
    pickup_point_id: Optional[str] = Field(default=None, max_length=100)
    pickup_point_name: Optional[str] = Field(default=None, max_length=200)
    pickup_point_address: Optional[str] = Field(default=None, max_length=500)
    
    # Получатель
    recipient_name: str = Field(max_length=200)
    recipient_phone: str = Field(max_length=20)
    recipient_email: str = Field(max_length=255)
    
    # Отправитель
    sender_name: str = Field(max_length=200)
    sender_phone: str = Field(max_length=20)
    
    # Временные метки
    created_at: datetime = Field(default_factory=datetime.utcnow)
    shipped_at: Optional[datetime] = Field(default=None)  # Отправлено
    arrived_at_pickup_point_at: Optional[datetime] = Field(default=None)  # Прибыло в пункт выдачи
    picked_up_at: Optional[datetime] = Field(default=None)  # Получено
    
    # Метаданные
    estimated_delivery_date: Optional[datetime] = Field(default=None)
    notes: Optional[str] = Field(default=None, max_length=1000)
    
    # Уведомления отправлены
    notification_sent_at_pickup_point: bool = Field(default=False)  # SMS с кодом отправлен
    notification_sent_picked_up: bool = Field(default=False)  # SMS о получении отправлен


class DeliveryStatusHistory(SQLModel, table=True):
    """История изменения статусов доставки"""
    id: Optional[int] = Field(default=None, primary_key=True)
    
    delivery_id: int = Field(index=True)
    status: str = Field(max_length=30)
    notes: Optional[str] = Field(default=None, max_length=500)
    
    created_at: datetime = Field(default_factory=datetime.utcnow)


# =============================================================================
# PYDANTIC MODELS FOR API
# =============================================================================

class DeliveryCreate(BaseModel):
    """Данные для создания доставки"""
    order_id: int = PydanticField(..., description="ID заказа")
    provider: DeliveryProvider = PydanticField(..., description="Провайдер доставки")
    
    # Адрес доставки
    delivery_address: Optional[str] = PydanticField(None, max_length=500)
    delivery_city: Optional[str] = PydanticField(None, max_length=100)
    delivery_zip: Optional[str] = PydanticField(None, max_length=20)
    delivery_country: str = PydanticField(default="Latvia", max_length=100)
    
    # Пункт выдачи (опционально)
    pickup_point_id: Optional[str] = PydanticField(None, max_length=100)
    pickup_point_name: Optional[str] = PydanticField(None, max_length=200)
    pickup_point_address: Optional[str] = PydanticField(None, max_length=500)
    
    # Получатель
    recipient_name: str = PydanticField(..., max_length=200)
    recipient_phone: str = PydanticField(..., max_length=20)
    recipient_email: str = PydanticField(..., max_length=255)
    
    # Отправитель
    sender_name: str = PydanticField(..., max_length=200)
    sender_phone: str = PydanticField(..., max_length=20)
    
    notes: Optional[str] = PydanticField(None, max_length=1000)


class DeliveryResponse(BaseModel):
    """Ответ с данными доставки"""
    id: int
    order_id: int
    provider: str
    tracking_number: str
    pickup_code: Optional[str]
    status: str
    
    delivery_address: Optional[str]
    delivery_city: Optional[str]
    delivery_zip: Optional[str]
    delivery_country: Optional[str]
    
    pickup_point_name: Optional[str]
    pickup_point_address: Optional[str]
    
    recipient_name: str
    recipient_phone: str
    
    created_at: datetime
    shipped_at: Optional[datetime]
    arrived_at_pickup_point_at: Optional[datetime]
    picked_up_at: Optional[datetime]
    estimated_delivery_date: Optional[datetime]
    
    notes: Optional[str]


class DeliveryStatusUpdate(BaseModel):
    """Обновление статуса доставки"""
    status: DeliveryStatus = PydanticField(..., description="Новый статус")
    notes: Optional[str] = PydanticField(None, max_length=500, description="Примечания")


class DeliveryTrackingResponse(BaseModel):
    """Ответ с информацией об отслеживании доставки"""
    tracking_number: str
    status: str
    provider: str
    
    recipient_name: str
    delivery_city: Optional[str]
    pickup_point_name: Optional[str]
    
    created_at: datetime
    estimated_delivery_date: Optional[datetime]
    
    # История статусов
    status_history: list = []


class PickupPointLocation(BaseModel):
    """Информация о пункте выдачи (для будущего использования)"""
    id: str
    provider: str
    name: str
    address: str
    city: str
    zip_code: str
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    working_hours: Optional[str] = None
