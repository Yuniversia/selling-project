# models.py

from sqlmodel import Field, SQLModel
from pydantic import BaseModel
from typing import Optional
from datetime import datetime

# ÐœÐ¾Ð´ÐµÐ»ÑŒ Ð¿Ð¾Ð»ÑŒÐ·Ð¾Ð²Ð°Ñ‚ÐµÐ»Ñ Ð´Ð»Ñ Ð±Ð°Ð·Ñ‹ Ð´Ð°Ð½Ð½Ñ‹Ñ… (SQLAlchemy/SQLModel)
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
    preferred_language: Optional[str] = Field(default=None, max_length=5)
    posts_count: int = Field(default=0)
    sells_count: int = Field(default=0)  # ÐšÐ¾Ð»Ð¸Ñ‡ÐµÑÑ‚Ð²Ð¾ Ð¿Ñ€Ð¾Ð´Ð°Ð¶
    rating: float = Field(default=5.0, ge=0, le=5)  # Ð ÐµÐ¹Ñ‚Ð¸Ð½Ð³ Ð¿Ð¾Ð»ÑŒÐ·Ð¾Ð²Ð°Ñ‚ÐµÐ»Ñ (0-5)
    created_at: datetime = Field(default_factory=datetime.utcnow)


class PublicUser(BaseModel):
    username: str
    email: str
    name: Optional[str] = None
    surname: Optional[str] = None

    status: str
    avatar_url: Optional[str] = None
    preferred_language: Optional[str] = None
    phone: Optional[str] = None
    created_date: datetime
    posts_count: int

    class Config:
        # Ð­Ñ‚Ð¾ Ð¿Ð¾Ð·Ð²Ð¾Ð»ÑÐµÑ‚ Pydantic Ñ‡Ð¸Ñ‚Ð°Ñ‚ÑŒ Ð´Ð°Ð½Ð½Ñ‹Ðµ Ð¸Ð· ORM-Ð¾Ð±ÑŠÐµÐºÑ‚Ð° SQLModel
        from_attributes = True


# Ð‘ÐµÐ·Ð¾Ð¿Ð°ÑÐ½Ð°Ñ Ð¼Ð¾Ð´ÐµÐ»ÑŒ Ð´Ð»Ñ Ð¿ÑƒÐ±Ð»Ð¸Ñ‡Ð½Ð¾Ð¹ Ð¸Ð½Ñ„Ð¾Ñ€Ð¼Ð°Ñ†Ð¸Ð¸ Ð¾ Ð¿Ñ€Ð¾Ð´Ð°Ð²Ñ†Ðµ (Ð±ÐµÐ· email Ð¸ phone)
class PublicUserMinimal(BaseModel):
    """
    ÐœÐ¸Ð½Ð¸Ð¼Ð°Ð»ÑŒÐ½Ð°Ñ Ð¿ÑƒÐ±Ð»Ð¸Ñ‡Ð½Ð°Ñ Ð¸Ð½Ñ„Ð¾Ñ€Ð¼Ð°Ñ†Ð¸Ñ Ð¾ Ð¿Ð¾Ð»ÑŒÐ·Ð¾Ð²Ð°Ñ‚ÐµÐ»Ðµ Ð´Ð»Ñ Ð¾Ñ‚Ð¾Ð±Ñ€Ð°Ð¶ÐµÐ½Ð¸Ñ Ð½Ð° ÑÑ‚Ñ€Ð°Ð½Ð¸Ñ†Ðµ Ñ‚Ð¾Ð²Ð°Ñ€Ð°.
    ÐÐ• Ð²ÐºÐ»ÑŽÑ‡Ð°ÐµÑ‚ Ñ‡ÑƒÐ²ÑÑ‚Ð²Ð¸Ñ‚ÐµÐ»ÑŒÐ½Ñ‹Ðµ Ð´Ð°Ð½Ð½Ñ‹Ðµ: email, phone, hashed_password.
    """
    username: str
    name: Optional[str] = None
    surname: Optional[str] = None
    avatar_url: Optional[str] = None
    preferred_language: Optional[str] = None
    rating: float
    posts_count: int
    sells_count: int
    joined_date: str  # Ð¤Ð¾Ñ€Ð¼Ð°Ñ‚Ð¸Ñ€Ð¾Ð²Ð°Ð½Ð½Ð°Ñ Ð´Ð°Ñ‚Ð° Ð² Ð²Ð¸Ð´Ðµ ÑÑ‚Ñ€Ð¾ÐºÐ¸

    class Config:
        from_attributes = True


