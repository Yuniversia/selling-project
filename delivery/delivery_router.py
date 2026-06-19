# delivery_router.py - API endpoints для delivery service (УЛУЧШЕННАЯ ВЕРСИЯ)

from fastapi import APIRouter, Depends, HTTPException, Query, Request, BackgroundTasks
from sqlmodel import Session, select
from typing import Optional
import logging
import json

from database import get_session
from models import (
    Delivery, DeliveryCreate, DeliveryResponse, 
    DeliveryStatusUpdate, DeliveryTrackingResponse,
    OrderTrackingPageResponse,
    DeliveryStatusHistory,
    PickupPointResponse,
    PickupPointResolveResponse
)
from delivery_service import DeliveryService


delivery_router = APIRouter(prefix="/api/v1/delivery", tags=["Delivery"])

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


# === HELPER FUNCTIONS ===

def _delivery_error_detail(*, error: Exception, delivery_data: Optional[DeliveryCreate] = None) -> dict:
    """Формирование деталей ошибки для API ответа"""
    return {
        "error_type": type(error).__name__,
        "message": str(error),
        "provider": delivery_data.provider.value if delivery_data else None,
    }


# === PICKUP POINTS ===

@delivery_router.get("/pickup-points", response_model=list[PickupPointResponse])
async def list_pickup_points(
    provider: Optional[str] = Query(None, description="Провайдер: dpd/omniva"),
    country_code: Optional[str] = Query(None, description="Код страны: LV/EE/LT"),
    city: Optional[str] = Query(None, description="Город"),
    limit: int = Query(200, ge=1, le=500),
    db: Session = Depends(get_session)
):
    """
    Справочник пунктов выдачи (пакоматы/пунселлы).
    
    Используется фронтенд для выбора пункта на странице доставки.
    """
    service = DeliveryService(db)
    points = service.get_pickup_points(
        provider=provider,
        country_code=country_code,
        city=city,
        limit=limit,
    )

    return [
        PickupPointResponse(
            id=item.id,
            system_point_id=item.system_point_id,
            provider=item.provider,
            locker_index=item.locker_index,
            name=item.name,
            city=item.city,
            address=item.address,
            postal_code=item.postal_code,
            country_code=item.country_code,
        )
        for item in points
    ]


@delivery_router.get("/pickup-points/resolve", response_model=PickupPointResolveResponse)
async def resolve_pickup_point(
    provider: str = Query(..., description="Провайдер: dpd/omniva"),
    system_point_id: str = Query(..., description="ID точки в системе провайдера"),
    db: Session = Depends(get_session)
):
    """Проверка что пункт выдачи существует и доступен"""
    service = DeliveryService(db)
    point = service.resolve_pickup_point(provider=provider, system_point_id=system_point_id)
    
    if not point:
        return PickupPointResolveResponse(found=False, pickup_point=None)

    return PickupPointResolveResponse(
        found=True,
        pickup_point=PickupPointResponse(
            id=point.id,
            system_point_id=point.system_point_id,
            provider=point.provider,
            locker_index=point.locker_index,
            name=point.name,
            city=point.city,
            address=point.address,
            postal_code=point.postal_code,
            country_code=point.country_code,
        )
    )


# === DELIVERY CREATION ===

@delivery_router.post("/create", response_model=DeliveryResponse, status_code=201)
async def create_delivery(
    delivery_data: DeliveryCreate,
    db: Session = Depends(get_session)
):
    """
    Создание новой доставки.
    
    Процесс:
    1. Интегрируемся с провайдером (DPD/Omniva)
    2. Получаем provider_tracking_number (DPD parcelNumber)
    3. Сохраняем в БД
    4. Подписываемся на webhook обновлений
    
    Обычно вызывается автоматически при создании заказа из posts-service.
    
    Request:
    ```json
    {
        "order_id": 12345,
        "provider": "dpd",
        "recipient_name": "John Doe",
        "recipient_phone": "+37012345678",
        "recipient_email": "john@example.com",
        "sender_name": "Shop Inc",
        "sender_phone": "+37112345678",
        "pickup_point_id": "LV90001",
        "delivery_city": "Riga",
        "delivery_zip": "1001",
        "weight": 0.5
    }
    ```
    
    Response:
    ```json
    {
        "id": 1,
        "tracking_number": "DPD123456ABCD",  # ← внутренний номер для фронте
        "provider_tracking_number": "12345678901234",  # ← DPD parcelNumber
        "provider": "dpd",
        "status": "created",
        "pickup_code": "123456",  # Код для пакомата
        "created_at": "2024-01-15T10:30:00"
    }
    ```
    """
    service = DeliveryService(db)
    
    try:
        delivery = service.create_delivery(delivery_data)
        return delivery
    except ValueError as e:
        raise HTTPException(
            status_code=400,
            detail=_delivery_error_detail(error=e, delivery_data=delivery_data)
        )
    except Exception as e:
        logger.error(f"Unexpected error during delivery creation: {e}")
        raise HTTPException(
            status_code=500,
            detail=_delivery_error_detail(error=e, delivery_data=delivery_data)
        )


