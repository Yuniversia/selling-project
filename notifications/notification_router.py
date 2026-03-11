# notification_router.py - API роутеры для notification service

from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session, select
from typing import Optional

from database import get_session
from models import (
    SendNotificationRequest, SendNotificationResponse,
    NotificationHistoryResponse, NotificationLog,
    NotificationType, NotificationChannel, OrderNotificationData
)
from notification_service import NotificationService

notification_router = APIRouter(prefix="/api/v1/notifications", tags=["Notifications"])


@notification_router.post("/send", response_model=SendNotificationResponse)
async def send_notification(
    request: SendNotificationRequest,
    db: Session = Depends(get_session)
):
    """
    Универсальный эндпоинт для отправки уведомлений
    
    Поддерживаемые типы:
    - ORDER_PAID: SMS уведомление после оплаты (продавцу и покупателю)
    - ORDER_REVIEW_REQUEST: SMS запрос на отзыв
    """
    service = NotificationService(db)
    
    notification_ids = []
    errors = []
    
    try:
        # Обрабатываем разные типы уведомлений
        if request.notification_type == NotificationType.ORDER_PAID:
            # Отправляем продавцу и покупателю SMS
            success, ids, errs = service.send_order_paid_notification(request.order_data)
            notification_ids.extend(ids)
            errors.extend(errs)
        
        elif request.notification_type == NotificationType.ORDER_REVIEW_REQUEST:
            success, ids, errs = service.send_review_request(request.order_data)
            notification_ids.extend(ids)
            errors.extend(errs)
        
        else:
            return SendNotificationResponse(
                success=False,
                message=f"Notification type {request.notification_type} not implemented",
                errors=[f"Unknown notification type: {request.notification_type}"]
            )
        
        # Формируем ответ
        if len(errors) == 0:
            return SendNotificationResponse(
                success=True,
                message="All notifications sent successfully",
                notification_ids=notification_ids
            )
        elif len(notification_ids) > 0:
            return SendNotificationResponse(
                success=True,
                message="Some notifications sent with errors",
                notification_ids=notification_ids,
                errors=errors
            )
        else:
            return SendNotificationResponse(
                success=False,
                message="Failed to send notifications",
                errors=errors
            )
    
    except Exception as e:
        return SendNotificationResponse(
            success=False,
            message=f"Error sending notifications: {str(e)}",
            errors=[str(e)]
        )


@notification_router.post("/order-paid")
async def notify_order_paid(
    order_data: OrderNotificationData,
    db: Session = Depends(get_session)
):
    """
    Уведомление об оплате заказа
    
    Отправляет:
    - Продавцу: SMS о покупке товара
    - Покупателю: SMS об успешной оплате + номер отслеживания
    """
    request = SendNotificationRequest(
        notification_type=NotificationType.ORDER_PAID,
        channel=NotificationChannel.SMS,
        order_data=order_data
    )
    return await send_notification(request, db)


@notification_router.post("/order-delivered")
async def notify_order_delivered(
    order_data: OrderNotificationData,
    db: Session = Depends(get_session)
):
    """
    Уведомление о доставке заказа
    
    Отправляет покупателю SMS с благодарностью и ссылкой для отзыва
    """
    request = SendNotificationRequest(
        notification_type=NotificationType.ORDER_REVIEW_REQUEST,
        channel=NotificationChannel.SMS,
        order_data=order_data
    )
    return await send_notification(request, db)


@notification_router.get("/history", response_model=list[NotificationHistoryResponse])
async def get_notification_history(
    order_id: Optional[int] = None,
    email: Optional[str] = None,
    phone: Optional[str] = None,
    limit: int = 50,
    db: Session = Depends(get_session)
):
    """
    Получение истории отправленных уведомлений
    
    Фильтры:
    - order_id: По номеру заказа
    - email: По email получателя
    - phone: По телефону получателя
    - limit: Максимальное количество записей (по умолчанию 50)
    """
    statement = select(NotificationLog)
    
    # Применяем фильтры
    if order_id:
        statement = statement.where(NotificationLog.order_id == order_id)
    if email:
        statement = statement.where(NotificationLog.recipient_email == email)
    if phone:
        statement = statement.where(NotificationLog.recipient_phone == phone)
    
    # Сортировка и лимит
    statement = statement.order_by(NotificationLog.created_at.desc()).limit(limit)
    
    notifications = db.exec(statement).all()
    
    return [
        NotificationHistoryResponse(
            id=n.id,
            notification_type=n.notification_type,
            channel=n.channel,
            recipient_email=n.recipient_email,
            recipient_phone=n.recipient_phone,
            status=n.status,
            created_at=n.created_at,
            sent_at=n.sent_at,
            error_message=n.error_message
        )
        for n in notifications
    ]


@notification_router.get("/health")
async def health_check():
    """Проверка работоспособности сервиса"""
    return {
        "status": "healthy",
        "service": "notification-service",
        "version": "1.0.0"
    }
