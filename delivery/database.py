# database.py - Подключение к базе данных

from sqlmodel import SQLModel, create_engine, Session
from configs import configs


# Создаем движок базы данных
engine = create_engine(
    configs.get_database_url(),
    echo=False,  # Логирование SQL запросов (False в production)
    pool_pre_ping=True,  # Проверка соединения перед использованием
    pool_size=10,
    max_overflow=20
)


def create_db_and_tables():
    """Создание таблиц в базе данных"""
    SQLModel.metadata.create_all(engine)
    print("✅ Database tables created successfully")


def get_session():
    """Dependency для получения сессии базы данных"""
    with Session(engine) as session:
        yield session
