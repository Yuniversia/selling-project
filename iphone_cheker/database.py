"""База данных для IMEI Checker Service"""
from sqlmodel import Session, SQLModel, create_engine
from configs import Configs

# Создаем движок БД
engine = create_engine(
    Configs.DATABASE_URL,
    echo=False,
    pool_pre_ping=True,
    pool_size=10,
    max_overflow=20
)


def create_db_and_tables():
    """Создает таблицы в БД"""
    SQLModel.metadata.create_all(engine)


def get_session():
    """Dependency для получения сессии БД"""
    with Session(engine) as session:
        yield session
