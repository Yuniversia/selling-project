# models.py

from sqlmodel import Field, SQLModel
from pydantic import BaseModel
from typing import Optional

# Модель пользователя для базы данных (SQLAlchemy/SQLModel)
class User(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    username: str = Field(index=True, unique=True, max_length=50)
    email: str = Field(index=True, unique=True, max_length=150)
    hashed_password: str

    name: Optional[str] = Field(default=None, index=False, unique=False, max_length=150)
    surname: Optional[str] = Field(default=None, index=False, unique=False, max_length=150)
    phone: Optional[str] = Field(default=None, index=False, max_length=12)
    posts_count: int = Field(default=0)

class PublicUser(BaseModel):
    username: str
    name: Optional[str]
    surname: Optional[str]
    email: str
    phone: Optional[str]
    created_date: str
    posts_count: int


# Схема для ввода данных при регистрации
class UserCreate(BaseModel):
    username: str
    email: str
    password: str

# Схема для ввода данных при аутентификации
class UserLogin(BaseModel):
    username: str
    password: str

# Схема для возвращаемого токена
class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"

# Схема для данных, хранящихся внутри JWT (payload)
class TokenData(BaseModel):
    username: Optional[str] = None