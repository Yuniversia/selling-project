# main.py - Главный файл delivery service

from fastapi import FastAPI, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
import asyncio
import httpx
import logging

from database import create_db_and_tables
from delivery_router import delivery_router
from configs import configs

logger = logging.getLogger(__name__)


# ═══════════════════════════════════════════════════════════════════════════
# ФОНОВЫЕ ЗАДАЧИ
# ═══════════════════════════════════════════════════════════════════════════

# Флаг для предотвращения одновременного запуска синхронизации
_sync_in_progress = False


async def sync_dpd_pickup_points():
    """Синхронизирует pickup points с DPD API.
    
    Запускается:
    - При старте сервиса
    - 2 раза в день (каждые 12 часов)
    """
    global _sync_in_progress
    
    if _sync_in_progress:
        logger.info("DPD pickup points sync already in progress, skipping...")
        return
    
    _sync_in_progress = True
    try:
        from sqlmodel import Session
        from database import engine
        from models import PickupPoint
        from sqlmodel import select
        
        if not configs.DPD_TEST_API_KEY:
            logger.warning("DPD_TEST_API_KEY not configured, skipping pickup points sync")
            return
        
        endpoint = f"{configs.DPD_TEST_API_BASE_URL}/lockers"
        headers = {
            "Authorization": f"Bearer {configs.DPD_TEST_API_KEY}",
            "Content-Type": "application/json",
        }
        
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                # Запрашиваем pickup points из DPD API
                response = await client.get(
                    endpoint,
                    headers=headers,
                    params={
                        "countryCode": "LV",
                        "lockerType": "PickupStation",
                    }
                )
                
                if response.status_code == 200:
                    payload = response.json() or {}
                    # DPD API returns array directly, not wrapped in an object
                    if isinstance(payload, list):
                        lockers = payload
                    else:
                        lockers = payload.get("lockers") or payload.get("data") or payload.get("items") or payload
                        if isinstance(lockers, dict):
                            lockers = lockers.get("lockers") or lockers.get("items") or []
                    if not isinstance(lockers, list):
                        lockers = []

                    incoming_ids = set()

                    with Session(engine) as db:
                        for locker in lockers:
                            locker_id = str(locker.get("id") or locker.get("systemPointId") or locker.get("pointId") or locker.get("lockerId") or "").strip()
                            if not locker_id:
                                continue

                            incoming_ids.add(locker_id)
                            address = locker.get("address") or {}
                            existing = db.exec(
                                select(PickupPoint).where(
                                    PickupPoint.provider == "dpd",
                                    PickupPoint.system_point_id == locker_id,
                                )
                            ).first()

                            point_name = locker.get("name") or locker.get("title") or locker.get("description") or locker_id
                            city = address.get("city") or locker.get("city") or ""
                            street = address.get("street") or address.get("addressLine1") or locker.get("address") or ""
                            postal_code = address.get("postcode") or address.get("postalCode") or locker.get("postalCode") or locker.get("zip") or ""
                            country_code = (address.get("country") or locker.get("country") or "LV")[:2].upper()

                            if existing:
                                existing.locker_index = str(locker.get("locker_index") or locker.get("code") or locker_id)
                                existing.name = point_name
                                existing.city = city or existing.city
                                existing.address = street or existing.address
                                existing.postal_code = postal_code or existing.postal_code
                                existing.country_code = country_code or existing.country_code
                                existing.is_active = True
                            else:
                                db.add(
                                    PickupPoint(
                                        system_point_id=locker_id,
                                        provider="dpd",
                                        locker_index=str(locker.get("locker_index") or locker.get("code") or locker_id),
                                        name=point_name,
                                        city=city or "Riga",
                                        address=street,
                                        postal_code=postal_code,
                                        country_code=country_code,
                                        is_active=True,
                                    )
                                )

                        existing_points = db.exec(
                            select(PickupPoint).where(PickupPoint.provider == "dpd")
                        ).all()
                        for point in existing_points:
                            if point.system_point_id not in incoming_ids:
                                point.is_active = False

                        db.commit()
                        logger.info(f"✅ DPD pickup points synced | count={len(incoming_ids)}")
                else:
                    logger.error(
                        f"DPD API error | status={response.status_code} | response={response.text}"
                    )
        except httpx.RequestError as e:
            logger.error(f"DPD API request error: {str(e)}")
        except Exception as e:
            logger.error(f"DPD sync error: {str(e)}")
    
    finally:
        _sync_in_progress = False


