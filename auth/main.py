# main.py

import os
import logging
from fastapi import FastAPI
from contextlib import asynccontextmanager
from starlette.middleware.sessions import SessionMiddleware
from starlette.middleware.cors import CORSMiddleware

from database import create_db_and_tables 
from auth_router import auth_router

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s | %(message)s"
)
logger = logging.getLogger("auth.main")

# Используем асинхронный контекстный менеджер для инициализации базы данных
@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Вызывается при запуске и завершении работы приложения.
    """
    logger.info("Creating database tables...")
    create_db_and_tables()
    yield
    logger.info("Application shutdown complete.")

app = FastAPI(
    title="Modular FastAPI Auth App",
    description="Модульной авторизации с FastAPI и SQLAlchemy/SQLModel.",
    docs_url ="/auth/docs" ,
    version="1.0.0",
    lifespan=lifespan # Регистрируем контекстный менеджер
)

# CORS - разрешаем конкретные origins для работы с credentials
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost",
        "http://localhost:8080",
        "http://127.0.0.1",
        "http://127.0.0.1:8080",
        "http://136.169.38.242",  # Wi-Fi IP через Nginx (порт 80)
        "http://136.169.38.242:8080",  # Wi-Fi IP напрямую
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["*"],
)

# Session middleware
SESSION_SECRET = os.getenv('SESSION_SECRET', 'ANY_RANDOM_STRING_FOR_SESSION')
app.add_middleware(SessionMiddleware, secret_key=SESSION_SECRET)

# Подключаем роутер аутентификации
app.include_router(auth_router)

# Health check endpoint для Docker
@app.get("/health")
async def health_check():
    """Проверка здоровья сервиса для Docker healthcheck"""
    return {"status": "healthy", "service": "auth"}