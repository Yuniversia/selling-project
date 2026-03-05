# models.py - Модели для notification service

from sqlmodel import Field, SQLModel
from pydantic import BaseModel, EmailStr
from typing import Optional
from datetime import datetime
from enum import Enum


# =============================================================================
# ENUMS
# =============================================================================

class NotificationType(str, Enum):
    """Типы уведомлений"""
    ORDER_CREATED = "order_created"  # Заказ создан
    ORDER_PAID = "order_paid"  # Заказ оплачен
    ORDER_SHIPPED = "order_shipped"  # Заказ отправлен
    ORDER_DELIVERED = "order_delivered"  # Заказ доставлен
    ORDER_COMPLETED = "order_completed"  # Заказ завершен
    ORDER_REVIEW_REQUEST = "order_review_request"  # Запрос на отзыв


class NotificationChannel(str, Enum):
    """Каналы отправки"""
    EMAIL = "email"
    SMS = "sms"
    BOTH = "both"


class NotificationStatus(str, Enum):
    """Статусы доставки уведомлений"""
    PENDING = "pending"
    SENT = "sent"
    FAILED = "failed"
    RETRY = "retry"


# =============================================================================
# DATABASE MODELS
# =============================================================================

class NotificationLog(SQLModel, table=True):
    """История отправленных уведомлений"""
    id: Optional[int] = Field(default=None, primary_key=True)
    
    # Тип уведомления
    notification_type: str = Field(index=True, max_length=50)
    channel: str = Field(max_length=10)  # email, sms, both
    
    # Получатель
    recipient_email: Optional[str] = Field(default=None, max_length=255, index=True)
    recipient_phone: Optional[str] = Field(default=None, max_length=20, index=True)
    recipient_name: Optional[str] = Field(default=None, max_length=200)
    
    # Связь с заказом
    order_id: Optional[int] = Field(default=None, index=True)
    
    # Содержимое
    subject: Optional[str] = Field(default=None, max_length=500)
    message: Optional[str] = Field(default=None)
    
    # Статус доставки
    status: str = Field(default="pending", max_length=20, index=True)
    error_message: Optional[str] = Field(default=None, max_length=1000)
    retry_count: int = Field(default=0)
    
    # Временные метки
    created_at: datetime = Field(default_factory=datetime.utcnow)
    sent_at: Optional[datetime] = Field(default=None)
    
    # SendPulse response
    external_id: Optional[str] = Field(default=None, max_length=255)  # ID из SendPulse API


class NotificationTemplate(SQLModel, table=True):
    """Шаблоны уведомлений"""
    id: Optional[int] = Field(default=None, primary_key=True)
    
    # Тип уведомления
    notification_type: str = Field(unique=True, index=True, max_length=50)
    
    # Шаблоны для email
    email_subject: Optional[str] = Field(default=None, max_length=500)
    email_body: Optional[str] = Field(default=None)  # HTML поддерживается
    
    # Шаблон для SMS
    sms_text: Optional[str] = Field(default=None, max_length=500)
    
    # Метаданные
    description: Optional[str] = Field(default=None, max_length=500)
    is_active: bool = Field(default=True)
    
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)


# =============================================================================
# PYDANTIC MODELS FOR API
# =============================================================================

class OrderNotificationData(BaseModel):
    """Данные для уведомления о заказе"""
    order_id: int
    
    # Данные продавца
    seller_name: str
    seller_email: Optional[EmailStr] = None
    seller_phone: Optional[str] = None
    
    # Данные покупателя
    buyer_name: str
    buyer_email: EmailStr
    buyer_phone: Optional[str] = None
    
    # Детали заказа
    product_name: str
    product_model: Optional[str] = None
    order_price: float
    delivery_method: str
    tracking_url: Optional[str] = None
    review_url: Optional[str] = None


class SendNotificationRequest(BaseModel):
    """Запрос на отправку уведомления"""
    notification_type: NotificationType
    channel: NotificationChannel
    order_data: OrderNotificationData


class SendNotificationResponse(BaseModel):
    """Ответ после отправки уведомления"""
    success: bool
    message: str
    notification_ids: list[int] = []
    errors: Optional[list[str]] = None


class NotificationHistoryResponse(BaseModel):
    """История уведомлений"""
    id: int
    notification_type: str
    channel: str
    recipient_email: Optional[str]
    recipient_phone: Optional[str]
    status: str
    created_at: datetime
    sent_at: Optional[datetime]
    error_message: Optional[str]
