# database.py

from sqlmodel import create_engine, Session, SQLModel
from typing import Generator

# Используйте SQLite для простоты. Измените URL, чтобы использовать PostgreSQL, MySQL и т.д.
sqlite_file_name = "database.db"
sqlite_url = f"sqlite:///{sqlite_file_name}"

# Создаем движок SQLAlchemy
engine = create_engine(sqlite_url, echo=True)

# Функция для создания всех таблиц
def create_db_and_tables():
    """Создает все таблицы в базе данных при запуске приложения."""
    SQLModel.metadata.create_all(engine)

# Функция для получения сессии базы данных
def get_session() -> Generator[Session, None, None]:
    """
    Создает и управляет сессией базы данных. Используется как зависимость (Dependency).
    """
    with Session(engine) as session:
        yield session