# order_router.py - Роутер для системы покупки и доставки

import logging
from fastapi import APIRouter, Depends, HTTPException, Request, Cookie
from sqlmodel import Session, select
from typing import Optional
from jose import jwt
import secrets
import string
from datetime import datetime
import httpx

from database import get_session
from models_v2 import (
    Order, OrderCreate, OrderResponse,
    Product, DeliveryMethod, OrderStatus, User,
    OrderReview, OrderIssue, OrderPageReviewCreate,
    OrderIssueCreate, OrderIssueStatus
)
from configs import Configs

order_router = APIRouter(prefix="/api/v1/orders", tags=["Orders"])
logger = logging.getLogger("posts.order_router")


def product_name(product: Optional[Product]) -> str:
    if not product:
        return "Product"
    attrs = product.attributes or {}
    return attrs.get("model") or product.title or "Product"


def product_model_text(product: Optional[Product]) -> Optional[str]:
    if not product:
        return None
    attrs = product.attributes or {}
    memory = attrs.get("memory")
    color = attrs.get("color")
    if memory and color:
        return f"{memory}GB {color}"
    return None


async def send_notification_async(endpoint: str, data: dict):
    """Асинхронная отправка уведомления через notification service"""
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            # Используем прямой endpoint для отправки SMS
            response = await client.post(
                f"{Configs.NOTIFICATION_SERVICE_URL}/api/v1/notifications/{endpoint}",
                json=data
            )
            if response.status_code == 200:
                result = response.json()
                logger.info(
                    f"Notification sent | type={endpoint} | order_id={data.get('order_id')} | "
                    f"ids={result.get('notification_ids', [])}"
                )
                return result
            else:
                logger.warning(
                    f"Notification failed | type={endpoint} | order_id={data.get('order_id')} | "
                    f"HTTP {response.status_code}"
                )
                return None
    except Exception as e:
        logger.error(f"Notification error | type={endpoint} | order_id={data.get('order_id')} | {e}")
        return None


async def get_delivery_info(order_id: int) -> Optional[dict]:
    """Получение информации о доставке из delivery-service"""
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            response = await client.get(
                f"{Configs.DELIVERY_SERVICE_URL}/api/v1/delivery/order/{order_id}"
            )
            if response.status_code == 200:
                delivery = response.json()
                logger.info(f"Delivery info fetched | order_id={order_id}")
                return delivery
            elif response.status_code == 404:
                logger.debug(f"No delivery for order_id={order_id} (pickup or not created yet)")
                return None
            else:
                logger.warning(f"Delivery service error | order_id={order_id} | HTTP {response.status_code}")
                return None
    except Exception as e:
        logger.error(f"Delivery info fetch error | order_id={order_id} | {e}")
        return None


async def get_delivery_by_tracking(tracking_number: str) -> Optional[dict]:
    """Получение информации о доставке по tracking_number из delivery-service"""
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            response = await client.get(
                f"{Configs.DELIVERY_SERVICE_URL}/api/v1/delivery/order-page/{tracking_number}"
            )
            if response.status_code == 200:
                return response.json()
            if response.status_code == 404:
                return None
            logger.warning(f"Delivery service error by tracking | HTTP {response.status_code}")
            return None
    except Exception as e:
        logger.error(f"Delivery tracking fetch error | {e}")
        return None


def get_current_user(access_token: str) -> dict:
    """Извлечение пользователя из JWT токена"""
    if not access_token:
        raise HTTPException(status_code=401, detail="Not authenticated")
    
    try:
        payload = jwt.decode(access_token, Configs.secret_key, algorithms=[Configs.token_algoritm])
        user_id = payload.get("user_id")
        if not user_id:
            logger.warning("Auth | token valid but no user_id in payload")
            raise HTTPException(status_code=401, detail="Invalid token")
        return {
            "user_id": user_id,
            "username": payload.get("username"),
            "user_type": payload.get("user_type", "regular")
        }
    except Exception as e:
        logger.warning(f"Auth | token validation failed: {type(e).__name__}")
        raise HTTPException(status_code=401, detail=f"Token validation failed: {str(e)}")


def generate_pickup_code() -> str:
    """Генерация 6-значного кода для получения из пакомата"""
    return ''.join(secrets.choice(string.digits) for _ in range(6))


def generate_confirmation_code() -> str:
    """Генерация 6-значного кода подтверждения"""
    return ''.join(secrets.choice(string.digits) for _ in range(6))


