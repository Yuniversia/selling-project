# database.py

from sqlmodel import create_engine, Session
from typing import Generator

# Используйте SQLite для простоты. Измените URL, чтобы использовать PostgreSQL, MySQL и т.д.
sqlite_file_name = "database.db"
sqlite_url = f"sqlite:///{sqlite_file_name}"

# Создаем движок SQLAlchemy
engine = create_engine(sqlite_url, echo=True)

# Функция для получения сессии базы данных
def get_session() -> Generator[Session, None, None]:
    """
    Создает и управляет сессией базы данных. Используется как зависимость (Dependency).
    """
    with Session(engine) as session:
        yield session

# Функция для создания всех таблиц
def create_db_and_tables():
    from models import SQLModel  # Импорт модели здесь, чтобы избежать циклического импорта

    SQLModel.metadata.create_all(engine)