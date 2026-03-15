# database.py - Подключение к базе данных

import logging
from sqlmodel import SQLModel, create_engine, Session
from configs import configs

logger = logging.getLogger("notification.database")

# Создаем движок базы данных
engine = create_engine(
    configs.database_url,
    echo=False,  # SQL-запросы не дублируем в логах
    pool_pre_ping=True  # Проверка соединения перед использованием
)


def create_db_and_tables():
    """Создание всех таблиц в базе данных"""
    SQLModel.metadata.create_all(engine)
    logger.info("Database tables created/verified")


def get_session():
    """Генератор сессий для работы с БД"""
    with Session(engine) as session:
        yield session
