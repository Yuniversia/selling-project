# models.py - ИСПРАВЛЕНО

from sqlmodel import Field, SQLModel
from pydantic import BaseModel, Field as PydanticField, field_validator
from typing import Optional
from datetime import datetime
from enum import Enum

# --- Модель Pydantic для входных данных (для POST запроса) ---
# Эта модель используется для валидации данных, пришедших из формы/JSON.
class IphonePostData(BaseModel):
    # IMEI: Обязательно 15 цифр, передается как строка.
    imei: str = PydanticField(
        ..., 
        min_length=15, 
        max_length=15, 
        description="IMEI телефона (15 цифр)"
    )
    # Batery: Целое число от 0 до 100.
    batery: int = PydanticField(
        ..., 
        ge=0, # minimum value 0
        le=100, # maximum value 100
        description="Уровень заряда батареи (0-100)"
    )

    # Валидатор для IMEI: убеждаемся, что строка состоит только из цифр
    @field_validator('imei')
    @classmethod
    def validate_imei_digits(cls, v: str):
        if not v.isdigit():
            raise ValueError('IMEI должен содержать только цифры')
        return v
    
    description: Optional[str] = None
    price: Optional[float] = PydanticField(default=None, description="Цена iPhone")
    condition: Optional[str] = PydanticField(default=None, description="Состояние устройства (Новый, Как новый, Небольшие дефекты, С дефектом, На запчасти)")
    
    # Комплектация
    has_original_box: bool = PydanticField(default=False, description="Оригинальная коробка")
    has_charger: bool = PydanticField(default=False, description="Зарядный блок")
    has_cable: bool = PydanticField(default=False, description="Кабель")
    has_receipt: bool = PydanticField(default=False, description="Чек о покупке")
    has_warranty: bool = PydanticField(default=False, description="Гарантия") 
    