@order_router.post("/create", response_model=OrderResponse)
async def create_order(
    order_data: OrderCreate,
    access_token: str = Cookie(None),
    db: Session = Depends(get_session)
):
    """
    Создание заказа
    
    Шаги:
    1. Проверяем, что товар существует и активен
    2. Проверяем, что покупатель не является продавцом (если авторизован)
    3. Валидируем адрес доставки (если не pickup)
    4. Создаем заказ в статусе pending_payment
    5. Возвращаем данные для оплаты
    
    Заказ может быть создан как авторизованным, так и анонимным пользователем.
    """
    # Пытаемся получить текущего пользователя (опционально для анонимных покупок)
    buyer_id = None
    if access_token:
        try:
            user = get_current_user(access_token)
            buyer_id = user["user_id"]
        except HTTPException:
            # Анонимный пользователь - buyer_id остаётся None
            pass
    
    # Проверяем товар
    post = db.get(Product, order_data.post_id)
    if not post:
        raise HTTPException(status_code=404, detail="Товар не найден")
    
    if not post.active:
        raise HTTPException(status_code=400, detail="Товар уже не активен")
    
    if post.price is None:
        raise HTTPException(status_code=400, detail="Цена товара не указана")
    
    # Проверяем, что покупатель не продавец (только для авторизованных)
    if buyer_id and post.seller_id == buyer_id:
        raise HTTPException(status_code=400, detail="Нельзя купить собственный товар")
    
    # Проверяем адрес доставки
    if order_data.delivery_method in [DeliveryMethod.DPD, DeliveryMethod.OMNIVA]:
        if not all([
            order_data.delivery_address,
            order_data.delivery_city,
            order_data.delivery_zip
        ]):
            raise HTTPException(
                status_code=400,
                detail="Для доставки необходимо указать полный адрес"
            )
    
    # Проверяем все обязательные данные ПЕРЕД созданием заказа
    if not all([
        post.id,
        post.seller_id,
        post.price,
        order_data.first_name,
        order_data.last_name,
        order_data.email,
        order_data.phone,
        order_data.delivery_method
    ]):
        raise HTTPException(status_code=400, detail="Не все обязательные поля заполнены")
    
    # Создаем заказ
    try:
        order = Order(
            post_id=post.id,
            buyer_id=buyer_id,  # Может быть None для анонимных
            seller_id=post.seller_id,
            price=post.price,
            delivery_method=order_data.delivery_method.value,
            buyer_first_name=order_data.first_name,
            buyer_last_name=order_data.last_name,
            buyer_email=order_data.email,
            buyer_phone=order_data.phone,
            delivery_address=order_data.delivery_address,
            delivery_city=order_data.delivery_city,
            delivery_zip=order_data.delivery_zip,
            delivery_country=order_data.delivery_country,
            status=OrderStatus.PENDING_PAYMENT.value
            # confirmation_code генерируется только при mark_as_delivered
        )
        
        # Проверяем, что объект создан корректно
        if not order.seller_id or not order.price:
            raise HTTPException(status_code=500, detail="Ошибка создания заказа: некорректные данные")
        
        db.add(order)
        db.commit()
        db.refresh(order)
        
        # Финальная проверка что заказ сохранился в БД
        if not order.id:
            db.rollback()
            raise HTTPException(status_code=500, detail="Ошибка сохранения заказа в базу данных")
        
        # БЕЗОПАСНОСТЬ: НЕ логируем персональные данные (имя, email, телефон)
        logger.info(
            f"Order created | id={order.id} | "
            f"buyer_id={order.buyer_id or 'anonymous'} | seller_id={order.seller_id} | "
            f"post_id={order.post_id} | price=€{order.price} | status={order.status}"
        )
        
        # Отправляем уведомления продавцу и покупателю
        try:
            # Получаем информацию о продавце
            seller = db.get(User, post.seller_id)
            
            notification_data = {
                "post_id": order.post_id,
                "order_id": order.id,
                "seller_name": seller.name or seller.username if seller else "Продавец",
                "seller_email": seller.email if seller else None,
                "seller_phone": seller.phone if seller else None,
                "buyer_name": f"{order.buyer_first_name} {order.buyer_last_name}",
                "buyer_email": order.buyer_email,
                "buyer_phone": order.buyer_phone,
                "product_name": product_name(post),
                "product_model": product_model_text(post),
                "order_price": order.price,
                "delivery_method": order.delivery_method,
                "tracking_url": f"{Configs.FRONTEND_URL.rstrip('/')}/order?tracking={order.tracking_number}"
            }
            
            # Примечание: уведомления отправляются после оплаты в /pay endpoint
            # await send_notification_async("order-paid", notification_data)
            
        except Exception as e:
            logger.warning(f"Notification data prep failed | order_id={order.id} | {e}")
            # Продолжаем выполнение даже если подготовка данных не удалась
            
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        logger.error(f"Order create failed | {e}")
        raise HTTPException(status_code=500, detail=f"Ошибка создания заказа: {str(e)}")
    
    return OrderResponse(
        id=order.id,
        post_id=order.post_id,
        status=order.status,
        delivery_method=order.delivery_method,
        price=order.price,
        buyer_first_name=order.buyer_first_name,
        buyer_last_name=order.buyer_last_name,
        created_at=order.created_at
    )


