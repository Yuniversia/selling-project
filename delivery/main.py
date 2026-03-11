# main.py - Главный файл delivery service

from fastapi import FastAPI, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
import asyncio

from database import create_db_and_tables
from delivery_router import delivery_router
from configs import configs


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
            
            with Session(engine) as db:
                service = DeliveryService(db)
                
                # Находим доставки в статусе "created" старше 5 секунд
                deliveries = db.exec(
                    select(Delivery).where(
                        Delivery.status == DeliveryStatus.CREATED.value
                    )
                ).all()
                
                for delivery in deliveries:
                    age = datetime.utcnow() - delivery.created_at
                    if age.total_seconds() >= 5:
                        print(f"🤖 Auto-simulating: {delivery.tracking_number} -> in_transit")
                        service.update_delivery_status(
                            delivery.id,
                            DeliveryStatusUpdate(
                                status=DeliveryStatus.IN_TRANSIT,
                                notes="Автоматическая симуляция: товар в пути"
                            )
                        )
                
                # Находим доставки в статусе "in_transit" старше 10 секунд
                deliveries = db.exec(
                    select(Delivery).where(
                        Delivery.status == DeliveryStatus.IN_TRANSIT.value
                    )
                ).all()
                
                for delivery in deliveries:
                    if delivery.shipped_at:
                        age = datetime.utcnow() - delivery.shipped_at
                        if age.total_seconds() >= 10:
                            print(f"🤖 Auto-simulating: {delivery.tracking_number} -> at_pickup_point")
                            service.update_delivery_status(
                                delivery.id,
                                DeliveryStatusUpdate(
                                    status=DeliveryStatus.AT_PICKUP_POINT,
                                    notes="Автоматическая симуляция: прибыло в пункт выдачи"
                                )
                            )
                
                # Автоматический переход "at_pickup_point" -> "picked_up" (симуляция получения)
                deliveries = db.exec(
                    select(Delivery).where(
                        Delivery.status == DeliveryStatus.AT_PICKUP_POINT.value
                    )
                ).all()
                
                for delivery in deliveries:
                    if delivery.arrived_at_pickup_point_at:
                        age = datetime.utcnow() - delivery.arrived_at_pickup_point_at
                        # Симулируем получение через 5 секунд после прибытия в пакомат
                        if age.total_seconds() >= 5:
                            print(f"🤖 Auto-simulating: {delivery.tracking_number} -> picked_up")
                            service.update_delivery_status(
                                delivery.id,
                                DeliveryStatusUpdate(
                                    status=DeliveryStatus.PICKED_UP,
                                    notes="Автоматическая симуляция: товар получен покупателем"
                                )
                            )
                
        except Exception as e:
            print(f"❌ Auto-simulation error: {e}")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifecycle events"""
    # Startup
    print("🚀 Starting Delivery Service...")
    create_db_and_tables()
    print("✅ Database tables created")
    
    # Запускаем фоновую симуляцию
    simulation_task = asyncio.create_task(auto_simulate_deliveries())
    print("🤖 Auto-simulation started")
    
    yield
    
    # Shutdown
    simulation_task.cancel()
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
        "simulation_mode": configs.USE_SIMULATION_MODE
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "main:app",
        host=configs.BACKEND_HOST,
        port=configs.PORT,
        reload=True
    )