# --- Модель SQLModel для базы данных ---
class Iphone(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    
    # Автор и статус поста
    author_id: int = Field(index=True)  # ID пользователя из auth-сервиса
    active: bool = Field(default=True, index=True)  # Активен ли пост
    view_count: int = Field(default=0)  # Количество просмотров
    price: Optional[float] = Field(default=None)

    # Поля, которые приходят из запроса (IphonePostData)
    imei: str = Field(max_length=15) # Изменено на str, чтобы хранить ведущие нули, если нужно
    batery: int = Field(index=True)
    description: Optional[str] = Field(default=None, max_length=1000)
    condition : Optional[str] = Field(default=None, max_length=100)  # Новое поле для состояния телефона
    
    # Поля, которые, вероятно, заполняются в post_service.py
    serial_number: Optional[str] = Field(max_length=20, default=None) # Изменено на str
    model: Optional[str] = Field(max_length=50, default=None)
    color: Optional[str] = Field(index=True, max_length=150, default=None)
    memory: Optional[int] = Field(index=True, default=None)  # Память в GB (64, 128, 256, 512, 1024)
    activated: Optional[bool] = Field(default=None)
    icloud_pair: Optional[bool] = Field(default=None)
    fmi: Optional[bool] = Field(default=None)
    simlock: Optional[bool] = Field(default=None)

    # Комплектация (Accessories)
    has_original_box: bool = Field(default=False)
    has_charger: bool = Field(default=False)
    has_cable: bool = Field(default=False)
    has_receipt: bool = Field(default=False)
    has_warranty: bool = Field(default=False)

    images_url: Optional[str] = Field(default=None)
    created_at: datetime = Field(default_factory=datetime.utcnow)

# Модель для GET ответа (необязательно, но полезно)
class IphonePublic(BaseModel):
    id: int
    author_id: int
    active: bool
    view_count: int
    price: Optional[float]
    imei: str
    batery: int
    condition: Optional[str]
    model: Optional[str]
    memory: Optional[int]  # Память в GB
    color: Optional[str]
    images_url: Optional[str]
    description: Optional[str]

    # Поля от мошеничествества
    activated: Optional[bool] = Field(default=None)
    icloud_pair: Optional[bool] = Field(default=None)
    fmi: Optional[bool] = Field(default=None)
    simlock: Optional[bool] = Field(default=None)

    # Комплектация
    has_original_box: bool = False
    has_charger: bool = False
    has_cable: bool = False
    has_receipt: bool = False
    has_warranty: bool = False
    created_at: datetime


# --- Модель для уникальных просмотров ---
class PostView(SQLModel, table=True):
    """Таблица для отслеживания уникальных просмотров постов"""
    id: Optional[int] = Field(default=None, primary_key=True)
    post_id: int = Field(foreign_key="iphone.id", index=True)
    viewer_id: Optional[int] = Field(default=None, index=True)  # ID авторизованного пользователя (может быть None)
    viewer_ip: str = Field(max_length=45, index=True)  # IP адрес (IPv4 или IPv6)
    user_agent: Optional[str] = Field(default=None, max_length=500)  # User-Agent браузера
    viewed_at: datetime = Field(default_factory=datetime.utcnow)


# --- Enum для причин жалоб ---
class ReportReason(str, Enum):
    FRAUD = "Мошенничество"
    FAKE_DEVICE = "Поддельное устройство"
    STOLEN = "Украденный телефон"
    WRONG_INFO = "Неверная информация"
    DUPLICATE = "Дубликат объявления"
    INAPPROPRIATE = "Неприемлемый контент"
    SPAM = "Спам"
    OTHER = "Другое"


# --- Модель для жалоб ---
class PostReport(SQLModel, table=True):
    """Таблица для жалоб на посты"""
    id: Optional[int] = Field(default=None, primary_key=True)
    post_id: int = Field(foreign_key="iphone.id", index=True)
    reporter_id: Optional[int] = Field(default=None, index=True)  # ID пользователя, подавшего жалобу
    reporter_ip: str = Field(max_length=45)  # IP адрес (для анонимных жалоб)
    reason: str = Field(max_length=50)  # Причина из ReportReason
    details: Optional[str] = Field(default=None, max_length=500)  # Дополнительные детали
    status: str = Field(default="pending", max_length=20)  # pending, reviewed, resolved, rejected
    created_at: datetime = Field(default_factory=datetime.utcnow)
    reviewed_at: Optional[datetime] = Field(default=None)
    reviewed_by: Optional[int] = Field(default=None)  # ID модератора, рассмотревшего жалобу


# --- Pydantic модели для API ---
class ReportCreate(BaseModel):
    """Модель для создания жалобы"""
    post_id: int = PydanticField(..., description="ID объявления")
    reason: ReportReason = PydanticField(..., description="Причина жалобы")
    details: Optional[str] = PydanticField(None, max_length=500, description="Дополнительные детали")


class ReportResponse(BaseModel):
    """Модель ответа после создания жалобы"""
    id: int
    post_id: int
    reason: str
    status: str
    created_at: datetime


# =============================================================================
# МОДЕЛИ ДЛЯ СИСТЕМЫ ПОКУПКИ И ДОСТАВКИ
# =============================================================================

# --- Enum для способов доставки ---
class DeliveryMethod(str, Enum):
    PICKUP = "pickup"  # Забрать лично
    DPD = "dpd"  # Доставка DPD
    OMNIVA = "omniva"  # Доставка Omniva


# --- Enum для статусов заказа ---
class OrderStatus(str, Enum):
    PENDING_PAYMENT = "pending_payment"  # Ожидает оплаты
    PAID = "paid"  # Оплачен
    PROCESSING = "processing"  # В обработке
    SHIPPED = "shipped"  # Отправлен
    DELIVERED = "delivered"  # Доставлен в пакомат/на адрес
    COMPLETED = "completed"  # Получен и подтвержден покупателем
    CANCELLED = "cancelled"  # Отменен
    REFUNDED = "refunded"  # Возврат средств


# --- Модель заказа в БД ---
class Order(SQLModel, table=True):
    """Таблица заказов"""
    id: Optional[int] = Field(default=None, primary_key=True)
    
    # Связи
    post_id: int = Field(foreign_key="iphone.id", index=True)  # Какой товар куплен
    buyer_id: Optional[int] = Field(default=None, index=True)  # ID покупателя (None для анонимов)
    seller_id: int = Field(index=True)  # ID продавца
    
    # Финансы
    price: float = Field(description="Цена товара на момент покупки")
    
    # Способ доставки
    delivery_method: str = Field(max_length=20)  # pickup, dpd, omniva
    
    # Данные покупателя
    buyer_first_name: str = Field(max_length=100)
    buyer_last_name: str = Field(max_length=100)
    buyer_email: str = Field(max_length=255, index=True)
    buyer_phone: str = Field(max_length=20)
    
    # Адрес доставки (заполняется только если не pickup)
    delivery_address: Optional[str] = Field(default=None, max_length=500)
    delivery_city: Optional[str] = Field(default=None, max_length=100)
    delivery_zip: Optional[str] = Field(default=None, max_length=20)
    delivery_country: Optional[str] = Field(default=None, max_length=100)
    
    # Код для получения из пакомата (генерируется после оплаты)
    pickup_code: Optional[str] = Field(default=None, max_length=10)
    
    # Трекинг-номер для отслеживания доставки
    tracking_number: Optional[str] = Field(default=None, max_length=100)
    
    # Статус заказа
    status: str = Field(default="pending_payment", max_length=20, index=True)
    
    # Временные метки
    created_at: datetime = Field(default_factory=datetime.utcnow)
    paid_at: Optional[datetime] = Field(default=None)
    shipped_at: Optional[datetime] = Field(default=None)
    delivered_at: Optional[datetime] = Field(default=None)
    completed_at: Optional[datetime] = Field(default=None)
    
    # Подтверждение получения
    confirmed_by_buyer: bool = Field(default=False)
    rejected_by_buyer: bool = Field(default=False)  # Отклонено покупателем
    
    # Отзыв
    review_rating: Optional[int] = Field(default=None, ge=0, le=5)  # Оценка 0-5
    review_text: Optional[str] = Field(default=None, max_length=500)  # Текст отзыва


# --- Pydantic модели для создания заказа ---
class OrderCreate(BaseModel):
    """Данные для создания заказа"""
    post_id: int = PydanticField(..., description="ID товара")
    delivery_method: DeliveryMethod = PydanticField(..., description="Способ доставки")
    
    # Данные покупателя
    first_name: str = PydanticField(..., min_length=2, max_length=100)
    last_name: str = PydanticField(..., min_length=2, max_length=100)
    email: str = PydanticField(..., description="Email для отправки кода")
    phone: str = PydanticField(..., min_length=8, max_length=20)
    
    # Адрес доставки (обязателен для DPD и Omniva)
    delivery_address: Optional[str] = PydanticField(None, max_length=500)
    delivery_city: Optional[str] = PydanticField(None, max_length=100)
    delivery_zip: Optional[str] = PydanticField(None, max_length=20)
    delivery_country: Optional[str] = PydanticField(default="Latvia", max_length=100)


class OrderResponse(BaseModel):
    """Ответ после создания заказа - БЕЗ ЛИЧНЫХ ДАННЫХ"""
    id: int
    post_id: int
    status: str
    delivery_method: str
    price: float
    created_at: datetime
    
    # Для покупателя - только его заказ
    buyer_first_name: Optional[str] = None
    buyer_last_name: Optional[str] = None
    
    # Для продавца - только имя покупателя (без email/phone/адреса)
    buyer_name: Optional[str] = None
    
    # Временные метки
    paid_at: Optional[datetime] = None
    shipped_at: Optional[datetime] = None
    delivered_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    
    # Отзыв (если есть)
    review_rating: Optional[int] = None
    review_text: Optional[str] = None


class OrderConfirmation(BaseModel):
    """Подтверждение получения товара + отзыв"""
    order_id: int = PydanticField(..., description="ID заказа")
    accepted: bool = PydanticField(..., description="Принять (True) или отклонить (False)")
    rating: int = PydanticField(..., ge=0, le=5, description="Оценка от 0 до 5 звёзд")
    review_text: Optional[str] = PydanticField(None, max_length=500, description="Текст отзыва")


# =============================================================================
# МОДЕЛЬ USER (для обновления статистики продавца)
# =============================================================================

class User(SQLModel, table=True):
    """Копия модели User из auth-service для обновления статистики"""
    id: Optional[int] = Field(default=None, primary_key=True)
    username: str = Field(index=True, unique=True, max_length=50)
    email: str = Field(index=True, unique=True, max_length=150)
    hashed_password: Optional[str]
    status: str = Field(default="active", index=True)
    user_type: str = Field(default="regular", index=True)
    
    avatar_url: Optional[str] = Field(default=None)
    name: Optional[str] = Field(default=None, max_length=150)
    surname: Optional[str] = Field(default=None, max_length=150)
    phone: Optional[str] = Field(default=None, max_length=20)
    posts_count: int = Field(default=0)
    sells_count: int = Field(default=0)  # Количество успешных продаж
    rating: float = Field(default=5.0, ge=0, le=5)  # Рейтинг продавца
    created_at: datetime = Field(default_factory=datetime.utcnow)