@order_router.post("/pay")
async def process_payment(
    order_id: int,
    access_token: str = Cookie(None),
    lang: str = Cookie("ru"),
    db: Session = Depends(get_session)
):
    """
    Обработка оплаты (ЗАГЛУШКА)
    
    В реальном приложении здесь была бы интеграция с платёжной системой.
    Пока просто имитируем успешную оплату.
    
    После оплаты:
    1. Меняем статус на PAID
    2. Генерируем код для пакомата
    3. Деактивируем объявление
    4. Отправляем sms с кодом (пока имитация)
    """
    # Пытаемся получить текущего пользователя (может быть None для анонимных)
    user_id = None
    if access_token:
        try:
            user = get_current_user(access_token)
            user_id = user["user_id"]
        except HTTPException:
            user_id = None

    if lang not in ["ru", "lv", "en"]:
        lang = "ru"
    
    # Получаем заказ
    order = db.get(Order, order_id)
    if not order:
        raise HTTPException(status_code=404, detail="Заказ не найден")
    
    # Проверяем, что заказ принадлежит пользователю (если пользователь авторизован)
    if user_id and order.buyer_id and order.buyer_id != user_id:
        raise HTTPException(status_code=403, detail="Доступ запрещен")
    
    # Проверяем статус
    if order.status != OrderStatus.PENDING_PAYMENT.value:
        raise HTTPException(status_code=400, detail="Заказ уже оплачен или отменен")
    
    # === ИМИТАЦИЯ ПЛАТЕЖА ===
    # В реальности здесь был бы запрос к Stripe, PayPal и т.д.
    payment_successful = True  # ЗАГЛУШКА
    
    if not payment_successful:
        raise HTTPException(status_code=400, detail="Ошибка оплаты")
    
    # Обновляем заказ
    order.status = OrderStatus.PAID.value
    order.paid_at = datetime.utcnow()
    
    # Деактивируем объявление
    post = db.get(Product, order.post_id)
    if post:
        post.active = False
    
    db.commit()
    db.refresh(order)
    
    # Создаем доставку через delivery service (если не pickup)
    if order.delivery_method in [DeliveryMethod.DPD.value, DeliveryMethod.OMNIVA.value]:
        logger.info(f"Delivery create | order_id={order.id} | method={order.delivery_method}")
        try:
            # Получаем информацию о продавце для отправки
            seller = db.get(User, order.seller_id)
            
            delivery_data = {
                "post_id": order.post_id,
                "order_id": order.id,
                "provider": order.delivery_method,
                "recipient_name": f"{order.buyer_first_name} {order.buyer_last_name}",
                "recipient_phone": order.buyer_phone,
                "recipient_email": order.buyer_email,
                "sender_name": seller.name or seller.username if seller else "Продавец",
                "sender_phone": seller.phone if seller and seller.phone else "+37120000000",
                "delivery_address": order.delivery_address,
                "delivery_city": order.delivery_city,
                "delivery_zip": order.delivery_zip,
                "delivery_country": order.delivery_country or "Latvia",
                "notes": f"lang={lang}"
            }
            
            logger.debug(f"Delivery create request | order_id={order.id} | url={Configs.DELIVERY_SERVICE_URL}/api/v1/delivery/create")
            
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.post(
                    f"{Configs.DELIVERY_SERVICE_URL}/api/v1/delivery/create",
                    json=delivery_data
                )
                
                if response.status_code == 201:
                    delivery_info = response.json()
                    order.tracking_number = delivery_info.get("tracking_number")
                    db.commit()
                    logger.info(f"Delivery created | order_id={order.id}")
                else:
                    logger.warning(f"Delivery create failed | order_id={order.id} | HTTP {response.status_code}")
                    
        except Exception as e:
            logger.error(f"Delivery create error | order_id={order.id} | {e}")
            # Продолжаем выполнение даже если доставка не создалась
    else:
        logger.info(f"Delivery skipped | order_id={order.id} | method={order.delivery_method}")

    if not order.tracking_number:
        order.tracking_number = f"ORD{order.id}"
        db.commit()
        db.refresh(order)

    order_page_url = f"{Configs.FRONTEND_URL.rstrip('/')}/order?tracking={order.tracking_number}"
    
    # Отправляем уведомление об оплате (продавцу и покупателю)
    try:
        seller = db.get(User, order.seller_id)
        post = db.get(Product, order.post_id)
        
        notification_data = {
            "post_id": order.post_id,
            "order_id": order.id,
            "seller_name": seller.name or seller.username if seller else "Продавец",
            "seller_email": seller.email if seller else None,
            "seller_phone": seller.phone if seller else None,
            "buyer_name": f"{order.buyer_first_name} {order.buyer_last_name}",
            "buyer_email": order.buyer_email,
            "buyer_phone": order.buyer_phone,
            "product_name": product_name(post),
            "product_model": product_model_text(post),
            "order_price": order.price,
            "delivery_method": order.delivery_method,
            "tracking_url": order_page_url,
            "tracking_number": order.tracking_number,
            "language": lang,
        }
        
        # Отправляем асинхронно
        await send_notification_async("order-paid", notification_data)
    except Exception as e:
        logger.warning(f"Payment notification failed | order_id={order.id} | {e}")
    
    return {
        "success": True,
        "order_id": order.id,
        "tracking_number": order.tracking_number,
        "redirect_url": order_page_url,
        "status": order.status,
        "message": "Товар успешно куплен! Продавец получил уведомление и отправит товар в ближайшее время."
    }


