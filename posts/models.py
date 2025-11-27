# models.py - ИСПРАВЛЕНО

from sqlmodel import Field, SQLModel
from pydantic import BaseModel, Field as PydanticField, field_validator
from typing import Optional
from datetime import datetime

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

    # Поля, которые приходят из запроса (IphonePostData)
    imei: str = Field(max_length=15) # Изменено на str, чтобы хранить ведущие нули, если нужно
    batery: int = Field(index=True)
    description: Optional[str] = Field(default=None, max_length=1000)
    
    # Поля, которые, вероятно, заполняются в post_service.py
    serial_number: Optional[str] = Field(max_length=20, default=None) # Изменено на str
    model: Optional[str] = Field(max_length=50, default=None)
    color: Optional[str] = Field(index=True, max_length=150, default=None)
    memory: Optional[str] = Field(index=True, default=None)
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
    imei: str
    batery: int
    model: Optional[str]
    memory: Optional[str]
    color: Optional[str]
    images_url: Optional[str]
    description: Optional[str]
    # Комплектация
    has_original_box: bool = False
    has_charger: bool = False
    has_cable: bool = False
    has_receipt: bool = False
    has_warranty: bool = False
    created_at: datetime