# === TRACKING & STATUS ===

@delivery_router.get("/tracking/{tracking_number}", response_model=DeliveryTrackingResponse)
async def track_delivery(
    tracking_number: str,
    db: Session = Depends(get_session)
):
    """
    Отслеживание доставки по внутреннему трекинг-номеру.
    
    Публичный endpoint - не требует авторизации.
    
    Возвращает:
    - Текущий статус
    - Историю изменений статуса
    - Информацию о пункте выдачи
    """
    service = DeliveryService(db)
    delivery = service.get_delivery_by_tracking(tracking_number)
    
    if not delivery:
        raise HTTPException(status_code=404, detail="Delivery not found")
    
    history = service.get_delivery_history(delivery.id)
    
    return DeliveryTrackingResponse(
        tracking_number=delivery.tracking_number,
        status=delivery.status,
        provider=delivery.provider,
        delivery_city=delivery.delivery_city,
        pickup_point_name=delivery.pickup_point_name,
        created_at=delivery.created_at,
        estimated_delivery_date=delivery.estimated_delivery_date,
        status_history=[
            {
                "status": h.status,
                "notes": h.notes,
                "created_at": h.created_at.isoformat()
            }
            for h in history
        ]
    )


@delivery_router.get("/order-page/{tracking_number}", response_model=OrderTrackingPageResponse)
async def order_tracking_page(
    tracking_number: str,
    db: Session = Depends(get_session)
):
    """
    Данные для страницы заказа (domain/orders/{tracking_number}).
    
    Возвращает:
    - Текущую стадию доставки (paid, in_transit, ready_for_pickup, picked_up)
    - Флаги доступных действий (can_mark_received, can_leave_review)
    - Полную историю статусов
    """
    service = DeliveryService(db)
    delivery = service.get_delivery_by_tracking(tracking_number)

    if not delivery:
        raise HTTPException(status_code=404, detail="Delivery not found")

    history = service.get_delivery_history(delivery.id)

    stage_map = {
        "created": "paid",
        "in_transit": "in_transit",
        "at_pickup_point": "ready_for_pickup",
        "picked_up": "picked_up",
        "cancelled": "cancelled",
        "returned": "cancelled"
    }

    current_stage = stage_map.get(delivery.status, delivery.status)
    is_received = delivery.status == "picked_up"

    return OrderTrackingPageResponse(
        tracking_number=delivery.tracking_number,
        order_id=delivery.order_id,
        status=delivery.status,
        provider=delivery.provider,
        stage=current_stage,
        can_mark_received=delivery.status == "at_pickup_point",
        can_leave_review=True,
        delivery_city=delivery.delivery_city,
        pickup_point_name=delivery.pickup_point_name,
        estimated_delivery_date=delivery.estimated_delivery_date,
        picked_up_at=delivery.picked_up_at if is_received else None,
        status_history=[
            {
                "status": item.status,
                "notes": item.notes,
                "created_at": item.created_at.isoformat()
            }
            for item in history
        ]
    )


@delivery_router.get("/order/{order_id}", response_model=DeliveryResponse)
async def get_delivery_by_order(
    order_id: int,
    db: Session = Depends(get_session)
):
    """
    Получение доставки по ID заказа.
    
    Используется posts-service для проверки статуса доставки.
    """
    service = DeliveryService(db)
    delivery = service.get_delivery_by_order(order_id)
    
    if not delivery:
        raise HTTPException(status_code=404, detail="Delivery for this order not found")
    
    return delivery


@delivery_router.post("/orders/{order_id}/after-payment")
async def order_paid_handler(
    request: Request,
    order_id: int,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_session)
):
    service = DeliveryService(db)
    
    try:
        delivery = service.get_delivery_by_order(order_id)
        
        if not delivery:
            logger.warning(f"No delivery found for order {order_id}")
            return {"ok": True}
        
        logger.info(f"Payment success handler | order_id={order_id} | delivery_id={delivery.id}")
        
        background_tasks.add_task(_simulate_dpd_delivery, delivery.id, db)
        
        return {"ok": True, "delivery_id": delivery.id}
    
    except Exception as e:
        logger.error(f"Payment success handler failed: {e}")
        return {"ok": True}
    