@order_router.get("/tracking/{tracking_number}")
async def get_order_page_by_tracking(
    tracking_number: str,
    db: Session = Depends(get_session)
):
    """
    Публичные данные для страницы заказа: domain/orders/{tracking_number}

    Возвращает:
    - базовую информацию о заказе
    - текущую стадию доставки
    - отзыв (если оставлен)
    - жалобы/возвраты по заказу
    """
    order = db.exec(
        select(Order).where(Order.tracking_number == tracking_number)
    ).first()

    # Fallback: поддерживаем старые/альтернативные ссылки вида /orders/{order_id} или /orders/ORD{order_id}
    if not order:
        resolved_order_id = None

        if tracking_number.isdigit():
            resolved_order_id = int(tracking_number)
        elif tracking_number.startswith("ORD") and tracking_number[3:].isdigit():
            resolved_order_id = int(tracking_number[3:])

        if resolved_order_id is not None:
            order = db.get(Order, resolved_order_id)

    delivery_data = await get_delivery_by_tracking(tracking_number)

    if not order and delivery_data:
        order = db.get(Order, delivery_data.get("order_id"))

    if not order:
        raise HTTPException(status_code=404, detail="Заказ не найден")

    post = db.get(Product, order.post_id)

    review = db.exec(
        select(OrderReview).where(OrderReview.order_id == order.id)
    ).first()

    issues = db.exec(
        select(OrderIssue)
        .where(OrderIssue.order_id == order.id)
        .order_by(OrderIssue.created_at.desc())
    ).all()

    status_stage_map = {
        OrderStatus.PENDING_PAYMENT.value: "payment_pending",
        OrderStatus.PAID.value: "paid",
        OrderStatus.PROCESSING.value: "processing",
        OrderStatus.SHIPPED.value: "in_transit",
        OrderStatus.DELIVERED.value: "delivered",
        OrderStatus.COMPLETED.value: "received",
        OrderStatus.CANCELLED.value: "cancelled",
        OrderStatus.REFUNDED.value: "refunded"
    }

    effective_status = delivery_data.get("status") if delivery_data else order.status

    return {
        "order": {
            "order_id": order.id,
            "post_id": order.post_id,
            "tracking_number": order.tracking_number,
            "status": effective_status,
            "delivery_method": order.delivery_method,
            "product_name": product_name(post),
            "price": order.price,
            "created_at": order.created_at,
            "paid_at": order.paid_at,
            "shipped_at": order.shipped_at,
            "delivered_at": order.delivered_at,
            "completed_at": order.completed_at
        },
        "delivery": delivery_data,
        "review": {
            "id": review.id if review else order.id,
            "rating": order.review_rating if order.review_rating is not None else (review.seller_rating if review else None),
            "review_text": order.review_text if order.review_text is not None else (review.review_text if review else None),
            "updated_at": review.updated_at if review else order.completed_at or order.delivered_at or order.created_at
        } if order.review_rating is not None or order.review_text or review else None,
        "issues": [
            {
                "id": issue.id,
                "issue_type": issue.issue_type,
                "reason": issue.reason,
                "description": issue.description,
                "status": issue.status,
                "created_at": issue.created_at,
                "updated_at": issue.updated_at
            }
            for issue in issues
        ],
        "actions": {
            "can_leave_review": True,
            "can_open_issue": True
        }
    }


