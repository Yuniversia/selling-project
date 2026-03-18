from datetime import datetime
from enum import Enum
from typing import Any, Dict, Optional

from pydantic import BaseModel, Field as PydanticField
from sqlalchemy import JSON, Column
from sqlmodel import Field, SQLModel


class PaymentStatus(str, Enum):
    REQUIRES_PAYMENT_METHOD = "requires_payment_method"
    REQUIRES_ACTION = "requires_action"
    PROCESSING = "processing"
    SUCCEEDED = "succeeded"
    CANCELED = "canceled"
    FAILED = "failed"
    PARTIALLY_REFUNDED = "partially_refunded"
    REFUNDED = "refunded"


class PaymentProvider(str, Enum):
    STRIPE = "stripe"


class Payment(SQLModel, table=True):
    __tablename__ = "payments"

    id: Optional[int] = Field(default=None, primary_key=True)

    order_id: Optional[int] = Field(default=None, index=True)
    post_id: Optional[int] = Field(default=None, index=True)
    buyer_id: Optional[int] = Field(default=None, index=True)
    seller_id: Optional[int] = Field(default=None, index=True)

    amount_cents: int = Field(ge=1)
    currency: str = Field(default="eur", max_length=10, index=True)
    description: Optional[str] = Field(default=None, max_length=500)

    status: str = Field(default=PaymentStatus.REQUIRES_PAYMENT_METHOD.value, index=True, max_length=50)
    provider: str = Field(default=PaymentProvider.STRIPE.value, max_length=20)

    provider_payment_intent_id: Optional[str] = Field(default=None, index=True, max_length=255)
    provider_checkout_session_id: Optional[str] = Field(default=None, index=True, max_length=255)
    provider_charge_id: Optional[str] = Field(default=None, index=True, max_length=255)
    client_secret: Optional[str] = Field(default=None, max_length=500)

    idempotency_key: Optional[str] = Field(default=None, index=True, max_length=255)
    request_id: Optional[str] = Field(default=None, max_length=255)

    payment_metadata: Dict[str, Any] = Field(default_factory=dict, sa_column=Column("metadata", JSON))
    last_error: Optional[str] = Field(default=None, max_length=2000)

    created_at: datetime = Field(default_factory=datetime.utcnow, index=True)
    updated_at: datetime = Field(default_factory=datetime.utcnow, index=True)
    paid_at: Optional[datetime] = Field(default=None, index=True)
    refunded_at: Optional[datetime] = Field(default=None, index=True)


class PaymentWebhookEvent(SQLModel, table=True):
    __tablename__ = "payment_webhook_events"

    id: Optional[int] = Field(default=None, primary_key=True)
    provider_event_id: str = Field(index=True, unique=True, max_length=255)
    event_type: str = Field(max_length=255)
    payload: Dict[str, Any] = Field(default_factory=dict, sa_column=Column(JSON))
    processed_at: datetime = Field(default_factory=datetime.utcnow, index=True)


class PaymentIntentCreateData(BaseModel):
    amount_cents: int = PydanticField(..., ge=1, description="Amount in cents")
    currency: str = PydanticField(default="eur", min_length=3, max_length=10)
    order_id: Optional[int] = None
    post_id: Optional[int] = None
    seller_id: Optional[int] = None
    description: Optional[str] = PydanticField(default=None, max_length=500)
    confirm: bool = False
    test_payment_method: Optional[str] = PydanticField(default=None, max_length=100)
    metadata: Dict[str, Any] = PydanticField(default_factory=dict)


class PaymentIntentResponse(BaseModel):
    id: int
    status: str
    provider: str
    provider_payment_intent_id: Optional[str] = None
    provider_checkout_session_id: Optional[str] = None
    client_secret: Optional[str] = None
    amount_cents: int
    currency: str
    order_id: Optional[int] = None
    post_id: Optional[int] = None
    buyer_id: Optional[int] = None
    seller_id: Optional[int] = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class RefundCreateData(BaseModel):
    amount_cents: Optional[int] = PydanticField(default=None, ge=1)
    reason: Optional[str] = PydanticField(default=None, max_length=100)
    metadata: Dict[str, Any] = PydanticField(default_factory=dict)


class StripeWebhookPayload(BaseModel):
    id: str
    type: str
    data: Dict[str, Any]


class CheckoutSessionCreateData(BaseModel):
    amount_cents: int = PydanticField(..., ge=1)
    currency: str = PydanticField(default="eur", min_length=3, max_length=10)
    order_id: int
    post_id: Optional[int] = None
    seller_id: Optional[int] = None
    buyer_email: Optional[str] = None
    product_name: str = PydanticField(default="Order payment", max_length=255)
    description: Optional[str] = PydanticField(default=None, max_length=500)
    success_url: str = PydanticField(..., min_length=8, max_length=2000)
    cancel_url: str = PydanticField(..., min_length=8, max_length=2000)
    metadata: Dict[str, Any] = PydanticField(default_factory=dict)


class CheckoutSessionResponse(BaseModel):
    payment_id: int
    checkout_session_id: str
    checkout_url: str
    order_id: int
    status: str


class CheckoutSessionStatusResponse(BaseModel):
    payment_id: Optional[int] = None
    checkout_session_id: str
    payment_status: str
    status: str
    paid: bool
    order_id: Optional[int] = None
    provider_payment_intent_id: Optional[str] = None
