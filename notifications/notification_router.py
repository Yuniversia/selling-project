# notification_router.py - API роутеры для notification service

from fastapi import APIRouter, Depends, HTTPException, Cookie, status
from sqlmodel import Session, select
from typing import Optional
from datetime import datetime
from jose import jwt
import logging

from database import get_session
from configs import configs
from models import (
    SendNotificationRequest, SendNotificationResponse,
    NotificationHistoryResponse, NotificationLog,
    NotificationType, NotificationChannel, OrderNotificationData
)
from notification_service import NotificationService, SendBerryService

notification_router = APIRouter(prefix="/api/v1/notifications", tags=["Notifications"])
logger = logging.getLogger("notification.router")


def _decode_user(access_token: Optional[str]) -> dict:
    if not access_token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Требуется авторизация")

    try:
        payload = jwt.decode(access_token, configs.secret_key, algorithms=[configs.token_algoritm])
    except Exception:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Недействительный токен")

    if not payload.get("user_id"):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Некорректный токен")

    return payload


def _check_admin(access_token: Optional[str]) -> dict:
    payload = _decode_user(access_token)
    if payload.get("user_type", "regular") not in ["admin", "support"]:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Доступ запрещен")
    return payload


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


@notification_router.post("/pickup-notification")
async def notify_pickup(
    pickup_data: dict,
    db: Session = Depends(get_session)
):
    """
    Уведомление о личной встрече/pickup
    
    Отправляет продавцу SMS с информацией о встрече и покупателе
    """
    logger.info(f"Pickup notification | order_id={pickup_data.get('order_id')} | seller_id={pickup_data.get('seller_id')}")
    
    service = NotificationService(db)
    
    try:
        seller_phone = pickup_data.get("seller_phone")
        seller_email = pickup_data.get("seller_email")
        contact_preference = pickup_data.get("contact_preference", "email").lower()
        
        buyer_name = pickup_data.get("buyer_name", "Покупатель")
        buyer_phone = pickup_data.get("buyer_phone", "не указан")
        buyer_email = pickup_data.get("buyer_email", "не указан")
        meeting_address = pickup_data.get("meeting_address", "адрес не указан")
        product_name = pickup_data.get("product_name", "Товар")
        order_id = pickup_data.get("order_id", "?")
        
        message = f"Заказ #{order_id}: {buyer_name} хочет купить '{product_name}'. Встреча: {meeting_address}. Контакт: {buyer_phone}"
        
        notification_ids = []
        errors = []
        
        # Отправляем в зависимости от предпочтения контакта
        if contact_preference == "phone" and seller_phone:
            logger.info(f"Sending SMS to seller phone: {seller_phone}")
            sendberry = SendBerryService()
            result = sendberry.send_sms(seller_phone, message)
            if result.get("success"):
                notification_ids.append(result.get("message_id"))
            else:
                errors.append(f"SMS send failed: {result.get('error')}")
        elif seller_phone:  # Fallback to phone if email fails
            logger.info(f"Email not available or preferred, sending SMS to: {seller_phone}")
            sendberry = SendBerryService()
            result = sendberry.send_sms(seller_phone, message)
            if result.get("success"):
                notification_ids.append(result.get("message_id"))
            else:
                errors.append(f"SMS send failed: {result.get('error')}")
        
        return {
            "success": len(errors) == 0,
            "notification_ids": notification_ids,
            "errors": errors,
            "message": "Pickup notification processed" if len(errors) == 0 else "Pickup notification sent with errors"
        }
    
    except Exception as e:
        logger.error(f"Pickup notification error: {str(e)}")
        return {
            "success": False,
            "notification_ids": [],
            "errors": [str(e)],
            "message": "Pickup notification failed"
        }



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


@notification_router.get("/balance")
async def get_notifications_balance(
    access_token: Optional[str] = Cookie(None),
):
    _check_admin(access_token)

    service = SendBerryService()
    success, data, error = service.get_balance()
    if not success or not data:
        logger.error(f"Notifications balance failed: {error}")
        raise HTTPException(status_code=503, detail=error or "Failed to fetch notifications balance")

    data["last_synced"] = datetime.utcnow().isoformat()
    return {
        "status": "success",
        "data": data,
    }