@order_router.post("/tracking/{tracking_number}/review")
async def leave_tracking_review(
    tracking_number: str,
    review_data: OrderPageReviewCreate,
    db: Session = Depends(get_session)
):
    """Оставить/обновить единый отзыв по tracking_number."""
    order = db.exec(
        select(Order).where(Order.tracking_number == tracking_number)
    ).first()
    if not order:
        raise HTTPException(status_code=404, detail="Заказ не найден")

    # Используем существующий функционал отзывов на заказе
    order.review_rating = review_data.rating
    order.review_text = review_data.review_text
    db.add(order)

    db.commit()
    db.refresh(order)

    # Пересчет рейтинга продавца
    seller = db.exec(select(User).where(User.id == order.seller_id)).first()
    if seller:
        rated_orders = db.exec(
            select(Order).where(
                Order.seller_id == order.seller_id,
                Order.review_rating.isnot(None)
            )
        ).all()
        if rated_orders:
            total = sum(item.review_rating for item in rated_orders if item.review_rating is not None)
            seller.rating = round(total / len(rated_orders), 2)
            db.add(seller)
            db.commit()

    return {
        "success": True,
        "order_id": order.id,
        "tracking_number": tracking_number,
        "review_id": order.id,
        "message": "Отзыв сохранен"
    }


@order_router.post("/tracking/{tracking_number}/issue")
async def create_tracking_issue(
    tracking_number: str,
    issue_data: OrderIssueCreate,
    db: Session = Depends(get_session)
):
    """Создать жалобу/заявку на возврат по tracking_number."""
    order = db.exec(
        select(Order).where(Order.tracking_number == tracking_number)
    ).first()
    if not order:
        raise HTTPException(status_code=404, detail="Заказ не найден")

    issue = OrderIssue(
        order_id=order.id,
        tracking_number=tracking_number,
        issue_type=issue_data.issue_type.value,
        reason=issue_data.reason,
        description=issue_data.description,
        status=OrderIssueStatus.OPEN.value
    )
    db.add(issue)
    db.commit()
    db.refresh(issue)

    return {
        "success": True,
        "order_id": order.id,
        "tracking_number": tracking_number,
        "issue": {
            "id": issue.id,
            "issue_type": issue.issue_type,
            "status": issue.status,
            "reason": issue.reason,
            "description": issue.description,
            "created_at": issue.created_at
        },
        "message": "Заявка создана"
    }


@order_router.post("/ship")
async def mark_as_shipped(
    order_id: int,
    access_token: str = Cookie(None),
    db: Session = Depends(get_session)
):
    """
    Продавец отмечает товар как "Отправлен"
    
    Упрощённая версия без реальной доставки:
    - Продавец нажимает "Отправлен"
    - Покупатель получает уведомление
    - Покупатель может подтвердить или отклонить получение
    """
    if not access_token:
        raise HTTPException(status_code=401, detail="Not authenticated")
    user = get_current_user(access_token)
    
    order = db.get(Order, order_id)
    if not order:
        raise HTTPException(status_code=404, detail="Заказ не найден")
    
    # Проверяем, что это продавец
    if order.seller_id != user["user_id"]:
        raise HTTPException(status_code=403, detail="Только продавец может отправить товар")
    
    if order.status != OrderStatus.PAID.value:
        raise HTTPException(status_code=400, detail="Заказ ещё не оплачен")
    
    # Обновляем статус
    order.status = OrderStatus.SHIPPED.value
    order.shipped_at = datetime.utcnow()
    
    db.commit()
    
    logger.info(f"Order shipped | order_id={order.id}")
    
    # Обновляем статус доставки в delivery service (если не pickup)
    if order.delivery_method in [DeliveryMethod.DPD.value, DeliveryMethod.OMNIVA.value]:
        logger.info(f"Delivery status update | order_id={order.id}")
        try:
            # Получаем доставку по order_id
            async with httpx.AsyncClient(timeout=10.0) as client:
                # Получаем delivery_id
                delivery_response = await client.get(
                    f"{Configs.DELIVERY_SERVICE_URL}/api/v1/delivery/order/{order.id}"
                )
                
                if delivery_response.status_code == 200:
                    delivery = delivery_response.json()
                    delivery_id = delivery.get("id")
                    
                    logger.debug(f"Delivery status → in_transit | order_id={order.id} | delivery_id={delivery_id}")
                    
                    # Обновляем статус на "in_transit"
                    update_response = await client.patch(
                        f"{Configs.DELIVERY_SERVICE_URL}/api/v1/delivery/{delivery_id}/status",
                        json={"status": "in_transit", "notes": "Посылка отправлена продавцом"}
                    )
                    
                    if update_response.status_code == 200:
                        logger.info(f"Delivery status updated to in_transit | order_id={order.id}")
                    else:
                        logger.warning(f"Delivery status update failed | order_id={order.id} | HTTP {update_response.status_code}")
                else:
                    logger.warning(f"Delivery not found for ship | order_id={order.id} | HTTP {delivery_response.status_code}")
                    
        except Exception as e:
            logger.error(f"Delivery status update error | order_id={order.id} | {e}")
            # Продолжаем выполнение
    else:
        logger.info(f"Delivery update skipped | order_id={order.id} | method={order.delivery_method}")
    
    return {
        "success": True,
        "message": "Товар отмечен как отправленный. Покупатель получит уведомление.",
        "order_id": order.id,
        "shipped_at": order.shipped_at
    }


