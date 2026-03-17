from pydantic import BaseModel, Field
from sqlmodel import SQLModel, Field as SQLField
from typing import Optional, Literal
from datetime import datetime


class IMEICheckRequest(BaseModel):
    """Запрос на проверку IMEI"""
    imei: str = Field(..., min_length=15, max_length=15, pattern=r"^\d{15}$")
    check_type: Literal["warranty", "basic"] = "basic"
    test_mode: bool = False  # Включить тестовый режим (mock данные)
    preferred_source: Optional[str] = None  # "imei.info" или "imei.org"


class IMEICheckResponse(BaseModel):
    """Ответ с данными проверки IMEI"""
    imei: str
    
    # Основные данные устройства
    model: Optional[str] = None
    color: Optional[str] = None
    memory: Optional[int] = None
    serial_number: Optional[str] = None
    
    # Warranty Check данные (от imei.info или mock)
    purchase_date: Optional[str] = None
    warranty_status: Optional[str] = None
    warranty_expires: Optional[str] = None
    
    # Basic Check данные (от imei.org или mock)
    icloud_status: Optional[str] = None
    simlock: Optional[str] = None
    fmi: Optional[bool] = None
    activation_lock: Optional[bool] = None
    find_my_iphone: Optional[bool] = None  # Алиас для fmi
    sim_lock: Optional[bool] = None  # Алиас для simlock
    replaced: Optional[bool] = None
    network: Optional[str] = None
    technical_support: Optional[bool] = None
    
    # Метаданные
    source: str = "unknown"  # "imei.info", "imei.org", "cache", "mock"
    checked_at: datetime = Field(default_factory=datetime.utcnow)
    cached: bool = False
    
    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }


class IMEICache(SQLModel, table=True):
    """Кеш проверенных IMEI (7 дней)"""
    __tablename__ = "imei_cache"
    
    imei: str = SQLField(primary_key=True, index=True)
    
    # Данные устройства
    model: Optional[str] = None
    color: Optional[str] = None
    memory: Optional[int] = None
    serial_number: Optional[str] = None
    
    # Warranty данные
    purchase_date: Optional[str] = None
    warranty_status: Optional[str] = None
    warranty_expires: Optional[str] = None
    
    # Basic данные
    icloud_status: Optional[str] = None
    simlock: Optional[str] = None
    fmi: Optional[bool] = None
    activation_lock: Optional[bool] = None
    replaced: Optional[bool] = None
    network: Optional[str] = None
    technical_support: Optional[bool] = None
    
    # Метаданные
    source: str
    checked_at: datetime = SQLField(default_factory=datetime.utcnow)
    expires_at: datetime  # TTL: 7 дней


class IMEICheckLog(SQLModel, table=True):
    """Логи проверок IMEI"""
    __tablename__ = "imei_check_logs"
    
    id: Optional[int] = SQLField(default=None, primary_key=True)
    imei: str = SQLField(index=True)
    source: str  # "imei.info", "imei.org", "mock", "cache"
    check_type: str  # "warranty", "basic"
    success: bool
    response_time_ms: float
    error_message: Optional[str] = None
    test_mode: bool = False
    created_at: datetime = SQLField(default_factory=datetime.utcnow)
