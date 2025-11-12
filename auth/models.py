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