async def _simulate_dpd_delivery(delivery_id: int, db: Session):
    import asyncio
    from models import DeliveryStatusUpdate
    
    service = DeliveryService(db)
    
    try:
        delivery = db.get(Delivery, delivery_id)
        if not delivery:
            return
        
        logger.info(f"Starting DPD delivery simulation | delivery_id={delivery_id}")
        
        # Этап 1: в пути (сразу)
        if delivery.status == "created":
            service.update_delivery_status(
                delivery_id,
                DeliveryStatusUpdate(
                    status="in_transit",
                    notes="DPD simulation: Picked up by courier"
                )
            )
        
        # Этап 2: в пункте выдачи (через 2 сек)
        await asyncio.sleep(2)

        delivery = db.get(Delivery, delivery_id)
        if delivery and delivery.status == "in_transit":
            service.update_delivery_status(
                delivery_id,
                DeliveryStatusUpdate(
                    status="at_pickup_point",
                    notes="DPD simulation: Delivered to pickup point"
                )
            )

        # Этап 3: получено покупателем (через 10 сек — симуляция скана PIN у пакомата)
        await asyncio.sleep(10)

        delivery = db.get(Delivery, delivery_id)
        if delivery and delivery.status == "at_pickup_point":
            service.update_delivery_status(
                delivery_id,
                DeliveryStatusUpdate(
                    status="picked_up",
                    notes="DPD simulation: Picked up by recipient"
                )
            )

        logger.info(f"DPD delivery simulation completed | delivery_id={delivery_id}")
    
    except Exception as e:
        logger.error(f"DPD delivery simulation failed: {e}")
    

@delivery_router.post("/{delivery_id}/status")
async def update_delivery_status_universal(
    request: Request,
    delivery_id: int,
    status: str = Query(..., description="Новый статус"),
    notes: str = Query(None, description="Опциональные заметки"),
    db: Session = Depends(get_session)
):
    service = DeliveryService(db)
    
    valid_statuses = ["created", "in_transit", "at_pickup_point", "picked_up", "cancelled", "returned"]
    if status not in valid_statuses:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid status. Must be one of: {', '.join(valid_statuses)}"
        )
    
    try:
        delivery = service.update_delivery_status(
            delivery_id,
            DeliveryStatusUpdate(
                status=status,
                notes=notes or f"Status updated to {status}"
            )
        )
        return delivery
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to update status: {str(e)}")

# === WEBHOOKS ===

@delivery_router.post("/dpd/webhook")
async def dpd_webhook(
    request: Request,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_session)
):
    """
    ⚡ DPD push callback для обновления статуса.
    
    Подписка через DPD API: /status/events/subscribetoparcel
    
    Параметры:
    - parcelnumber: 14-значный номер посылки (provider_tracking_number)
    - callbackurl: https://imarket.lv/api/v1/delivery/dpd/webhook
    
    ⚠️ Требует публичный HTTPS URL!
    - В dev используй ngrok или похожее
    - В production укажи правильный URL в DELIVERY_SERVICE_URL
    
    Формат входящего webhook:
    ```json
    {
        "parcelNumber": "12345678901234",
        "details": [
            {
                "status": "En route",
                "dateTime": "2024-01-15 14:30:00"
            }
        ]
    }
    ```
    """
    try:
        payload = await request.json()
        
        parcel_number = payload.get("parcelNumber")
        if not parcel_number:
            logger.warning("DPD webhook: missing parcelNumber")
            return {"ok": True}  # всегда 200, иначе DPD повторяет запрос
        
        # Находим доставку по provider_tracking_number (DPD parcelNumber)
        service = DeliveryService(db)
        delivery = service.get_delivery_by_provider_tracking(str(parcel_number))
        
        if not delivery:
            logger.warning(f"DPD webhook: delivery not found for parcel {parcel_number}")
            return {"ok": True}
        
        logger.info(
            f"DPD webhook received | order_id={delivery.order_id} | parcel={parcel_number}"
        )
        
        # Синхронизируем статус в фоне
        background_tasks.add_task(service.sync_dpd_tracking, delivery.id)
        
        return {"ok": True}
    
    except json.JSONDecodeError:
        logger.error("DPD webhook: invalid JSON")
        return {"ok": True}
    except Exception as e:
        logger.error(f"DPD webhook error: {e}")
        return {"ok": True}


# === ADMIN & LIST ===

@delivery_router.get("/", response_model=list[DeliveryResponse])
async def list_deliveries(
    status: Optional[str] = Query(None, description="Filter by status"),
    provider: Optional[str] = Query(None, description="Filter by provider"),
    limit: int = Query(50, le=100),
    db: Session = Depends(get_session)
):
    """
    Список доставок с фильтрацией.
    
    Для администрирования и отладки.
    """
    query = select(Delivery)
    
    if status:
        query = query.where(Delivery.status == status)
    
    if provider:
        query = query.where(Delivery.provider == provider)
    
    query = query.limit(limit).order_by(Delivery.created_at.desc())
    
    deliveries = db.exec(query).all()
    return deliveries


@delivery_router.get("/health")
async def health_check():
    """Health check endpoint для Docker"""
    return {
        "status": "healthy",
        "service": "delivery",
        "version": "2.0"
    }