@order_router.post("/review", response_model=dict)
async def leave_review(
    review_data: dict,
    access_token: str = Cookie(None),
    db: Session = Depends(get_session)
):
    """
    Покупатель оставляет отзыв на уже доставленный/завершенный заказ
    
    Заказ должен быть в статусе COMPLETED или DELIVERED
    Не меняет статус заказа - только сохраняет отзыв
    """
    if not access_token:
        raise HTTPException(status_code=401, detail="Not authenticated")
    user = get_current_user(access_token)
    
    order_id = review_data.get("order_id")
    rating = review_data.get("rating")
    review_text = review_data.get("review_text")
    
    if not order_id or rating is None:
        raise HTTPException(status_code=400, detail="order_id и rating обязательны")
    
    if not (0 <= rating <= 5):
        raise HTTPException(status_code=400, detail="Оценка должна быть от 0 до 5")
    
    order = db.get(Order, order_id)
    if not order:
        raise HTTPException(status_code=404, detail="Заказ не найден")
    
    # Проверяем, что это покупатель
    if order.buyer_id != user["user_id"]:
        raise HTTPException(status_code=403, detail="Только покупатель может оставить отзыв")
    
    # Покупатель может оставить отзыв если заказ DELIVERED или COMPLETED
    if order.status not in [OrderStatus.DELIVERED.value, OrderStatus.COMPLETED.value]:
        raise HTTPException(status_code=400, detail="Товар ещё не доставлен")
    
    if order.review_rating is not None:
        raise HTTPException(status_code=400, detail="Вы уже оставили отзыв на этот заказ")
    
    # Сохраняем отзыв
    order.review_rating = rating
    order.review_text = review_text
    
    db.add(order)
    db.commit()
    
    logger.info(f"Review saved | order_id={order.id} | rating={rating}/5")
    
    # Обновляем рейтинг продавца
    try:
        seller_statement = select(User).where(User.id == order.seller_id)
        seller = db.exec(seller_statement).first()
        
        if seller:
            # Обновляем рейтинг (среднее арифметическое)
            completed_orders = db.exec(
                select(Order).where(
                    Order.seller_id == order.seller_id,
                    Order.review_rating.isnot(None)
                )
            ).all()
            
            if completed_orders:
                total_rating = sum(o.review_rating for o in completed_orders if o.review_rating is not None)
                seller.rating = round(total_rating / len(completed_orders), 2)
                db.add(seller)
                db.commit()
            
            logger.info(f"Seller rating updated | order_id={order.id}")
    except Exception as e:
        logger.warning(f"Seller rating update failed | order_id={order.id} | {e}")
    
    return {
        "success": True,
        "message": "Спасибо за ваш отзыв!",
        "order_id": order.id,
        "rating": rating
    }


