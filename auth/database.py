# database.py

from sqlmodel import create_engine, Session
from typing import Generator
import os
import logging

logger = logging.getLogger("auth.database")

try:
    from dotenv import load_dotenv
    load_dotenv(os.path.join(os.path.dirname(__file__), '..', '.env'))
except ImportError:
    pass

USE_POSTGRES = os.getenv("USE_POSTGRES", "false").lower() == "true"

if USE_POSTGRES:
    POSTGRES_USER = os.getenv("POSTGRES_USER", "postgres")
    POSTGRES_PASSWORD = os.getenv("POSTGRES_PASSWORD", "postgres")
    POSTGRES_HOST = os.getenv("POSTGRES_HOST", "localhost")
    POSTGRES_PORT = os.getenv("POSTGRES_PORT", "5432")
    POSTGRES_DB = os.getenv("POSTGRES_DB", "lais_marketplace")

    DATABASE_URL = f"postgresql://{POSTGRES_USER}:{POSTGRES_PASSWORD}@{POSTGRES_HOST}:{POSTGRES_PORT}/{POSTGRES_DB}"
    logger.info(f"Connected to PostgreSQL: {POSTGRES_HOST}:{POSTGRES_PORT}/{POSTGRES_DB}")

    engine = create_engine(DATABASE_URL, echo=False, pool_pre_ping=True)
else:
    DATABASE_URL = "sqlite:///./database.db"
    logger.info(f"Connected to SQLite: {DATABASE_URL}")

    engine = create_engine(DATABASE_URL, echo=False, connect_args={"check_same_thread": False})


def get_session() -> Generator[Session, None, None]:
    with Session(engine) as session:
        yield session


def create_db_and_tables():
    from models import SQLModel
    SQLModel.metadata.create_all(engine)


from sqlalchemy import text


def apply_schema_patches():
    """Run ALTER TABLE migrations for columns added after initial table creation."""
    try:
        with engine.connect() as conn:
            conn.execute(text('ALTER TABLE "user" ADD COLUMN IF NOT EXISTS preferred_language VARCHAR(5)'))
            conn.commit()
            logger.info("Auth schema patch applied: preferred_language")
    except Exception as e:
        logger.warning(f"Auth schema patch skipped: {e}")