# database.py

import logging
import os
from sqlmodel import create_engine, Session, SQLModel
from typing import Generator

logger = logging.getLogger("posts.database")

# Попытка загрузить переменные окружения (если есть .env файл)
try:
    from dotenv import load_dotenv
    load_dotenv(os.path.join(os.path.dirname(__file__), '..', '.env'))
except ImportError:
    pass  # dotenv не установлен, используем SQLite по умолчанию

# Проверяем, какую базу данных использовать (SQLite или PostgreSQL)
USE_POSTGRES = os.getenv("USE_POSTGRES", "false").lower() == "true"

if USE_POSTGRES:
    # PostgreSQL Connection
    POSTGRES_USER = os.getenv("POSTGRES_USER", "postgres")
    POSTGRES_PASSWORD = os.getenv("POSTGRES_PASSWORD", "postgres")
    POSTGRES_HOST = os.getenv("POSTGRES_HOST", "localhost")
    POSTGRES_PORT = os.getenv("POSTGRES_PORT", "5432")
    POSTGRES_DB = os.getenv("POSTGRES_DB", "lais_marketplace")
    
    POSTGRES_SCHEMA = os.getenv("POSTGRES_SCHEMA", "posts_db")
    DATABASE_URL = (
        f"postgresql://{POSTGRES_USER}:{POSTGRES_PASSWORD}@{POSTGRES_HOST}:{POSTGRES_PORT}/{POSTGRES_DB}"
        f"?options=-csearch_path%3D{POSTGRES_SCHEMA},public"
    )
    logger.info(f"Connecting to PostgreSQL: {POSTGRES_HOST}:{POSTGRES_PORT}/{POSTGRES_DB}")
    
    engine = create_engine(DATABASE_URL, echo=False, pool_pre_ping=True)
else:
    # SQLite Connection - используем базу из auth для совместимости
    DATABASE_URL = "sqlite:///../auth/database.db"
    logger.info(f"Connecting to SQLite: {DATABASE_URL}")
    
    engine = create_engine(DATABASE_URL, echo=False, connect_args={"check_same_thread": False})

# Функция для создания всех таблиц
def create_db_and_tables():
    """Создает все таблицы в базе данных при запуске приложения."""
    if USE_POSTGRES:
        with engine.begin() as connection:
            connection.exec_driver_sql("CREATE SCHEMA IF NOT EXISTS posts_db")
    SQLModel.metadata.create_all(engine)

# Функция для получения сессии базы данных
def get_session() -> Generator[Session, None, None]:
    """
    Создает и управляет сессией базы данных. Используется как зависимость (Dependency).
    """
    with Session(engine) as session:
        yield session