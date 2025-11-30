from sqlmodel import SQLModel, Field, Relationship
from datetime import datetime
from typing import Optional, List
from uuid import UUID, uuid4


class Chat(SQLModel, table=True):
    """Комната чата между покупателем и продавцом по конкретному объявлению"""
    id: Optional[int] = Field(default=None, primary_key=True)
    iphone_id: int = Field(index=True)  # FK будет создан через SQL миграцию
    seller_id: int = Field(index=True)  # FK будет создан через SQL миграцию
    buyer_id: Optional[str] = Field(default=None, index=True)  # ID или UUID покупателя
    buyer_is_registered: bool = Field(default=False)  # Зарегистрирован ли покупатель
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)


class Message(SQLModel, table=True):
    """Сообщение в чате"""
    id: Optional[int] = Field(default=None, primary_key=True)
    chat_id: int = Field(index=True)  # FK будет создан через SQL миграцию
    sender_id: str = Field(index=True)  # ID пользователя или UUID анонима
    sender_is_registered: bool = Field(default=False)
    message_text: str = Field(max_length=2000)
    is_read: bool = Field(default=False)
    created_at: datetime = Field(default_factory=datetime.utcnow)


# Pydantic схемы для API
class MessageCreate(SQLModel):
    """Схема для создания сообщения"""
    message_text: str = Field(max_length=2000)
    sender_id: str
    sender_is_registered: bool = False


class MessageResponse(SQLModel):
    """Схема ответа с сообщением"""
    id: int
    chat_id: int
    sender_id: str
    sender_is_registered: bool
    message_text: str
    is_read: bool
    created_at: datetime


class ChatCreate(SQLModel):
    """Схема для создания чата"""
    iphone_id: int
    seller_id: int
    buyer_id: str
    buyer_is_registered: bool = False


class ChatResponse(SQLModel):
    """Схема ответа с чатом"""
    id: int
    iphone_id: int
    seller_id: int
    buyer_id: str
    buyer_is_registered: bool
    created_at: datetime
    updated_at: datetime
    unread_count: int = 0
    last_message: Optional[str] = None
    last_message_time: Optional[datetime] = None


class ChatWithMessages(ChatResponse):
    """Чат со списком сообщений"""
    messages: List[MessageResponse] = []
