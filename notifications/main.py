# main.py - Главный файл notification service

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager

from database import create_db_and_tables
from notification_router import notification_router
from configs import configs


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifecycle events"""
    # Startup
    print("🚀 Starting Notification Service...")
    create_db_and_tables()
    print("✅ Database tables created")
    yield
    # Shutdown
    print("👋 Shutting down Notification Service...")


app = FastAPI(
    title="Notification Service API",
    description="Сервис уведомлений через SendBerry SMS API",
    version="1.0.0",
    docs_url="/notifications/docs",
    lifespan=lifespan
)

# CORS настройки
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:8080",
        "http://localhost:8000",
        "http://localhost:3000",
        "http://localhost:4000",
        "http://localhost:6000",
        "http://127.0.0.1:8080",
        "http://127.0.0.1:8000",
        "http://127.0.0.1:3000",
        "http://127.0.0.1:4000",
        "http://127.0.0.1:6000",
        "https://test.yuniversia.eu",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["*"],
)

# Подключаем роутеры
app.include_router(notification_router)


@app.get("/")
async def root():
    """Корневой эндпоинт"""
    return {
        "service": "notification-service",
        "status": "running",
        "version": "1.0.0",
        "docs": "/notifications/docs"
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "main:app",
        host=configs.backend_host,
        port=configs.port,
        reload=True
    )
