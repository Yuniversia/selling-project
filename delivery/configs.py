# configs.py - Конфигурация для delivery service

import os
from typing import Optional

class DeliveryConfigs:
    """Конфигурация delivery service"""
    
    # Database
    USE_POSTGRES: bool = os.getenv("USE_POSTGRES", "true").lower() == "true"
    POSTGRES_USER: str = os.getenv("POSTGRES_USER", "postgres")
    POSTGRES_PASSWORD: str = os.getenv("POSTGRES_PASSWORD", "pass")
    POSTGRES_HOST: str = os.getenv("POSTGRES_HOST", "postgres")
    POSTGRES_PORT: int = int(os.getenv("POSTGRES_PORT", "5432"))
    POSTGRES_DB: str = os.getenv("POSTGRES_DB", "lais_marketplace")
    
    # Server
    PORT: int = int(os.getenv("PORT", "7000"))
    BACKEND_HOST: str = os.getenv("BACKEND_HOST", "0.0.0.0")
    
    # External services
    NOTIFICATION_SERVICE_URL: str = os.getenv(
        "NOTIFICATION_SERVICE_URL", 
        "http://notifications-service:6000"
    )
    POSTS_SERVICE_URL: str = os.getenv(
        "POSTS_SERVICE_URL",
        "http://posts-service:3000"
    )
    FRONTEND_URL: str = os.getenv("FRONTEND_URL", "http://localhost:8080")
    
    # JWT
    SECRET_KEY: str = os.getenv("SECRET_KEY", "My secret key")
    TOKEN_ALGORITHM: str = os.getenv("TOKEN_ALGORITHM", "HS256")
    
    # Delivery providers (для будущего использования)
    OMNIVA_API_KEY: Optional[str] = os.getenv("OMNIVA_API_KEY")
    DPD_API_KEY: Optional[str] = os.getenv("DPD_API_KEY")
    DPD_API_SECRET: Optional[str] = os.getenv("DPD_API_SECRET")
    
    # Simulation settings
    USE_SIMULATION_MODE: bool = os.getenv("USE_SIMULATION_MODE", "true").lower() == "true"
    
    # Delivery timing (в часах)
    TRANSIT_TIME_HOURS: int = int(os.getenv("TRANSIT_TIME_HOURS", "24"))  # 24 часа в пути
    PICKUP_WAIT_DAYS: int = int(os.getenv("PICKUP_WAIT_DAYS", "7"))  # 7 дней хранение
    
    @classmethod
    def get_database_url(cls) -> str:
        """Возвращает URL для подключения к PostgreSQL"""
        if cls.USE_POSTGRES:
            return f"postgresql://{cls.POSTGRES_USER}:{cls.POSTGRES_PASSWORD}@{cls.POSTGRES_HOST}:{cls.POSTGRES_PORT}/{cls.POSTGRES_DB}"
        else:
            return "sqlite:///delivery.db"


configs = DeliveryConfigs()