# Ð¡Ñ…ÐµÐ¼Ð° Ð´Ð»Ñ Ð²Ð²Ð¾Ð´Ð° Ð´Ð°Ð½Ð½Ñ‹Ñ… Ð¿Ñ€Ð¸ Ñ€ÐµÐ³Ð¸ÑÑ‚Ñ€Ð°Ñ†Ð¸Ð¸
class UserCreate(BaseModel):
    username: str
    email: str
    password: Optional[str] # Ð˜Ð¼ÐµÐµÑ‚ Ð²Ð¾Ð·Ð¼Ð¾Ð¶Ð½Ð¾ÑÑ‚ÑŒ None Ð´Ð»Ñ Ñ€ÐµÐ³Ð¸ÑÑ‚Ñ€Ð°Ñ†Ð¸Ð¸ Ñ‡ÐµÑ€ÐµÐ· o2auth
    name: Optional[str] = None  # Ð˜Ð¼Ñ Ð¿Ð¾Ð»ÑŒÐ·Ð¾Ð²Ð°Ñ‚ÐµÐ»Ñ
    surname: Optional[str] = None  # Ð¤Ð°Ð¼Ð¸Ð»Ð¸Ñ Ð¿Ð¾Ð»ÑŒÐ·Ð¾Ð²Ð°Ñ‚ÐµÐ»Ñ
    avatar_url: Optional[str] = None
    preferred_language: Optional[str] = None  # URL Ð°Ð²Ð°Ñ‚Ð°Ñ€Ð° (Ð¸Ð· Google OAuth)

# Ð¡Ñ…ÐµÐ¼Ð° Ð´Ð»Ñ Ð²Ð²Ð¾Ð´Ð° Ð´Ð°Ð½Ð½Ñ‹Ñ… Ð¿Ñ€Ð¸ Ð°ÑƒÑ‚ÐµÐ½Ñ‚Ð¸Ñ„Ð¸ÐºÐ°Ñ†Ð¸Ð¸
class UserLogin(BaseModel):
    username_or_email: str
    password: str

# Ð¡Ñ…ÐµÐ¼Ð° Ð´Ð»Ñ Ð¾Ð±Ð½Ð¾Ð²Ð»ÐµÐ½Ð¸Ñ Ð¿Ñ€Ð¾Ñ„Ð¸Ð»Ñ
class UserUpdate(BaseModel):
    name: Optional[str] = None
    surname: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None
    avatar_url: Optional[str] = None
    preferred_language: Optional[str] = None

# Ð¡Ñ…ÐµÐ¼Ð° Ð´Ð»Ñ Ð²Ð¾Ð·Ð²Ñ€Ð°Ñ‰Ð°ÐµÐ¼Ð¾Ð³Ð¾ Ñ‚Ð¾ÐºÐµÐ½Ð°
class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"

# Ð¡Ñ…ÐµÐ¼Ð° Ð´Ð»Ñ Ð´Ð°Ð½Ð½Ñ‹Ñ…, Ñ…Ñ€Ð°Ð½ÑÑ‰Ð¸Ñ…ÑÑ Ð²Ð½ÑƒÑ‚Ñ€Ð¸ JWT (payload)
class TokenData(BaseModel):
    username: Optional[str] = None