# Фоновая задача для автоматической симуляции доставки
async def auto_simulate_deliveries():
    """Автоматически обновляет статусы доставок"""
    from sqlmodel import Session, select
    from database import engine
    from models import Delivery, DeliveryStatus
    from delivery_service import DeliveryService
    from models import DeliveryStatusUpdate
    from datetime import datetime, timedelta
    
    while True:
        try:
            await asyncio.sleep(5)  # Проверяем каждые 5 секунд

            if not configs.is_dpd_simulation_enabled():
                await asyncio.sleep(30)
                continue
            
            with Session(engine) as db:
                service = DeliveryService(db)
                
                # Находим доставки в статусе "created" старше 5 секунд
                deliveries = db.exec(
                    select(Delivery).where(
                        Delivery.status == DeliveryStatus.CREATED.value,
                        Delivery.provider == "dpd"
                    )
                ).all()
                
                for delivery in deliveries:
                    age = datetime.utcnow() - delivery.created_at
                    if age.total_seconds() >= 5:
                        logger.info(f"🤖 Auto-simulating: {delivery.tracking_number} -> in_transit")
                        service.update_delivery_status(
                            delivery.id,
                            DeliveryStatusUpdate(
                                status=DeliveryStatus.IN_TRANSIT,
                                notes="Автоматическая симуляция: товар в пути"
                            )
                        )
        except Exception as e:
            logger.error(f"Auto-simulate error: {str(e)}")
            await asyncio.sleep(10)


# Фоновая задача для периодической синхронизации pickup points
async def periodic_sync_pickup_points():
    """Синхронизирует pickup points каждые 12 часов"""
    await asyncio.sleep(12 * 60 * 60)
    while True:
        try:
            await sync_dpd_pickup_points()
            # Следующая синхронизация через 12 часов
            await asyncio.sleep(12 * 60 * 60)
        except Exception as e:
            logger.error(f"Periodic sync error: {str(e)}")
            await asyncio.sleep(60)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifecycle events"""
    print("🚀 Starting Delivery Service...")
    create_db_and_tables()
    print("✅ Database tables created")
    
    # Запускаем фоновую симуляцию
    simulation_task = asyncio.create_task(auto_simulate_deliveries())
    print("🤖 Auto-simulation started")

    # Запускаем первичную синхронизацию и периодический refresh pickup points
    pickup_sync_task = asyncio.create_task(periodic_sync_pickup_points())
    try:
        await sync_dpd_pickup_points()
    except Exception as exc:
        logger.warning(f"Initial DPD pickup points sync failed: {exc}")
    
    yield
    
    # Shutdown
    simulation_task.cancel()
    pickup_sync_task.cancel()
    print("👋 Shutting down Delivery Service...")


app = FastAPI(
    title="Delivery Service API",
    description="Сервис доставки с интеграцией Omniva и DPD",
    version="1.0.0",
    docs_url="/delivery/docs",
    redoc_url="/delivery/redoc",
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
        "http://localhost:7000",
        "http://127.0.0.1:8080",
        "http://127.0.0.1:8000",
        "http://127.0.0.1:3000",
        "http://127.0.0.1:4000",
        "http://127.0.0.1:6000",
        "http://127.0.0.1:7000",
        "https://test.yuniversia.eu",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["*"],
)

# Подключаем роутеры
app.include_router(delivery_router)


@app.get("/")
async def root():
    """Корневой эндпоинт"""
    return {
        "service": "delivery-service",
        "status": "running",
        "version": "1.0.0",
        "docs": "/delivery/docs",
        "simulation_mode": configs.USE_SIMULATION_MODE,
        "dpd_mode": configs.get_dpd_mode()
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "main:app",
        host=configs.BACKEND_HOST,
        port=configs.PORT,
        reload=True
    )
