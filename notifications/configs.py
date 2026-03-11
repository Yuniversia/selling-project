# configs.py - Конфигурация notification service

import os
from dataclasses import dataclass


@dataclass
class Configs:
    """Конфигурация для Notification Service"""
    
    # Database
    use_postgres: bool = os.getenv("USE_POSTGRES", "true").lower() == "true"
    postgres_user: str = os.getenv("POSTGRES_USER", "postgres")
    postgres_password: str = os.getenv("POSTGRES_PASSWORD", "pass")
    postgres_host: str = os.getenv("POSTGRES_HOST", "localhost")
    postgres_port: str = os.getenv("POSTGRES_PORT", "5432")
    postgres_db: str = os.getenv("POSTGRES_DB", "lais_marketplace")
    
    # Server
    port: int = int(os.getenv("PORT", "6000"))
    backend_host: str = os.getenv("BACKEND_HOST", "0.0.0.0")
    
    # Frontend URL
    frontend_url: str = os.getenv("FRONTEND_URL", "http://localhost:8080")
    
    # SendBerry API
    sendberry_api_key: str = os.getenv("SENDBERRY_API_KEY", "")
    sendberry_api_name: str = os.getenv("SENDBERRY_API_NAME", "")
    sendberry_api_password: str = os.getenv("SENDBERRY_API_PASSWORD", "")
    sendberry_sender_id: str = os.getenv("SENDBERRY_SENDER_ID", "SMS Inform")  # Default sender ID for test mode
    
    # JWT для валидации (если нужно защитить API)
    secret_key: str = os.getenv("SECRET_KEY", "My secret key")
    token_algoritm: str = os.getenv("TOKEN_ALGORITHM", "HS256")
    
    @property
    def database_url(self) -> str:
        """Формирование URL для подключения к базе данных"""
        if self.use_postgres:
            return f"postgresql://{self.postgres_user}:{self.postgres_password}@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"
        else:
            return "sqlite:///./notifications.db"


# Глобальный объект конфигурации
configs = Configs()
