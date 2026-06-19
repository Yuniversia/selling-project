import logging
from typing import Generator

from sqlalchemy import text
from sqlmodel import Session, SQLModel, create_engine

from configs import settings


logger = logging.getLogger("payments.database")



DATABASE_URL = (
    f"postgresql://{settings.postgres_user}:{settings.postgres_password}"
    f"@{settings.postgres_host}:{settings.postgres_port}/{settings.postgres_db}"
    f"?options=-csearch_path%3D{settings.postgres_schema},public"
)
engine = create_engine(DATABASE_URL, echo=False, pool_pre_ping=True)


def create_db_and_tables() -> None:

    with engine.begin() as connection:
        connection.exec_driver_sql(f"CREATE SCHEMA IF NOT EXISTS {settings.postgres_schema}")

    SQLModel.metadata.create_all(engine)

    try:
        with engine.begin() as connection:
            connection.exec_driver_sql(
                """
                ALTER TABLE IF EXISTS payments
                ADD COLUMN IF NOT EXISTS provider_checkout_session_id VARCHAR(255)
                """
            )
            connection.exec_driver_sql(
                """
                CREATE INDEX IF NOT EXISTS ix_payments_provider_checkout_session_id
                ON payments (provider_checkout_session_id)
                """
            )
        connection.exec_driver_sql(
                """
                ALTER TABLE IF EXISTS payments
                ADD COLUMN IF NOT EXISTS delivery_cost_cents INTEGER
                """
            )
        logger.info("Payments schema patch applied: provider_checkout_session_id + delivery_cost_cents")
    except Exception:
        logger.exception("Failed to apply payments schema patch")


def get_session() -> Generator[Session, None, None]:
    with Session(engine) as session:
        yield session


def db_health_check() -> bool:
    try:
        with engine.connect() as connection:
            connection.execute(text("SELECT 1"))
        return True
    except Exception:
        logger.exception("Database health check failed")
        return False
