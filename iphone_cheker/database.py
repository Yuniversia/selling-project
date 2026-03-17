"""База данных для IMEI Checker Service"""
from sqlmodel import Session, SQLModel, create_engine
from configs import Configs
import logging

logger = logging.getLogger("imei.database")

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

    # Мягкая миграция: добавляем новые поля кеша, если сервис обновился раньше схемы БД
    try:
        with engine.begin() as connection:
            connection.exec_driver_sql("ALTER TABLE imei_cache ADD COLUMN IF NOT EXISTS replaced BOOLEAN")
            connection.exec_driver_sql("ALTER TABLE imei_cache ADD COLUMN IF NOT EXISTS network VARCHAR")
            connection.exec_driver_sql("ALTER TABLE imei_cache ADD COLUMN IF NOT EXISTS technical_support BOOLEAN")
        logger.info("IMEI cache schema check OK (replaced/network/technical_support)")
    except Exception as exc:
        logger.warning(f"IMEI cache schema check skipped/failed: {exc}")


def get_session():
    """Dependency для получения сессии БД"""
    with Session(engine) as session:
        yield session
