"""Models for Web Push Notifications"""
from sqlmodel import SQLModel, Field
from datetime import datetime
from typing import Optional


class PushSubscription(SQLModel, table=True):
    """User's push notification subscription"""
    __tablename__ = "push_subscriptions"
    
    id: Optional[int] = Field(default=None, primary_key=True)
    user_id: str = Field(index=True)  # Can be registered user ID or anonymous UUID
    endpoint: str = Field(index=True, unique=True)  # Push service endpoint URL
    p256dh: str  # Public key for encryption
    auth: str  # Authentication secret
    is_active: bool = Field(default=True)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)


class PushSubscriptionCreate(SQLModel):
    """Schema for creating a push subscription"""
    endpoint: str
    keys: dict  # Contains p256dh and auth


class PushSubscriptionResponse(SQLModel):
    """Schema for push subscription response"""
    id: int
    user_id: str
    is_active: bool
    created_at: datetime
