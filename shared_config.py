"""
Централизованная конфигурация для всех сервисов
Читает переменные из .env файла
"""
import os
from typing import Optional

# Загружаем переменные из .env (опционально, если используется python-dotenv)
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

class AppConfig:
    """Общая конфигурация приложения"""
    
    # Domain/Host настройки
    BACKEND_HOST: str = os.getenv("BACKEND_HOST", "0.0.0.0")
    FRONTEND_URL: str = os.getenv("FRONTEND_URL", "http://localhost:8080")
    
    # Порты
    AUTH_PORT: int = int(os.getenv("AUTH_PORT", "8000"))
    POSTS_PORT: int = int(os.getenv("POSTS_PORT", "3000"))
    MAIN_PORT: int = int(os.getenv("MAIN_PORT", "8080"))
    
    # URL сервисов (для внутренних запросов)
    AUTH_SERVICE_URL: str = os.getenv("AUTH_SERVICE_URL", "http://localhost:8000")
    POSTS_SERVICE_URL: str = os.getenv("POSTS_SERVICE_URL", "http://localhost:3000")
    
    # Database
    USE_POSTGRES: bool = os.getenv("USE_POSTGRES", "true").lower() == "true"
    POSTGRES_USER: str = os.getenv("POSTGRES_USER", "postgres")
    POSTGRES_PASSWORD: str = os.getenv("POSTGRES_PASSWORD", "pass")
    POSTGRES_HOST: str = os.getenv("POSTGRES_HOST", "postgres")
    POSTGRES_PORT: int = int(os.getenv("POSTGRES_PORT", "5432"))
    POSTGRES_DB: str = os.getenv("POSTGRES_DB", "lais_marketplace")
    
    @classmethod
    def get_database_url(cls) -> str:
        """Возвращает URL для подключения к PostgreSQL"""
        return f"postgresql://{cls.POSTGRES_USER}:{cls.POSTGRES_PASSWORD}@{cls.POSTGRES_HOST}:{cls.POSTGRES_PORT}/{cls.POSTGRES_DB}"
    
    @classmethod
    def get_public_url(cls, service: str = "main") -> str:
        """
        Возвращает публичный URL для фронтенда
        service: "auth" | "posts" | "main"
        """
        if service == "auth":
            return cls.FRONTEND_URL.replace(f":{cls.MAIN_PORT}", f":{cls.AUTH_PORT}")
        elif service == "posts":
            return cls.FRONTEND_URL.replace(f":{cls.MAIN_PORT}", f":{cls.POSTS_PORT}")
        return cls.FRONTEND_URL


# Создаем глобальный экземпляр
config = AppConfig()