@order_router.get("/my-orders")
async def get_my_orders(
    access_token: str = Cookie(None),
    db: Session = Depends(get_session)
):
    """Получить все заказы пользователя (как покупателя) - БЕЗ ЛИЧНЫХ ДАННЫХ"""
    if not access_token:
        return {"orders": []}
    
    try:
        user = get_current_user(access_token)
        user_id = user["user_id"]
        logger.info(f"My orders | user_id={user_id}")
    except HTTPException as e:
        return {"orders": []}
    
    statement = select(Order).where(Order.buyer_id == user_id).order_by(Order.created_at.desc())
    orders = db.exec(statement).all()
    
    logger.info(f"My orders result | user_id={user_id} | count={len(orders)}")
    
    # Форматируем ответ БЕЗ личных данных (покупатель видит свои заказы)
    safe_orders = []
    for order in orders:
        # Получаем информацию о доставке из delivery-service
        delivery_info = None
        if order.delivery_method in ['omniva', 'dpd']:
            delivery_info = await get_delivery_info(order.id)
        
        order_response = OrderResponse(
            id=order.id,
            post_id=order.post_id,
            status=order.status,
            delivery_method=order.delivery_method,
            price=order.price,
            buyer_first_name=order.buyer_first_name,
            buyer_last_name=order.buyer_last_name,
            created_at=order.created_at,
            paid_at=order.paid_at,
            shipped_at=order.shipped_at,
            delivered_at=order.delivered_at,
            completed_at=order.completed_at,
            review_rating=order.review_rating,
            review_text=order.review_text
        )
        
        # Добавляем информацию о доставке если есть
        if delivery_info:
            order_response.tracking_number = delivery_info.get('tracking_number')
            order_response.pickup_code = delivery_info.get('pickup_code')
            order_response.delivery_status = delivery_info.get('status')
            order_response.delivery_provider = delivery_info.get('provider')
            order_response.estimated_delivery = delivery_info.get('estimated_delivery')
        
        safe_orders.append(order_response)
    
    return {"orders": safe_orders}


@order_router.get("/my-sales")
async def get_my_sales(
    access_token: str = Cookie(None),
    db: Session = Depends(get_session)
):
    """Получить все продажи пользователя (как продавца) - ТОЛЬКО ИМЯ ПОКУПАТЕЛЯ"""
    if not access_token:
        return {"sales": []}
    
    try:
        user = get_current_user(access_token)
        user_id = user["user_id"]
        logger.info(f"My sales | user_id={user_id}")
    except HTTPException as e:
        return {"sales": []}
    
    statement = select(Order).where(Order.seller_id == user_id).order_by(Order.created_at.desc())
    orders = db.exec(statement).all()
    
    logger.info(f"My sales result | user_id={user_id} | count={len(orders)}")
    
    # Форматируем ответ: продавец видит ТОЛЬКО ИМЯ покупателя (БЕЗ email/phone/адреса)
    safe_sales = []
    for order in orders:
        # Получаем информацию о доставке из delivery-service
        delivery_info = None
        if order.delivery_method in ['omniva', 'dpd']:
            delivery_info = await get_delivery_info(order.id)
        
        order_response = OrderResponse(
            id=order.id,
            post_id=order.post_id,
            status=order.status,
            delivery_method=order.delivery_method,
            price=order.price,
            buyer_name=f"{order.buyer_first_name} {order.buyer_last_name}",  # Только имя
            created_at=order.created_at,
            paid_at=order.paid_at,
            shipped_at=order.shipped_at,
            delivered_at=order.delivered_at,
            completed_at=order.completed_at,
            review_rating=order.review_rating,
            review_text=order.review_text
        )
        
        # Добавляем информацию о доставке если есть
        if delivery_info:
            order_response.tracking_number = delivery_info.get('tracking_number')
            order_response.pickup_code = delivery_info.get('pickup_code')
            order_response.delivery_status = delivery_info.get('status')
            order_response.delivery_provider = delivery_info.get('provider')
            order_response.estimated_delivery = delivery_info.get('estimated_delivery')
        
        safe_sales.append(order_response)
    
    return {"sales": safe_sales}


@order_router.get("/details")
async def get_order_details(
    order_id: int,
    access_token: str = Cookie(None),
    db: Session = Depends(get_session)
):
    """Получить детали заказа"""
    if not access_token:
        raise HTTPException(status_code=401, detail="Not authenticated")
    user = get_current_user(access_token)
    
    order = db.get(Order, order_id)
    if not order:
        raise HTTPException(status_code=404, detail="Заказ не найден")
    
    # Проверяем доступ (покупатель, продавец или админ)
    if order.buyer_id != user["user_id"] and order.seller_id != user["user_id"] and user["user_type"] not in ["admin", "support"]:
        raise HTTPException(status_code=403, detail="Доступ запрещен")
    
    # Получаем информацию о товаре
    post = db.get(Product, order.post_id)
    
    return {
        "order": order,
        "post": post
    }


