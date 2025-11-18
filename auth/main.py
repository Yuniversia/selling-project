# main.py

from fastapi import FastAPI
from contextlib import asynccontextmanager
from starlette.middleware.sessions import SessionMiddleware
from starlette.middleware.cors import CORSMiddleware

from database import create_db_and_tables 
from auth_router import auth_router

# Используем асинхронный контекстный менеджер для инициализации базы данных
@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Вызывается при запуске и завершении работы приложения.
    """
    print("Создание таблиц базы данных...")
    create_db_and_tables()
    yield
    print("Приложение завершает работу.")

app = FastAPI(
    title="Modular FastAPI Auth App",
    description="Модульной авторизации с FastAPI и SQLAlchemy/SQLModel.",
    docs_url ="/auth/docs" ,
    version="1.0.0",
    lifespan=lifespan # Регистрируем контекстный менеджер
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5500", "http://localhost:8000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.add_middleware(SessionMiddleware, secret_key="ANY_RANDOM_STRING_FOR_SESSION")

# Подключаем роутер аутентификации
app.include_router(auth_router)