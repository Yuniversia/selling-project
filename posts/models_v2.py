from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field as PydanticField, field_validator
from sqlalchemy import Column, JSON
from sqlmodel import Field, SQLModel


class ProductStatus(str, Enum):
    CREATING = "creating"
    PUBLISHED = "published"
    PENDING_VERIFICATION = "pending_verification"
    REJECTED = "rejected"


class Product(SQLModel, table=True):
    __tablename__ = "products"

    id: Optional[int] = Field(default=None, primary_key=True)
    category_id: int = Field(index=True)
    seller_id: int = Field(index=True)
    price: float = Field(ge=0)
    title: Optional[str] = Field(default=None, max_length=255)
    description: Optional[str] = Field(default=None, max_length=2000)
    status: str = Field(default=ProductStatus.CREATING.value, index=True, max_length=40)
    active: bool = Field(default=True, index=True)
    view_count: int = Field(default=0)
    images_url: List[str] = Field(default_factory=list, sa_column=Column(JSON))
    attributes: Dict[str, Any] = Field(default_factory=dict, sa_column=Column(JSON))
    created_at: datetime = Field(default_factory=datetime.utcnow, index=True)
    updated_at: datetime = Field(default_factory=datetime.utcnow, index=True)


class PostCreateData(BaseModel):
    category_id: int = PydanticField(..., ge=1)
    price: float = PydanticField(..., ge=0)
    title: Optional[str] = PydanticField(default=None, max_length=255)
    description: Optional[str] = PydanticField(default=None, max_length=2000)
    attributes: Dict[str, Any] = PydanticField(default_factory=dict)

    @field_validator("attributes")
    @classmethod
    def validate_data_source(cls, value: Dict[str, Any]) -> Dict[str, Any]:
        data_source = value.get("data_source")
        if not isinstance(data_source, dict):
            raise ValueError("attributes.data_source is required")

        origin = data_source.get("origin")
        verified = data_source.get("verified")
        if not origin:
            raise ValueError("attributes.data_source.origin is required")
        if not isinstance(verified, bool):
            raise ValueError("attributes.data_source.verified must be boolean")

        if not data_source.get("updated_at"):
            data_source["updated_at"] = datetime.utcnow().isoformat()
            value["data_source"] = data_source

        return value


class ProductPublic(BaseModel):
    id: int
    category_id: int
    seller_id: int
    price: float
    title: Optional[str]
    description: Optional[str]
    status: str
    active: bool
    view_count: int
    images_url: List[str]
    attributes: Dict[str, Any]
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class PostUpdateData(BaseModel):
    status: Optional[ProductStatus] = None
    active: Optional[bool] = None
    price: Optional[float] = PydanticField(default=None, ge=0)
    title: Optional[str] = PydanticField(default=None, max_length=255)
    description: Optional[str] = PydanticField(default=None, max_length=2000)


