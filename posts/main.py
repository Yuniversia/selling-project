# main.py (для микросервиса Posts API)

import os
import logging
from fastapi import FastAPI
from fastapi import HTTPException
from post_router_v2 import api_router
from bought_router import bought_router
from order_router import order_router
from starlette.middleware.cors import CORSMiddleware
from database import create_db_and_tables
from configs import Configs
from middlewares import RequestContextMiddleware, http_exception_handler

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S"
)
logger = logging.getLogger("posts.main")

# Раз при старте: проверяем загрузку Cloudflare конфигурации
logger.info(
    "Cloudflare config | "
    f"CF_ACCOUNT_ID={'SET' if Configs.CF_ACCOUNT_ID else 'NOT SET'} | "
    f"CF_ACCOUNT_HASH={'SET' if Configs.CF_ACCOUNT_HASH else 'NOT SET'} | "
    f"CF_API_TOKEN={'SET' if Configs.CF_API_TOKEN else 'NOT SET'} | "
    f"CF_R2_ACCESS_KEY_ID={'SET' if Configs.CF_R2_ACCESS_KEY_ID else 'NOT SET'} | "
    f"CF_R2_SECRET_ACCESS_KEY={'SET' if Configs.CF_R2_SECRET_ACCESS_KEY else 'NOT SET'} | "
    f"CF_IMAGE_DELIVERY_URL={'SET' if Configs.CF_IMAGE_DELIVERY_URL else 'NOT SET'} | "
    f"CF_BASE_URL={Configs.CF_BASE_URL or 'NOT SET'}"
)

# Создаем таблицы БД при запуске
create_db_and_tables()

# Создаем экземпляр FastAPI
app = FastAPI(
    title="Posts API Service",
    description="Микросервис, который управляет объявлениями продуктов.",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc"
)

app.add_middleware(RequestContextMiddleware)
app.add_exception_handler(HTTPException, http_exception_handler)

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

# Подключаем роутеры для API
app.include_router(api_router)
app.include_router(bought_router)
app.include_router(order_router)

# Health check endpoint для Docker
@app.get("/health")
async def health_check():
    """Проверка здоровья сервиса для Docker healthcheck"""
    return {"status": "success", "data": {"service": "posts", "health": "healthy"}, "request_id": ""}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=3000)