@order_router.post("/delivery-received")
async def delivery_received_webhook(
    request: dict,
    db: Session = Depends(get_session)
):
    """
    Webhook от delivery-service: уведомление о том, что доставка получена покупателем
    
    Автоматически:
    1. Обновляет статус заказа на COMPLETED (не DELIVERED, сразу завершаем)
    2. Обновляет статистику продавца (sells_count, rating)
    3. Скрывает чаты связанные с заказом
    4. Отправляет уведомление покупателю с ссылкой на отзыв
    """
    order_id = request.get("order_id")
    tracking_number = request.get("tracking_number")
    picked_up_at = request.get("picked_up_at")
    language = request.get("language") or "ru"
    
    if not order_id:
        raise HTTPException(status_code=400, detail="order_id is required")
    
    logger.info(f"Delivery received webhook | order_id={order_id}")
    
    # Находим заказ
    order = db.get(Order, order_id)
    if not order:
        logger.warning(f"Delivery received | order_id={order_id} not found")
        raise HTTPException(status_code=404, detail="Заказ не найден")
    
    # Проверяем текущий статус
    if order.status not in [OrderStatus.SHIPPED.value, OrderStatus.PROCESSING.value]:
        logger.warning(f"Delivery received | order_id={order_id} | unexpected status={order.status}")
        return {
            "success": False,
            "message": f"Заказ имеет статус {order.status}, ожидался shipped или processing"
        }
    
    # Обновляем статус на COMPLETED (автоматическое подтверждение получения)
    order.status = OrderStatus.COMPLETED.value
    order.delivered_at = datetime.utcnow()
    order.completed_at = datetime.utcnow()
    order.confirmed_by_buyer = True  # Автоматическое подтверждение
    
    db.add(order)
    db.commit()
    db.refresh(order)
    
    logger.info(f"Order auto-completed | order_id={order_id}")
    
    # Обновляем статистику продавца (автоматически, как при подтверждении)
    try:
        seller_statement = select(User).where(User.id == order.seller_id)
        seller = db.exec(seller_statement).first()
        
        if seller:
            # +1 к продажам
            seller.sells_count += 1
            
            # Обновляем рейтинг (среднее арифметическое всех завершенных заказов с отзывами)
            completed_orders = db.exec(
                select(Order).where(
                    Order.seller_id == order.seller_id,
                    Order.review_rating.isnot(None)
                )
            ).all()
            
            if completed_orders:
                total_rating = sum(o.review_rating for o in completed_orders if o.review_rating is not None)
                seller.rating = round(total_rating / len(completed_orders), 2)
            
            db.add(seller)
            db.commit()
            
            logger.info(f"Seller stats updated | order_id={order_id}")
    except Exception as e:
        logger.warning(f"Seller stats update failed | order_id={order_id} | {e}")
    
    # Скрываем чаты связанные с этим заказом
    if order.buyer_id:
        try:
            buyer_id_for_chat = str(order.buyer_id)
            chat_api_url = "http://chat-service:4000/api/chat/chats/hide-for-order"
            
            logger.info(f"Hiding chats for completed order | order_id={order_id}")
            
            async with httpx.AsyncClient(timeout=5.0) as client:
                response = await client.post(
                    chat_api_url,
                    params={
                        "post_id": order.post_id,
                        "buyer_id": buyer_id_for_chat
                    }
                )
                
                if response.status_code == 200:
                    result = response.json()
                    logger.info(f"Chats hidden | post_id={order.post_id} | count={result.get('hidden_count', 0)}")
                else:
                    logger.warning(f"Chat hide failed | post_id={order.post_id} | HTTP {response.status_code}")
        except Exception as e:
            logger.error(f"Chat hide error | post_id={order.post_id} | {e}")
    
    # Отправляем SMS с благодарностью и ссылкой на отзыв
    try:
        seller = db.get(User, order.seller_id)
        post = db.get(Product, order.post_id)
        
        notification_data = {
            "post_id": order.post_id,
            "order_id": order.id,
            "seller_name": seller.name or seller.username if seller else "Продавец",
            "seller_email": seller.email if seller else None,
            "seller_phone": seller.phone if seller else None,
            "buyer_name": f"{order.buyer_first_name} {order.buyer_last_name}",
            "buyer_email": order.buyer_email,
            "buyer_phone": order.buyer_phone,
            "product_name": product_name(post),
            "product_model": product_model_text(post),
            "order_price": order.price,
            "delivery_method": order.delivery_method,
            "tracking_number": order.tracking_number or f"ORD{order.id}",
            "language": language,
            "review_url": f"{Configs.FRONTEND_URL.rstrip('/')}/order?tracking={order.tracking_number or f'ORD{order.id}'}"
        }
        
        # Отправляем асинхронно SMS с благодарностью и ссылкой на отзыв
        await send_notification_async("order-delivered", notification_data)
    except Exception as e:
        logger.warning(f"Review request SMS failed | order_id={order.id} | {e}")
    
    return {
        "success": True,
        "message": "Заказ автоматически завершён (получен покупателем)",
        "order_id": order.id,
        "status": order.status,
        "delivered_at": order.delivered_at,
        "completed_at": order.completed_at
    }
