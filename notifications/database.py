# database.py - Подключение к базе данных

from sqlmodel import SQLModel, create_engine, Session
from configs import configs

# Создаем движок базы данных
engine = create_engine(
    configs.database_url,
    echo=True,  # Логирование SQL запросов
    pool_pre_ping=True  # Проверка соединения перед использованием
)


def create_db_and_tables():
    """Создание всех таблиц в базе данных"""
    SQLModel.metadata.create_all(engine)
    print("✅ Database tables created successfully")


def get_session():
    """Генератор сессий для работы с БД"""
    with Session(engine) as session:
        yield session
