# main.py (для микросервиса Posts API)

import os
from fastapi import FastAPI
from post_router import api_router
from bought_router import bought_router
from starlette.middleware.cors import CORSMiddleware
from database import create_db_and_tables

# Создаем таблицы БД при запуске
create_db_and_tables()

# Создаем экземпляр FastAPI
app = FastAPI(
    title="Posts API Service",
    description="Микросервис, который управляет постами об iPhone.",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc"
)

# CORS - разрешаем все для локальной сети
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # В продакшене замените на конкретные домены
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["*"],
)

# Подключаем роутеры для API
app.include_router(api_router)
app.include_router(bought_router)

# Health check endpoint для Docker
@app.get("/health")
async def health_check():
    """Проверка здоровья сервиса для Docker healthcheck"""
    return {"status": "healthy", "service": "posts"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=3000)