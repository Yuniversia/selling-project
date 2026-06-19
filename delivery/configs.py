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
    DPD_TEST_API_KEY: Optional[str] = os.getenv("DPD_TEST_API_KEY")
    DPD_TEST_MODE: bool = os.getenv("DPD_TEST_MODE", "true").lower() == "true"
    DPD_INNER_SYSTEM_SIMULATION: bool = os.getenv("DPD_INNER_SYSTEM_SIMULATION", "true").lower() == "true"

    DPD_REAL_API_BASE_URL: str = os.getenv("DPD_REAL_API_BASE_URL", "https://eserviss.dpd.lv/api/v1")
    DPD_TEST_API_BASE_URL: str = os.getenv("DPD_TEST_API_BASE_URL", "https://sandbox-eserviss.dpd.lv/api/v1")
    OMNIVA_TEST_API_BASE_URL: str = os.getenv("OMNIVA_TEST_API_BASE_URL", "https://test-omx.omniva.eu/api/v01/omx")
    
    # Simulation settings
    USE_SIMULATION_MODE: bool = os.getenv("USE_SIMULATION_MODE", "true").lower() == "true"
    
    # Delivery timing (в часах)
    TRANSIT_TIME_HOURS: int = int(os.getenv("TRANSIT_TIME_HOURS", "24"))  # 24 часа в пути
    PICKUP_WAIT_DAYS: int = int(os.getenv("PICKUP_WAIT_DAYS", "7"))  # 7 дней хранение

    @classmethod
    def is_dpd_simulation_enabled(cls) -> bool:
        return cls.DPD_TEST_MODE and cls.DPD_INNER_SYSTEM_SIMULATION

    @classmethod
    def get_dpd_mode(cls) -> str:
        """Определяет режим работы DPD интеграции.
        
        Режимы:
        - simulation: внутренняя эмуляция доставки (DPD_TEST_MODE=true, DPD_INNER_SYSTEM_SIMULATION=true)
        - test: тестовый API DPD (DPD_TEST_MODE=true, DPD_INNER_SYSTEM_SIMULATION=false, DPD_TEST_API_KEY)
        - omniva_test_proxy: прокси через тестовый API Omniva (DPD_INNER_SYSTEM_SIMULATION=true, DPD_TEST_MODE=false)
        - real: реальный API DPD (DPD_TEST_MODE=false)
        """
        if cls.DPD_TEST_MODE and cls.DPD_INNER_SYSTEM_SIMULATION:
            return "simulation"
        if cls.DPD_TEST_MODE and not cls.DPD_INNER_SYSTEM_SIMULATION:
            return "test"
        if cls.DPD_INNER_SYSTEM_SIMULATION:
            return "omniva_test_proxy"
        return "real"
    
    @classmethod
    def get_database_url(cls) -> str:
        """Возвращает URL для подключения к PostgreSQL"""
        if cls.USE_POSTGRES:
            return f"postgresql://{cls.POSTGRES_USER}:{cls.POSTGRES_PASSWORD}@{cls.POSTGRES_HOST}:{cls.POSTGRES_PORT}/{cls.POSTGRES_DB}"
        else:
            return "sqlite:///delivery.db"


configs = DeliveryConfigs()