class PostView(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    post_id: int = Field(foreign_key="products.id", index=True)
    viewer_id: Optional[int] = Field(default=None, index=True)
    viewer_ip: str = Field(max_length=45, index=True)
    user_agent: Optional[str] = Field(default=None, max_length=500)
    viewed_at: datetime = Field(default_factory=datetime.utcnow)


class ReportReason(str, Enum):
    FRAUD = "Мошенничество"
    FAKE_DEVICE = "Поддельное устройство"
    STOLEN = "Украденный телефон"
    WRONG_INFO = "Неверная информация"
    DUPLICATE = "Дубликат объявления"
    INAPPROPRIATE = "Неприемлемый контент"
    SPAM = "Спам"
    OTHER = "Другое"


class PostReport(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    post_id: int = Field(foreign_key="products.id", index=True)
    reporter_id: Optional[int] = Field(default=None, index=True)
    reporter_ip: str = Field(max_length=45)
    reason: str = Field(max_length=50)
    details: Optional[str] = Field(default=None, max_length=500)
    status: str = Field(default="pending", max_length=20)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    reviewed_at: Optional[datetime] = Field(default=None)
    reviewed_by: Optional[int] = Field(default=None)


class ReportCreate(BaseModel):
    post_id: int = PydanticField(..., description="ID объявления")
    reason: ReportReason = PydanticField(..., description="Причина жалобы")
    details: Optional[str] = PydanticField(None, max_length=500, description="Дополнительные детали")


class ReportResponse(BaseModel):
    id: int
    post_id: int
    reason: str
    status: str
    created_at: datetime


class DeliveryMethod(str, Enum):
    PICKUP = "pickup"
    DPD = "dpd"
    OMNIVA = "omniva"


class OrderStatus(str, Enum):
    PENDING_PAYMENT = "pending_payment"
    PAID = "paid"
    PROCESSING = "processing"
    SHIPPED = "shipped"
    DELIVERED = "delivered"
    COMPLETED = "completed"
    CANCELLED = "cancelled"
    REFUNDED = "refunded"


class Order(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)

    post_id: int = Field(foreign_key="products.id", index=True)
    buyer_id: Optional[int] = Field(default=None, index=True)
    seller_id: int = Field(index=True)

    price: float = Field(description="Цена товара на момент покупки")

    delivery_method: str = Field(max_length=20)

    buyer_first_name: str = Field(max_length=100)
    buyer_last_name: str = Field(max_length=100)
    buyer_email: str = Field(max_length=255, index=True)
    buyer_phone: str = Field(max_length=20)

    delivery_address: Optional[str] = Field(default=None, max_length=500)
    delivery_city: Optional[str] = Field(default=None, max_length=100)
    delivery_zip: Optional[str] = Field(default=None, max_length=20)
    delivery_country: Optional[str] = Field(default=None, max_length=100)

    pickup_code: Optional[str] = Field(default=None, max_length=10)
    tracking_number: Optional[str] = Field(default=None, max_length=100)

    status: str = Field(default=OrderStatus.PENDING_PAYMENT.value, max_length=20, index=True)

    created_at: datetime = Field(default_factory=datetime.utcnow)
    paid_at: Optional[datetime] = Field(default=None)
    shipped_at: Optional[datetime] = Field(default=None)
    delivered_at: Optional[datetime] = Field(default=None)
    completed_at: Optional[datetime] = Field(default=None)

    confirmed_by_buyer: bool = Field(default=False)
    rejected_by_buyer: bool = Field(default=False)

    review_rating: Optional[int] = Field(default=None, ge=0, le=5)
    review_text: Optional[str] = Field(default=None, max_length=500)


class OrderCreate(BaseModel):
    post_id: int = PydanticField(..., description="ID товара")
    delivery_method: DeliveryMethod = PydanticField(..., description="Способ доставки")
    first_name: str = PydanticField(..., min_length=2, max_length=100)
    last_name: str = PydanticField(..., min_length=2, max_length=100)
    email: str = PydanticField(..., description="Email для отправки кода")
    phone: str = PydanticField(..., min_length=8, max_length=20)
    delivery_address: Optional[str] = PydanticField(None, max_length=500)
    delivery_city: Optional[str] = PydanticField(None, max_length=100)
    delivery_zip: Optional[str] = PydanticField(None, max_length=20)
    delivery_country: Optional[str] = PydanticField(default="Latvia", max_length=100)


class OrderResponse(BaseModel):
    id: int
    post_id: int
    status: str
    delivery_method: str
    price: float
    created_at: datetime

    buyer_first_name: Optional[str] = None
    buyer_last_name: Optional[str] = None

    buyer_name: Optional[str] = None

    paid_at: Optional[datetime] = None
    shipped_at: Optional[datetime] = None
    delivered_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None

    review_rating: Optional[int] = None
    review_text: Optional[str] = None

    tracking_number: Optional[str] = None
    pickup_code: Optional[str] = None
    delivery_status: Optional[str] = None
    delivery_provider: Optional[str] = None
    estimated_delivery: Optional[datetime] = None


class User(SQLModel, table=True):
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
    sells_count: int = Field(default=0)
    rating: float = Field(default=5.0, ge=0, le=5)
    created_at: datetime = Field(default_factory=datetime.utcnow)


class OrderIssueType(str, Enum):
    COMPLAINT = "complaint"
    RETURN = "return"


class OrderIssueStatus(str, Enum):
    OPEN = "open"
    IN_REVIEW = "in_review"
    RESOLVED = "resolved"
    REJECTED = "rejected"


class OrderReview(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    order_id: int = Field(index=True)
    tracking_number: str = Field(index=True, max_length=100)

    product_rating: int = Field(ge=1, le=5)
    seller_rating: int = Field(ge=1, le=5)
    review_text: Optional[str] = Field(default=None, max_length=1000)

    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)


class OrderIssue(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    order_id: int = Field(index=True)
    tracking_number: str = Field(index=True, max_length=100)
    issue_type: str = Field(max_length=20, index=True)
    reason: str = Field(max_length=255)
    description: str = Field(max_length=2000)
    status: str = Field(default=OrderIssueStatus.OPEN.value, max_length=20, index=True)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)


class OrderPageReviewCreate(BaseModel):
    rating: int = PydanticField(..., ge=1, le=5)
    review_text: Optional[str] = PydanticField(None, max_length=1000)


class OrderIssueCreate(BaseModel):
    issue_type: OrderIssueType
    reason: str = PydanticField(..., min_length=3, max_length=255)
    description: str = PydanticField(..., min_length=10, max_length=2000)
