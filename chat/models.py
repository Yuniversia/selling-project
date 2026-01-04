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
    anonymous_buyer_number: Optional[int] = Field(default=None)  # Номер анонимного покупателя (1, 2, 3...)
    is_hidden_by_buyer: bool = Field(default=False)  # Скрыт ли чат для покупателя
    is_hidden_by_seller: bool = Field(default=False)  # Скрыт ли чат для продавца
    support_joined: bool = Field(default=False)  # Присоединилась ли тех поддержка
    support_user_id: Optional[int] = Field(default=None, index=True)  # ID сотрудника поддержки
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)


class Message(SQLModel, table=True):
    """Сообщение в чате"""
    id: Optional[int] = Field(default=None, primary_key=True)
    chat_id: int = Field(index=True)  # FK будет создан через SQL миграцию
    sender_id: str = Field(index=True)  # ID пользователя или UUID анонима
    sender_is_registered: bool = Field(default=False)
    message_text: Optional[str] = Field(default=None, max_length=2000)
    message_type: str = Field(default="text")  # text, image, file, system
    file_url: Optional[str] = Field(default=None)  # URL файла в Cloudflare R2
    file_name: Optional[str] = Field(default=None)  # Имя файла
    file_size: Optional[int] = Field(default=None)  # Размер файла в байтах
    is_read: bool = Field(default=False)
    created_at: datetime = Field(default_factory=datetime.utcnow)


# Pydantic схемы для API
class MessageCreate(SQLModel):
    """Схема для создания сообщения"""
    message_text: Optional[str] = Field(default=None, max_length=2000)
    message_type: str = Field(default="text")
    file_url: Optional[str] = Field(default=None)
    file_name: Optional[str] = Field(default=None)
    file_size: Optional[int] = Field(default=None)
    sender_id: str
    sender_is_registered: bool = False


class MessageResponse(SQLModel):
    """Схема ответа с сообщением"""
    id: int
    chat_id: int
    sender_id: str
    sender_is_registered: bool
    message_text: Optional[str] = None
    message_type: str = "text"
    file_url: Optional[str] = None
    file_name: Optional[str] = None
    file_size: Optional[int] = None
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
    anonymous_buyer_number: Optional[int] = None
    is_hidden_by_buyer: bool = False
    is_hidden_by_seller: bool = False
    support_joined: bool = False
    support_user_id: Optional[int] = None
    created_at: datetime
    updated_at: datetime
    unread_count: int = 0
    last_message: Optional[str] = None
    last_message_time: Optional[datetime] = None


class ChatWithMessages(ChatResponse):
    """Чат со списком сообщений"""
    messages: List[MessageResponse] = []
