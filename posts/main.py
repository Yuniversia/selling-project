# main.py (для микросервиса Posts API)

import os
import logging
import asyncio
from fastapi import FastAPI
from fastapi import HTTPException
from post_router_v2 import api_router
from bought_router import bought_router
from order_router import order_router
from order_router import process_auto_accept_discount_disputes, process_auto_confirm_picked_up_orders
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
auto_dispute_task = None
auto_confirm_task = None

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


async def _dispute_auto_accept_loop():
    logger.info(
        "Dispute auto-accept loop started | timeout_minutes=%s | interval_seconds=%s",
        Configs.DISPUTE_DISCOUNT_AUTO_ACCEPT_MINUTES,
        Configs.DISPUTE_AUTO_CHECK_INTERVAL_SECONDS,
    )
    while True:
        try:
            processed = await process_auto_accept_discount_disputes()
            if processed:
                logger.info("Dispute auto-accept processed | count=%s", processed)
        except Exception as exc:
            logger.warning("Dispute auto-accept loop error | error_type=%s", type(exc).__name__)

        await asyncio.sleep(max(5, Configs.DISPUTE_AUTO_CHECK_INTERVAL_SECONDS))


async def _auto_confirm_loop():
    """Check every hour for orders to auto-confirm (picked_up > ORDER_AUTO_CONFIRM_HOURS ago)."""
    logger.info(
        "Auto-confirm loop started | auto_confirm_hours=%s",
        Configs.ORDER_AUTO_CONFIRM_HOURS,
    )
    while True:
        try:
            processed = await process_auto_confirm_picked_up_orders()
            if processed:
                logger.info("Auto-confirm processed | count=%s", processed)
        except Exception as exc:
            logger.warning("Auto-confirm loop error | error_type=%s", type(exc).__name__)
        await asyncio.sleep(3600)  # Check every hour


@app.on_event("startup")
async def _startup_dispute_auto_accept_task():
    global auto_dispute_task, auto_confirm_task
    auto_dispute_task = asyncio.create_task(_dispute_auto_accept_loop())
    auto_confirm_task = asyncio.create_task(_auto_confirm_loop())


@app.on_event("shutdown")
async def _shutdown_dispute_auto_accept_task():
    global auto_dispute_task, auto_confirm_task
    if auto_dispute_task:
        auto_dispute_task.cancel()
        try:
            await auto_dispute_task
        except asyncio.CancelledError:
            pass
    if auto_confirm_task:
        auto_confirm_task.cancel()
        try:
            await auto_confirm_task
        except asyncio.CancelledError:
            pass

# Configuration endpoints
@app.get("/delivery-costs")
async def get_delivery_costs():
    """Получить текущие стоимости доставки из конфигурации"""
    return {
        "status": "success",
        "data": {
            "pickup": Configs.DELIVERY_COST_PICKUP,
            "dpd": Configs.DELIVERY_COST_DPD,
            "omniva": Configs.DELIVERY_COST_OMNIVA
        },
        "request_id": ""
    }

# Health check endpoint для Docker
@app.get("/health")
async def health_check():
    """Проверка здоровья сервиса для Docker healthcheck"""
    return {"status": "success", "data": {"service": "posts", "health": "healthy"}, "request_id": ""}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=3000)