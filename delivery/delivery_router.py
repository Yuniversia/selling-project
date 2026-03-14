# delivery_router.py - API endpoints для delivery service

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlmodel import Session, select
from typing import Optional

from database import get_session
from models import (
    Delivery, DeliveryCreate, DeliveryResponse, 
    DeliveryStatusUpdate, DeliveryTrackingResponse,
    OrderTrackingPageResponse,
    DeliveryStatusHistory
)
from delivery_service import DeliveryService


delivery_router = APIRouter(prefix="/api/v1/delivery", tags=["Delivery"])


@delivery_router.post("/create", response_model=DeliveryResponse, status_code=201)
async def create_delivery(
    delivery_data: DeliveryCreate,
    db: Session = Depends(get_session)
):
    """
    Создание новой доставки
    
    Обычно вызывается автоматически при создании заказа из posts-service
    """
    service = DeliveryService(db)
    
    try:
        delivery = service.create_delivery(delivery_data)
        return delivery
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to create delivery: {str(e)}")


@delivery_router.get("/tracking/{tracking_number}", response_model=DeliveryTrackingResponse)
async def track_delivery(
    tracking_number: str,
    db: Session = Depends(get_session)
):
    """
    Отслеживание доставки по трекинг-номеру
    
    Публичный endpoint - не требует авторизации
    """
    service = DeliveryService(db)
    delivery = service.get_delivery_by_tracking(tracking_number)
    
    if not delivery:
        raise HTTPException(status_code=404, detail="Доставка не найдена")
    
    # Получаем историю статусов
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
    Данные для страницы заказа domain/orders/{tracking_number}

    Публичный endpoint для фронтенда: возвращает текущую стадию доставки,
    историю статусов и флаги доступных действий.
    """
    service = DeliveryService(db)
    delivery = service.get_delivery_by_tracking(tracking_number)

    if not delivery:
        raise HTTPException(status_code=404, detail="Доставка не найдена")

    history = service.get_delivery_history(delivery.id)

    stage_map = {
        "created": "created",
        "in_transit": "in_transit",
        "at_pickup_point": "ready_for_pickup",
        "picked_up": "received",
        "cancelled": "cancelled",
        "returned": "returned"
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
    Получение доставки по ID заказа
    
    Используется для проверки статуса доставки в posts-service
    """
    service = DeliveryService(db)
    delivery = service.get_delivery_by_order(order_id)
    
    if not delivery:
        raise HTTPException(status_code=404, detail="Доставка для этого заказа не найдена")
    
    return delivery


@delivery_router.patch("/{delivery_id}/status", response_model=DeliveryResponse)
async def update_delivery_status(
    delivery_id: int,
    status_update: DeliveryStatusUpdate,
    db: Session = Depends(get_session)
):
    """
    Обновление статуса доставки
    
    В реальном проекте будет вызываться webhook'ами от DPD/Omniva
    Пока используется для ручной имитации
    """
    service = DeliveryService(db)
    
    try:
        delivery = service.update_delivery_status(delivery_id, status_update)
        return delivery
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to update status: {str(e)}")


@delivery_router.post("/{delivery_id}/simulate", response_model=DeliveryResponse)
async def simulate_delivery(
    delivery_id: int,
    db: Session = Depends(get_session)
):
    """
    Имитация начала процесса доставки (для тестирования)
    
    Переводит доставку в статус "В пути"
    """
    service = DeliveryService(db)
    
    try:
        delivery = service.simulate_delivery_process(delivery_id)
        return delivery
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to simulate delivery: {str(e)}")


@delivery_router.post("/{delivery_id}/deliver-to-pickup-point", response_model=DeliveryResponse)
async def deliver_to_pickup_point(
    delivery_id: int,
    db: Session = Depends(get_session)
):
    """
    Имитация доставки в пункт выдачи
    
    - Переводит статус в "at_pickup_point"
    - Генерирует 6-значный код
    - Отправляет SMS с кодом получения
    """
    service = DeliveryService(db)
    
    try:
        delivery = service.update_delivery_status(
            delivery_id,
            DeliveryStatusUpdate(
                status="at_pickup_point",
                notes="Посылка прибыла в пункт выдачи"
            )
        )
        return delivery
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to deliver: {str(e)}")


@delivery_router.post("/{delivery_id}/mark-picked-up", response_model=DeliveryResponse)
async def mark_as_picked_up(
    delivery_id: int,
    pickup_code: str = Query(..., description="6-значный код получения"),
    db: Session = Depends(get_session)
):
    """
    Отметить посылку как полученную
    
    - Проверяет код получения
    - Переводит в статус "picked_up"
    - Отправляет SMS с благодарностью + ссылкой на отзыв
    """
    service = DeliveryService(db)
    delivery = db.get(Delivery, delivery_id)
    
    if not delivery:
        raise HTTPException(status_code=404, detail="Доставка не найдена")
    
    # Проверяем код получения
    if delivery.pickup_code != pickup_code:
        raise HTTPException(status_code=403, detail="Неверный код получения")
    
    try:
        delivery = service.update_delivery_status(
            delivery_id,
            DeliveryStatusUpdate(
                status="picked_up",
                notes="Посылка получена покупателем"
            )
        )
        return delivery
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to mark as picked up: {str(e)}")


@delivery_router.get("/", response_model=list[DeliveryResponse])
async def list_deliveries(
    status: Optional[str] = Query(None, description="Фильтр по статусу"),
    provider: Optional[str] = Query(None, description="Фильтр по провайдеру"),
    limit: int = Query(50, le=100),
    db: Session = Depends(get_session)
):
    """
    Список доставок с фильтрацией
    
    Для администрирования
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
        "service": "delivery"
    }
