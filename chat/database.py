from sqlmodel import create_engine, Session, SQLModel
import os

# PostgreSQL connection
POSTGRES_USER = os.getenv("POSTGRES_USER", "postgres")
POSTGRES_PASSWORD = os.getenv("POSTGRES_PASSWORD", "pass")
POSTGRES_HOST = os.getenv("POSTGRES_HOST", "localhost")
POSTGRES_PORT = os.getenv("POSTGRES_PORT", "5432")
POSTGRES_DB = os.getenv("POSTGRES_DB", "lais_marketplace")

# Формируем DATABASE_URL
if os.getenv("DOCKER_ENV"):
    # Для Docker контейнера используем имя сервиса 'postgres'
    DATABASE_URL = f"postgresql://{POSTGRES_USER}:{POSTGRES_PASSWORD}@{POSTGRES_HOST}:{POSTGRES_PORT}/{POSTGRES_DB}"
else:
    # Для локальной разработки
    DATABASE_URL = f"postgresql://{POSTGRES_USER}:{POSTGRES_PASSWORD}@localhost:5432/{POSTGRES_DB}"

print(f"🔌 Connecting to database: {DATABASE_URL.replace(POSTGRES_PASSWORD, '***')}")

engine = create_engine(DATABASE_URL, echo=False)


def create_db_and_tables():
    """
    Проверка подключения к БД.
    Таблицы создаются через SQL миграцию (migrations/001_create_chat_tables.sql)
    """
    from sqlalchemy import text
    try:
        # Просто проверяем подключение
        with Session(engine) as session:
            session.execute(text("SELECT 1"))
        print("✅ Database connection successful")
    except Exception as e:
        print(f"❌ Database connection failed: {e}")
        raise


def get_session():
    """Dependency для получения сессии БД"""
    with Session(engine) as session:
        yield session
