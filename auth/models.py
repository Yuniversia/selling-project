# models.py

from sqlmodel import Field, SQLModel
from pydantic import BaseModel
from typing import Optional
from datetime import datetime

# Модель пользователя для базы данных (SQLAlchemy/SQLModel)
class User(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    username: str = Field(index=True, unique=True, max_length=50)
    email: str = Field(index=True, unique=True, max_length=150)
    hashed_password: Optional[str]
    status: str = Field(default="active", index=True)
    user_type: str = Field(default="regular", index=True)  # regular, admin, suport, etc.

    avatar_url: Optional[str] = Field(default=None)
    name: Optional[str] = Field(default=None, max_length=150)
    surname: Optional[str] = Field(default=None, max_length=150)
    phone: Optional[str] = Field(default=None, max_length=20)
    posts_count: int = Field(default=0)
    sells_count: int = Field(default=0)  # Количество продаж
    rating: float = Field(default=5.0, ge=0, le=5)  # Рейтинг пользователя (0-5)
    created_at: datetime = Field(default_factory=datetime.utcnow)


class PublicUser(BaseModel):
    username: str
    email: str
    name: Optional[str] = None
    surname: Optional[str] = None

    status: str
    avatar_url: Optional[str] = None
    phone: Optional[str] = None
    created_date: datetime
    posts_count: int

    class Config:
        # Это позволяет Pydantic читать данные из ORM-объекта SQLModel
        from_attributes = True


# Схема для ввода данных при регистрации
class UserCreate(BaseModel):
    username: str
    email: str
    password: Optional[str] # Имеет возможность None для регистрации через o2auth
    name: Optional[str] = None  # Имя пользователя
    surname: Optional[str] = None  # Фамилия пользователя
    avatar_url: Optional[str] = None  # URL аватара (из Google OAuth)

# Схема для ввода данных при аутентификации
class UserLogin(BaseModel):
    username_or_email: str
    password: str

# Схема для обновления профиля
class UserUpdate(BaseModel):
    name: Optional[str] = None
    surname: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None
    avatar_url: Optional[str] = None

# Схема для возвращаемого токена
class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"

# Схема для данных, хранящихся внутри JWT (payload)
class TokenData(BaseModel):
    username: Optional[str] = None