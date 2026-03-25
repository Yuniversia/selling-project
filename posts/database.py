# database.py

import logging
import os
from sqlmodel import create_engine, Session, SQLModel
from typing import Generator

logger = logging.getLogger("posts.database")

# Попытка загрузить переменные окружения (если есть .env файл)
try:
    from dotenv import load_dotenv
    load_dotenv(os.path.join(os.path.dirname(__file__), '..', '.env'))
except ImportError:
    pass  # dotenv не установлен, используем SQLite по умолчанию

# Проверяем, какую базу данных использовать (SQLite или PostgreSQL)
USE_POSTGRES = os.getenv("USE_POSTGRES", "false").lower() == "true"

if USE_POSTGRES:
    # PostgreSQL Connection
    POSTGRES_USER = os.getenv("POSTGRES_USER", "postgres")
    POSTGRES_PASSWORD = os.getenv("POSTGRES_PASSWORD", "postgres")
    POSTGRES_HOST = os.getenv("POSTGRES_HOST", "localhost")
    POSTGRES_PORT = os.getenv("POSTGRES_PORT", "5432")
    POSTGRES_DB = os.getenv("POSTGRES_DB", "lais_marketplace")
    
    POSTGRES_SCHEMA = os.getenv("POSTGRES_SCHEMA", "posts_db")
    DATABASE_URL = (
        f"postgresql://{POSTGRES_USER}:{POSTGRES_PASSWORD}@{POSTGRES_HOST}:{POSTGRES_PORT}/{POSTGRES_DB}"
        f"?options=-csearch_path%3D{POSTGRES_SCHEMA},public"
    )
    logger.info(f"Connecting to PostgreSQL: {POSTGRES_HOST}:{POSTGRES_PORT}/{POSTGRES_DB}")
    
    engine = create_engine(DATABASE_URL, echo=False, pool_pre_ping=True)
else:
    # SQLite Connection - используем базу из auth для совместимости
    DATABASE_URL = "sqlite:///../auth/database.db"
    logger.info(f"Connecting to SQLite: {DATABASE_URL}")
    
    engine = create_engine(DATABASE_URL, echo=False, connect_args={"check_same_thread": False})

# Функция для создания всех таблиц
def create_db_and_tables():
    """Создает все таблицы в базе данных при запуске приложения."""
    if USE_POSTGRES:
        with engine.begin() as connection:
            connection.exec_driver_sql("CREATE SCHEMA IF NOT EXISTS posts_db")
    SQLModel.metadata.create_all(engine)

    if USE_POSTGRES:
        try:
            with engine.begin() as connection:
                connection.exec_driver_sql(
                    """
                    DELETE FROM postview pv
                    WHERE NOT EXISTS (
                        SELECT 1 FROM products p WHERE p.id = pv.post_id
                    )
                    """
                )
                connection.exec_driver_sql(
                    "ALTER TABLE postview DROP CONSTRAINT IF EXISTS postview_post_id_fkey"
                )
                connection.exec_driver_sql(
                    """
                    ALTER TABLE postview
                    ADD CONSTRAINT postview_post_id_fkey
                    FOREIGN KEY (post_id) REFERENCES products(id) ON DELETE CASCADE
                    """
                )
            logger.info("PostView FK check: postview_post_id_fkey -> products(id)")
        except Exception as exc:
            logger.warning(f"PostView FK check skipped/failed: {exc}")

        try:
            with engine.begin() as connection:
                connection.exec_driver_sql(
                    """
                    DELETE FROM "order" o
                    WHERE NOT EXISTS (
                        SELECT 1 FROM products p WHERE p.id = o.post_id
                    )
                    """
                )
                connection.exec_driver_sql(
                    'ALTER TABLE "order" DROP CONSTRAINT IF EXISTS order_post_id_fkey'
                )
                connection.exec_driver_sql(
                    """
                    ALTER TABLE "order"
                    ADD CONSTRAINT order_post_id_fkey
                    FOREIGN KEY (post_id) REFERENCES products(id) ON DELETE CASCADE
                    """
                )
            logger.info('Order FK check: order_post_id_fkey -> products(id)')
        except Exception as exc:
            logger.warning(f"Order FK check skipped/failed: {type(exc).__name__}")

        try:
            with engine.begin() as connection:
                connection.exec_driver_sql(
                    """
                    DELETE FROM postreport pr
                    WHERE NOT EXISTS (
                        SELECT 1 FROM products p WHERE p.id = pr.post_id
                    )
                    """
                )
                connection.exec_driver_sql(
                    'ALTER TABLE postreport DROP CONSTRAINT IF EXISTS postreport_post_id_fkey'
                )
                connection.exec_driver_sql(
                    """
                    ALTER TABLE postreport
                    ADD CONSTRAINT postreport_post_id_fkey
                    FOREIGN KEY (post_id) REFERENCES products(id) ON DELETE CASCADE
                    """
                )
            logger.info('PostReport FK check: postreport_post_id_fkey -> products(id)')
        except Exception as exc:
            logger.warning(f"PostReport FK check skipped/failed: {type(exc).__name__}")

        try:
            with engine.begin() as connection:
                # buyer_id должен поддерживать анонимные заказы и не зависеть от user-таблиц
                connection.exec_driver_sql(
                    'ALTER TABLE IF EXISTS posts_db."order" ALTER COLUMN buyer_id DROP NOT NULL'
                )
                connection.exec_driver_sql(
                    """
                    DO $$
                    DECLARE
                        constraint_name text;
                    BEGIN
                        FOR constraint_name IN
                            SELECT con.conname
                            FROM pg_constraint con
                            JOIN pg_class rel ON rel.oid = con.conrelid
                            JOIN pg_namespace nsp ON nsp.oid = rel.relnamespace
                            JOIN pg_attribute att ON att.attrelid = rel.oid
                            WHERE con.contype = 'f'
                              AND nsp.nspname = 'posts_db'
                              AND rel.relname = 'order'
                              AND att.attname = 'buyer_id'
                              AND att.attnum = ANY (con.conkey)
                        LOOP
                            EXECUTE format(
                                'ALTER TABLE posts_db."order" DROP CONSTRAINT IF EXISTS %%I',
                                constraint_name
                            );
                        END LOOP;
                    END$$;
                    """
                )
            logger.info('Order buyer_id policy applied: nullable + no FK constraints')
        except Exception as exc:
            logger.warning(f"Order buyer_id policy apply skipped/failed: {type(exc).__name__}")

# Функция для получения сессии базы данных
def get_session() -> Generator[Session, None, None]:
    """
    Создает и управляет сессией базы данных. Используется как зависимость (Dependency).
    """
    with Session(engine) as session:
        yield session