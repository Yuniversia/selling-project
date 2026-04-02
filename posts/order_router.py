# order_router.py - Роутер для системы покупки и доставки

import logging
import os
from fastapi import APIRouter, Depends, HTTPException, Request, Cookie, Query
from fastapi.responses import RedirectResponse
from sqlmodel import Session, select
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from typing import Optional
from jose import jwt
import secrets
import string
import uuid
from datetime import datetime
import httpx

from database import get_session
from models_v2 import (
    Order, OrderCreate, OrderResponse,
    Product, DeliveryMethod, OrderStatus, User,
    OrderReview, OrderIssue, OrderPageReviewCreate,
    OrderIssueCreate, OrderIssueStatus, PostReport
)
from configs import Configs

order_router = APIRouter(prefix="/api/v1/orders", tags=["Orders"])
logger = logging.getLogger("posts.order_router")


def safe_exception_name(exc: Exception) -> str:
    """Возвращает безопасный тип исключения без текста с параметрами/PII."""
    return type(exc).__name__


def extract_pg_integrity_meta(exc: IntegrityError) -> dict:
    """Безопасно извлекает метаданные ошибки БД без персональных данных."""
    orig = getattr(exc, "orig", None)
    diag = getattr(orig, "diag", None)
    return {
        "sqlstate": getattr(orig, "pgcode", None),
        "constraint": getattr(diag, "constraint_name", None),
        "column": getattr(diag, "column_name", None),
        "table": getattr(diag, "table_name", None),
    }


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
        logger.error(
            f"Notification error | type={endpoint} | order_id={data.get('order_id')} | "
            f"error_type={safe_exception_name(e)}"
        )
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
        logger.error(
            f"Delivery info fetch error | order_id={order_id} | error_type={safe_exception_name(e)}"
        )
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
        logger.error(f"Delivery tracking fetch error | error_type={safe_exception_name(e)}")
        return None


async def resolve_pickup_point_for_order(provider: str, system_point_id: str) -> Optional[dict]:
    """Проверка выбранного пакомата через delivery-service"""
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            response = await client.get(
                f"{Configs.DELIVERY_SERVICE_URL}/api/v1/delivery/pickup-points/resolve",
                params={
                    "provider": provider,
                    "system_point_id": system_point_id,
                }
            )
            if response.status_code != 200:
                logger.warning(
                    f"Pickup point resolve failed | provider={provider} | point={system_point_id} | HTTP {response.status_code}"
                )
                return None

            payload = response.json()
            if not payload.get("found"):
                return None
            return payload.get("pickup_point")
    except Exception as e:
        logger.error(
            f"Pickup point resolve error | provider={provider} | point={system_point_id} | error_type={safe_exception_name(e)}"
        )
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
        raise HTTPException(status_code=401, detail="Token validation failed")


def generate_pickup_code() -> str:
    """Генерация 6-значного кода для получения из пакомата"""
    return ''.join(secrets.choice(string.digits) for _ in range(6))


def generate_confirmation_code() -> str:
    """Генерация 6-значного кода подтверждения"""
    return ''.join(secrets.choice(string.digits) for _ in range(6))


async def finalize_order_after_successful_payment(
    *,
    db: Session,
    order: Order,
    lang: str,
) -> str:
    if order.status == OrderStatus.PAID.value:
        if not order.tracking_number:
            order.tracking_number = f"ORD{order.id}"
            db.commit()
            db.refresh(order)
        return f"{Configs.FRONTEND_URL.rstrip('/')}/order?tracking={order.tracking_number}"

    order.status = OrderStatus.PAID.value
    order.paid_at = datetime.utcnow()

    post = db.get(Product, order.post_id)
    if post:
        post.active = False

    db.commit()
    db.refresh(order)

    if order.delivery_method in [DeliveryMethod.DPD.value, DeliveryMethod.OMNIVA.value]:
        logger.info(f"Delivery create | order_id={order.id} | method={order.delivery_method}")
        try:
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
                "notes": f"lang={lang}",
            }

            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.post(
                    f"{Configs.DELIVERY_SERVICE_URL}/api/v1/delivery/create",
                    json=delivery_data,
                )

                if response.status_code == 201:
                    delivery_info = response.json()
                    order.tracking_number = delivery_info.get("tracking_number")
                    db.commit()
                    logger.info(f"Delivery created | order_id={order.id}")
                else:
                    logger.warning(f"Delivery create failed | order_id={order.id} | HTTP {response.status_code}")

        except Exception as e:
            logger.error(
                f"Delivery create error | order_id={order.id} | error_type={safe_exception_name(e)}"
            )
    else:
        logger.info(f"Delivery skipped | order_id={order.id} | method={order.delivery_method}")

    # === ФАЗА 3: УВЕДОМЛЕНИЕ ПРОДАВЦУ ДЛЯ PERSONAL_PICKUP ===
    if order.delivery_method == "personal_pickup":
        try:
            post = db.get(Product, order.post_id)
            seller = db.get(User, order.seller_id)
            
            # Получаем данные о встрече из атрибутов товара
            meeting_address = post.attributes.get("seller_meeting_address", "Адрес не указан") if post and post.attributes else "Адрес не указан"
            contact_preference = post.attributes.get("seller_contact_preference", "email") if post and post.attributes else "email"
            
            seller_notification_data = {
                "order_id": order.id,
                "seller_id": order.seller_id,
                "seller_email": seller.email if seller else None,
                "seller_phone": seller.phone if seller else None,
                "buyer_name": f"{order.buyer_first_name} {order.buyer_last_name}",
                "buyer_email": order.buyer_email,
                "buyer_phone": order.buyer_phone,
                "meeting_address": meeting_address,
                "contact_preference": contact_preference,
                "product_name": product_name(post),
            }
            
            # Отправляем специальное уведомление для личной встречи
            await send_notification_async("pickup-notification", seller_notification_data)
            logger.info(f"Pickup notification sent | order_id={order.id} | seller_id={order.seller_id}")
        except Exception as e:
            logger.warning(
                f"Pickup notification failed | order_id={order.id} | error_type={safe_exception_name(e)}"
            )

    if not order.tracking_number:
        order.tracking_number = f"ORD{order.id}"
        db.commit()
        db.refresh(order)

    order_page_url = f"{Configs.FRONTEND_URL.rstrip('/')}/order?tracking={order.tracking_number}"

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
        await send_notification_async("order-paid", notification_data)
    except Exception as e:
        logger.warning(
            f"Payment notification failed | order_id={order.id} | error_type={safe_exception_name(e)}"
        )

    return order_page_url


@order_router.post("/", response_model=OrderResponse)
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
    
    # === БЕЗОПАСНОСТЬ: Валидация стоимости доставки ===
    # Никогда не доверяем цене с фронтенда - проверяем по конфигурации
    expected_delivery_cost = {
        DeliveryMethod.PICKUP.value: Configs.DELIVERY_COST_PICKUP,
        DeliveryMethod.DPD.value: Configs.DELIVERY_COST_DPD,
        DeliveryMethod.OMNIVA.value: Configs.DELIVERY_COST_OMNIVA,
    }
    
    delivery_method_value = order_data.delivery_method.value if isinstance(order_data.delivery_method, DeliveryMethod) else order_data.delivery_method
    correct_delivery_cost = expected_delivery_cost.get(delivery_method_value)
    
    if correct_delivery_cost is None:
        raise HTTPException(status_code=400, detail="Неизвестный способ доставки")
    
    # Проверяем, что отправленная цена доставки совпадает с ожидаемой (допуск 0.01€ на погрешность округления)
    if abs(float(order_data.delivery_cost or 0) - float(correct_delivery_cost)) > 0.01:
        logger.warning(
            f"Delivery cost mismatch | post_id={order_data.post_id} | buyer_id={buyer_id or 'anonymous'} | "
            f"received={order_data.delivery_cost} | expected={correct_delivery_cost} | method={delivery_method_value}"
        )
        raise HTTPException(
            status_code=400, 
            detail="Стоимость доставки не совпадает с актуальной. Перезагрузите страницу и попробуйте снова"
        )
    
    # === КОНЕЦ ВАЛИДАЦИИ ===
    
    # Проверяем, что покупатель не продавец (только для авторизованных)
    if buyer_id and post.seller_id == buyer_id:
        raise HTTPException(status_code=400, detail="Нельзя купить собственный товар")
    
    normalized_delivery_address = order_data.delivery_address
    normalized_delivery_city = order_data.delivery_city
    normalized_delivery_zip = order_data.delivery_zip
    normalized_delivery_country = order_data.delivery_country
    normalized_locker_name = order_data.selected_locker_name

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

        if not order_data.selected_locker_id:
            raise HTTPException(
                status_code=400,
                detail="Для доставки через пакомат необходимо выбрать пункт выдачи"
            )

        resolved_pickup_point = await resolve_pickup_point_for_order(
            provider=order_data.delivery_method.value,
            system_point_id=order_data.selected_locker_id,
        )
        if not resolved_pickup_point:
            raise HTTPException(
                status_code=400,
                detail="Выбранный пункт выдачи не найден или не принадлежит выбранной службе доставки"
            )

        normalized_locker_name = resolved_pickup_point.get("name")
        normalized_delivery_address = resolved_pickup_point.get("address") or order_data.delivery_address
        normalized_delivery_city = resolved_pickup_point.get("city") or order_data.delivery_city
        normalized_delivery_zip = resolved_pickup_point.get("postal_code") or order_data.delivery_zip
        normalized_delivery_country = resolved_pickup_point.get("country_code") or order_data.delivery_country
    
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
            # === ФАЗА 2: Новые поля доставки ===
            delivery_cost=order_data.delivery_cost,
            selected_locker_id=order_data.selected_locker_id,
            selected_locker_name=normalized_locker_name,
            buyer_first_name=order_data.first_name,
            buyer_last_name=order_data.last_name,
            buyer_email=order_data.email,
            buyer_phone=order_data.phone,
            delivery_address=normalized_delivery_address,
            delivery_city=normalized_delivery_city,
            delivery_zip=normalized_delivery_zip,
            delivery_country=normalized_delivery_country,
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
        
        # БЕЗОПАСНОСТЬ: Логируем важные данные платежа (без PII)
        logger.info(
            f"Order created | id={order.id} | "
            f"buyer_id={order.buyer_id or 'anonymous'} | seller_id={order.seller_id} | "
            f"post_id={order.post_id} | price=€{order.price} | delivery_cost=€{order.delivery_cost} | "
            f"total=€{float(order.price) + float(order.delivery_cost)} | "
            f"delivery_method={order.delivery_method} | status={order.status}"
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
            logger.warning(
                f"Notification data prep failed | order_id={order.id} | error_type={safe_exception_name(e)}"
            )
            # Продолжаем выполнение даже если подготовка данных не удалась
            
    except HTTPException:
        raise
    except IntegrityError as e:
        db.rollback()
        meta = extract_pg_integrity_meta(e)
        logger.error(
            f"Order create failed | post_id={order_data.post_id} | buyer_id={buyer_id or 'anonymous'} | "
            f"error_type={safe_exception_name(e)} | sqlstate={meta.get('sqlstate')} | "
            f"table={meta.get('table')} | column={meta.get('column')} | "
            f"constraint={meta.get('constraint')}"
        )

        # Частый случай: в БД buyer_id всё ещё NOT NULL, а заказ создаёт аноним
        if buyer_id is None and meta.get("sqlstate") == "23502" and meta.get("column") == "buyer_id":
            raise HTTPException(status_code=401, detail="Для оформления заказа войдите в аккаунт")

        # Нарушение FK/UNIQUE/CHECK
        if meta.get("sqlstate") in {"23503", "23505", "23514"}:
            raise HTTPException(status_code=409, detail="Заказ не удалось создать из-за ограничения базы данных")

        raise HTTPException(
            status_code=500,
            detail="Ошибка создания заказа. Попробуйте позже или войдите в аккаунт"
        )
    except SQLAlchemyError as e:
        db.rollback()
        logger.error(
            f"Order create failed | post_id={order_data.post_id} | buyer_id={buyer_id or 'anonymous'} | "
            f"error_type={safe_exception_name(e)}"
        )
        raise HTTPException(status_code=500, detail="Ошибка базы данных при создании заказа")
    except Exception as e:
        db.rollback()
        logger.error(
            f"Order create failed | post_id={order_data.post_id} | buyer_id={buyer_id or 'anonymous'} | "
            f"error_type={safe_exception_name(e)}"
        )
        raise HTTPException(status_code=500, detail="Внутренняя ошибка при создании заказа")
    
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


@order_router.post("/{order_id}/payments")
async def process_payment(
    order_id: int,
    request: Request,
    access_token: str = Cookie(None),
    lang: str = Cookie("ru"),
    db: Session = Depends(get_session)
):
    """Создаёт Stripe Checkout Session и возвращает redirect_url на Stripe."""
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
    
    # === БЕЗОПАСНОСТЬ: Повторная валидация стоимости доставки перед платежом ===
    expected_delivery_cost = {
        DeliveryMethod.PICKUP.value: Configs.DELIVERY_COST_PICKUP,
        DeliveryMethod.DPD.value: Configs.DELIVERY_COST_DPD,
        DeliveryMethod.OMNIVA.value: Configs.DELIVERY_COST_OMNIVA,
    }
    
    correct_delivery_cost = expected_delivery_cost.get(order.delivery_method)
    if correct_delivery_cost is None:
        logger.error(
            f"Payment failed - invalid delivery method | order_id={order.id} | "
            f"delivery_method={order.delivery_method}"
        )
        raise HTTPException(status_code=400, detail="Некорректный способ доставки")
    
    # Проверяем, что delivery_cost в заказе совпадает с конфигурацией
    if abs(float(order.delivery_cost or 0) - float(correct_delivery_cost)) > 0.01:
        logger.warning(
            f"Payment rejected - delivery cost mismatch | order_id={order.id} | "
            f"stored={order.delivery_cost} | expected={correct_delivery_cost} | "
            f"method={order.delivery_method}"
        )
        raise HTTPException(status_code=400, detail="Стоимость доставки изменилась. Пожалуйста, создайте новый заказ")
    
    # === КОНЕЦ ВАЛИДАЦИИ ===
    
    # Stripe hosted checkout redirect
    # Сумма для оплаты включает цену товара + стоимость доставки
    total_price = float(order.price) + float(order.delivery_cost or 0)
    amount_cents = int(round(total_price * 100))
    request_id = request.headers.get("X-Request-ID") or str(uuid.uuid4())
    success_url = (
        f"{Configs.FRONTEND_URL.rstrip('/')}/api/v1/orders/{order.id}/payments/success"
        f"?session_id={{CHECKOUT_SESSION_ID}}&lang={lang}"
    )
    cancel_url = f"{Configs.FRONTEND_URL.rstrip('/')}/product?id={order.post_id}&payment=cancelled"

    payment_payload = {
        "amount_cents": amount_cents,
        "currency": "eur",
        "order_id": order.id,
        "post_id": order.post_id,
        "seller_id": order.seller_id,
        "buyer_email": order.buyer_email,
        "product_name": f"Order #{order.id}",
        "description": f"Payment for order #{order.id}",
        "success_url": success_url,
        "cancel_url": cancel_url,
        "metadata": {
            "flow": "posts-order-checkout",
            "delivery_method": order.delivery_method,
        },
    }
    
    logger.info(
        f"Payment initiated | order_id={order.id} | post_id={order.post_id} | "
        f"item_price=€{order.price} | delivery_cost=€{order.delivery_cost} | "
        f"total=€{total_price:.2f} | delivery_method={order.delivery_method}"
    )

    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            response = await client.post(
                f"{Configs.PAYMENTS_SERVICE_URL}/api/v1/payments/checkout-sessions",
                json=payment_payload,
                headers={"X-Request-ID": request_id},
                cookies={"access_token": access_token} if access_token else None,
            )

        if response.status_code not in (200, 201, 202):
            detail = "Payments service unavailable"
            try:
                payload = response.json()
                detail = payload.get("error", {}).get("message") or payload.get("detail") or detail
            except Exception:
                pass
            raise HTTPException(status_code=502, detail=f"Payment failed: {detail}")

        payment_result = response.json()
        payment_data = payment_result.get("data", payment_result)
        checkout_url = payment_data.get("checkout_url")
        if not checkout_url:
            raise HTTPException(status_code=502, detail="Payment checkout URL missing")

    except HTTPException:
        raise
    except Exception as exc:
        logger.error(
            "Payment service error | order_id=%s | error_type=%s",
            order.id,
            safe_exception_name(exc),
        )
        raise HTTPException(status_code=502, detail="Payment service error")
    
    return {
        "success": True,
        "order_id": order.id,
        "redirect_url": checkout_url,
        "status": order.status,
        "payment_request_id": request_id,
        "message": "Перенаправление на Stripe Checkout"
    }


@order_router.get("/{order_id}/payments/success")
async def payment_success_callback(
    order_id: int,
    session_id: str,
    lang: str = "ru",
    db: Session = Depends(get_session),
):
    if lang not in ["ru", "lv", "en"]:
        lang = "ru"

    order = db.get(Order, order_id)
    if not order:
        raise HTTPException(status_code=404, detail="Заказ не найден")

    if order.status == OrderStatus.PAID.value:
        tracking = order.tracking_number or f"ORD{order.id}"
        return RedirectResponse(url=f"{Configs.FRONTEND_URL.rstrip('/')}/order?tracking={tracking}", status_code=302)

    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            response = await client.get(
                f"{Configs.PAYMENTS_SERVICE_URL}/api/v1/payments/checkout-sessions/{session_id}"
            )
        if response.status_code != 200:
            return RedirectResponse(
                url=f"{Configs.FRONTEND_URL.rstrip('/')}/product?id={order.post_id}&payment=failed",
                status_code=302,
            )

        payload = response.json()
        data = payload.get("data", payload)
        is_paid = bool(data.get("paid"))
        if not is_paid:
            return RedirectResponse(
                url=f"{Configs.FRONTEND_URL.rstrip('/')}/product?id={order.post_id}&payment=not_paid",
                status_code=302,
            )
    except Exception:
        return RedirectResponse(
            url=f"{Configs.FRONTEND_URL.rstrip('/')}/product?id={order.post_id}&payment=verification_failed",
            status_code=302,
        )

    order_page_url = await finalize_order_after_successful_payment(db=db, order=order, lang=lang)
    return RedirectResponse(url=order_page_url, status_code=302)


@order_router.get("/shipments/{tracking_number}")
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
        OrderStatus.IN_TRANSIT.value: "in_transit",
        OrderStatus.READY_FOR_PICKUP.value: "ready_for_pickup",
        OrderStatus.PICKED_UP.value: "picked_up",
        OrderStatus.CONFIRMED.value: "confirmed",
        OrderStatus.CANCELLED.value: "cancelled",
        OrderStatus.REFUNDED.value: "refunded"
    }

    # Используем order.status как источник истины (это обновляется мгновенно при подтверждении)
    # delivery.status может быть асинхронно синхронизирован
    
    # === КОНСИСТЕНТНОСТЬ: Проверяем и синхронизируем расходящиеся статусы ===
    # ВАЖНО: Синхронизируем ТОЛЬКО если order еще не подтвержден!
    # Идея: delivery -> order (одностороннее)
    # Не перезаписываем if order.status == CONFIRMED
    if delivery_data:
        delivery_status = delivery_data.get("status")
        order_status = order.status
        
        if delivery_status and delivery_status != order_status:
            logger.warning(
                f"Status mismatch | tracking={tracking_number} | order_status={order_status} | delivery_status={delivery_status}"
            )
            
            # Если доставка уже прошла в статус picked_up, но order еще не обновлен (и еще не подтвержден), обновляем order
            # ВАЖНО: Не перезаписываем если order уже был подтвержден (status == CONFIRMED)
            if delivery_status == "picked_up" and order_status not in [OrderStatus.PICKED_UP.value, OrderStatus.CONFIRMED.value]:
                logger.info(
                    f"Auto-syncing order status | tracking={tracking_number} | from {order_status} to picked_up"
                )
                order.status = OrderStatus.PICKED_UP.value
                order.delivered_at = datetime.utcnow()
                db.add(order)
                db.commit()
                db.refresh(order)
    
    # ВАЖНО: Если пользователь подтвердил заказ (order_confirmed_at != None),
    # то effective_status = CONFIRMED, даже если order.status в БД еще не обновился!
    # Это критично для правильного расчета actions в frontend
    effective_status = OrderStatus.CONFIRMED.value if order.order_confirmed_at is not None else order.status

    # SECURITY: Передаем данные продавца о встречи и контактах ТОЛЬКО если заказ еще не забран (not picked_up)
    seller_meeting_address = None
    seller_contact_preference = None
    seller_phone = None
    seller_email = None
    
    # SECURITY: Отправляем контакты ТОЛЬКО если:
    # 1. Это личная встреча (pickup)
    # 2. Заказ еще НЕ забран (picked_up)
    # 3. Заказ еще НЕ подтвержден (confirmed)
    if (order.delivery_method == "pickup" and 
        effective_status != "picked_up" and 
        effective_status != "confirmed"):
        # Получаем данные продавца из attributes поста
        if post and post.attributes:
            seller_meeting_address = post.attributes.get("seller_meeting_address")
            seller_contact_preference = post.attributes.get("seller_contact_preference")
            seller_phone = post.attributes.get("seller_phone")
            seller_email = post.attributes.get("seller_email")

    # === ДИНАМИЧЕСКАЯ ЛОГИКА: Видимость форм зависит от статуса ===
    is_pickup = order.delivery_method == "pickup"
    is_delivery = order.delivery_method in ["dpd", "omniva"]
    order_confirmed = order.order_confirmed_at is not None
    
    # PICKUP: жалоба ДО подтверждения (status=PAID и заказ не подтвержден)
    can_open_issue_pickup = effective_status == OrderStatus.PAID.value and not order_confirmed
    
    # DPD/OMNIVA: жалоба ТОЛЬКО когда забран (status=PICKED_UP и заказ не подтвержден)
    can_open_issue_delivery = effective_status == OrderStatus.PICKED_UP.value and not order_confirmed
    
    # Выбираем правильное значение в зависимости от способа доставки
    if is_pickup:
        can_open_issue = can_open_issue_pickup
    elif is_delivery:
        can_open_issue = can_open_issue_delivery
    else:
        can_open_issue = False
    
    # Отзыв: ТОЛЬКО если заказ подтвержден И еще нет отзыва
    # (order.review_rating = None гарантирует один отзыв)
    can_leave_review = order_confirmed and order.review_rating is None
    
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
            "completed_at": order.completed_at,
            "order_confirmed_at": order.order_confirmed_at,  # ✅ ДОБАВЛЕНО: Критично для frontend!
            "review_rating": order.review_rating,            # ✅ ДОБАВЛЕНО: Для проверки один раз
            # SECURITY: Продавец информация о встречи
            "seller_meeting_address": seller_meeting_address,
            "seller_contact_preference": seller_contact_preference,
            "seller_phone": seller_phone,
            "seller_email": seller_email
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
            "can_leave_review": can_leave_review,      # ✅ ДИНАМИЧЕСКОЕ: зависит от статуса
            "can_open_issue": can_open_issue           # ✅ ДИНАМИЧЕСКОЕ: зависит от статуса и метода
        }
    }


@order_router.post("/shipments/{tracking_number}/reviews")
async def leave_tracking_review(
    tracking_number: str,
    review_data: OrderPageReviewCreate,
    db: Session = Depends(get_session)
):
    """Оставить единый отзыв по tracking_number.
    
    Требования:
    - Заказ должен быть в статусе CONFIRMED
    - Отзыв может быть оставлен только один раз (review_rating must be NULL)
    """
    order = db.exec(
        select(Order).where(Order.tracking_number == tracking_number)
    ).first()
    if not order:
        raise HTTPException(status_code=404, detail="Заказ не найден")
    
    # === БИЗНЕС-ПРАВИЛО: Отзыв только при статусе CONFIRMED ===
    if order.status != OrderStatus.CONFIRMED.value:
        raise HTTPException(
            status_code=400, 
            detail=f"Отзыв можно оставлять только когда статус 'confirmed'. Текущий статус: {order.status}"
        )
    
    # === БИЗНЕС-ПРАВИЛО: Один отзыв на мандат ===
    if order.review_rating is not None:
        raise HTTPException(
            status_code=400,
            detail="Вы уже оставили отзыв для этого заказа. Один отзыв на сделку."
        )

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


@order_router.post("/shipments/{tracking_number}/issues")
async def create_tracking_issue(
    tracking_number: str,
    request: Request,
    issue_data: OrderIssueCreate,
    db: Session = Depends(get_session)
):
    """Создать жалобу/заявку на возврат по tracking_number.
    
    === БИЗНЕС-ПРАВИЛА ПО СПОСОБУ ДОСТАВКИ ===
    
    1. PICKUP (личная встреча):
       - Жалобу можно подать ДО подтверждения (status=PAID и order_confirmed_at is NULL)
       - После подтверждения жалобы поддаваться не могут
    
    2. DPD/OMNIVA (курьерская доставка):
       - Жалобу можно подать ТОЛЬКО когда заказ уже забран (status=PICKED_UP)
       - После подтверждения жалобы поддаваться не могут
    """
    order = db.exec(
        select(Order).where(Order.tracking_number == tracking_number)
    ).first()
    if not order:
        raise HTTPException(status_code=404, detail="Заказ не найден")
    
    # === БИЗНЕС-ПРАВИЛО: Жалобы по способу доставки ===
    is_pickup = order.delivery_method == "pickup"
    is_delivery = order.delivery_method in ["dpd", "omniva"]
    
    if is_pickup:
        # PICKUP: жалоба ДО подтверждения (status=PAID)
        if order.status != OrderStatus.PAID.value:
            raise HTTPException(
                status_code=400,
                detail=f"Для личной встречи жалобу можно подать только до подтверждения заказа (статус должен быть 'paid'). Текущий статус: {order.status}"
            )
        if order.order_confirmed_at is not None:
            raise HTTPException(
                status_code=400,
                detail="Вы уже подтвердили состояние заказа. Жалобы больше не поддаются."
            )
    
    elif is_delivery:
        # DPD/OMNIVA: жалоба ТОЛЬКО когда уже забран (status=PICKED_UP)
        if order.status != OrderStatus.PICKED_UP.value:
            raise HTTPException(
                status_code=400,
                detail=f"Жалобу можно подать только когда заказ забран с паромата (статус 'picked_up'). Текущий статус: {order.status}"
            )
        if order.order_confirmed_at is not None:
            raise HTTPException(
                status_code=400,
                detail="Вы уже подтвердили состояние заказа. Жалобы больше не поддаются."
            )
    
    else:
        raise HTTPException(
            status_code=400,
            detail="Жалобы поддерживаются только для личной встречи (pickup) и курьерских доставок (DPD/Omniva)"
        )

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

    # Синхронизируем с общей лентой жалоб для админ-панели (/api/v1/reports)
    try:
        reporter_id = None
        access_token = request.cookies.get("access_token")
        if access_token:
            try:
                reporter_id = jwt.decode(access_token, Configs.secret_key, algorithms=[Configs.token_algoritm]).get("user_id")
            except Exception:
                reporter_id = None

        reporter_ip = request.headers.get("X-Forwarded-For", "").split(",")[0].strip() if request.headers.get("X-Forwarded-For") else (request.client.host if request.client else "unknown")
        short_reason = (issue_data.reason or "").strip()[:50]
        details_prefix = f"[tracking:{tracking_number}] [type:{issue_data.issue_type.value}]"

        report = PostReport(
            post_id=order.post_id,
            reporter_id=reporter_id,
            reporter_ip=reporter_ip,
            reason=short_reason or "Issue from order page",
            details=f"{details_prefix}\n{issue_data.description}",
            status="pending",
        )
        db.add(report)
        db.commit()
    except Exception as sync_error:
        logger.warning(
            f"Order issue->PostReport sync failed | tracking={tracking_number} | order_id={order.id} | "
            f"error_type={safe_exception_name(sync_error)}"
        )

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


@order_router.post("/{order_id}/shipments")
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
    
    # Обновляем статус на IN_TRANSIT (в пути для доставки или готов для pickup)
    order.status = OrderStatus.IN_TRANSIT.value
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
            logger.error(
                f"Delivery status update error | order_id={order.id} | error_type={safe_exception_name(e)}"
            )
            # Продолжаем выполнение
    else:
        logger.info(f"Delivery update skipped | order_id={order.id} | method={order.delivery_method}")
    
    return {
        "success": True,
        "message": "Товар отмечен как отправленный. Покупатель получит уведомление.",
        "order_id": order.id,
        "shipped_at": order.shipped_at
    }


@order_router.post("/{order_id}/reviews", response_model=dict)
async def leave_review(
    order_id: int,
    review_data: dict,
    access_token: str = Cookie(None),
    db: Session = Depends(get_session)
):
    """
    Покупатель оставляет отзыв на уже доставленный/завершенный заказ
    
    Заказ должен быть в статусе CONFIRMED
    Не меняет статус заказа - только сохраняет отзыв
    """
    if not access_token:
        raise HTTPException(status_code=401, detail="Not authenticated")
    user = get_current_user(access_token)
    
    rating = review_data.get("rating")
    review_text = review_data.get("review_text")
    
    if rating is None:
        raise HTTPException(status_code=400, detail="rating обязателен")
    
    if not (0 <= rating <= 5):
        raise HTTPException(status_code=400, detail="Оценка должна быть от 0 до 5")
    
    order = db.get(Order, order_id)
    if not order:
        raise HTTPException(status_code=404, detail="Заказ не найден")
    
    # Проверяем, что это покупатель
    if order.buyer_id != user["user_id"]:
        raise HTTPException(status_code=403, detail="Только покупатель может оставить отзыв")
    
    # Покупатель может оставить отзыв если заказ CONFIRMED
    if order.status != OrderStatus.CONFIRMED.value:
        raise HTTPException(status_code=400, detail="Товар ещё не доставлен или состояние не подтверждено")
    
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
        logger.warning(
            f"Seller rating update failed | order_id={order.id} | error_type={safe_exception_name(e)}"
        )
    
    return {
        "success": True,
        "message": "Спасибо за ваш отзыв!",
        "order_id": order.id,
        "rating": rating
    }


@order_router.get("/me/orders")
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


@order_router.get("/me/sales")
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


@order_router.get("")
async def get_admin_orders_today_stats(
    start_at: datetime = Query(..., description="Начало периода в ISO формате UTC"),
    end_at: datetime = Query(..., description="Конец периода в ISO формате UTC"),
    access_token: str = Cookie(None),
    db: Session = Depends(get_session)
):
    """Статистика заказов за период через start_at/end_at, только для admin/support."""
    user = get_current_user(access_token)
    if user.get("user_type", "regular") not in ["admin", "support"]:
        raise HTTPException(status_code=403, detail="Недостаточно прав")

    if end_at <= start_at:
        raise HTTPException(status_code=422, detail="end_at должен быть больше start_at")

    today_orders = db.exec(
        select(Order).where(
            Order.created_at >= start_at,
            Order.created_at < end_at,
        )
    ).all()

    return {
        "status": "success",
        "data": {
            "new_orders": len(today_orders),
            "start_at": start_at.isoformat(),
            "end_at": end_at.isoformat(),
        }
    }


@order_router.get("/{order_id}")
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


@order_router.post("/delivery-events/receipts")
async def delivery_received_webhook(
    request: dict,
    db: Session = Depends(get_session)
):
    """
    Webhook от delivery-service: уведомление о том, что доставка получена покупателем
    
    Автоматически:
    1. Обновляет статус заказа на PICKED_UP (получен с пакомата)
    2. Ждет, пока покупатель вручную подтвердит состояние (CONFIRMED)
    3. После подтверждения пользователь может оставить отзыв
    4. Отправляет уведомление покупателю с ссылкой на подтверждение и отзыв
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
    
    # Идемпотентность: если уже подтвержден, просто возвращаем
    if order.status == OrderStatus.CONFIRMED.value:
        logger.info(
            f"Delivery received webhook | order already confirmed | order_id={order_id} | tracking={tracking_number}"
        )
        return {
            "success": True,
            "message": "Заказ уже был подтвержден покупателем",
            "order_id": order.id,
            "status": order.status,
        }

    # Проверяем текущий статус - должен быть в процессе доставки или готов к получению
    if order.status not in [
        OrderStatus.PAID.value,
        OrderStatus.IN_TRANSIT.value,
        OrderStatus.READY_FOR_PICKUP.value,
    ]:
        logger.warning(
            f"Delivery received webhook | unexpected status | order_id={order_id} | tracking={tracking_number} | current_status={order.status}"
        )
        return {
            "success": False,
            "message": f"Заказ имеет статус {order.status}, ожидался paid/in_transit/ready_for_pickup"
        }
    
    # Обновляем статус на PICKED_UP (автоматическое обновление при получении с пакомата)
    order.status = OrderStatus.PICKED_UP.value
    order.delivered_at = datetime.utcnow()
    
    db.add(order)
    db.commit()
    db.refresh(order)
    
    logger.info(f"Order picked up | order_id={order_id} | status={order.status}")
    
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
        logger.warning(
            f"Seller stats update failed | order_id={order_id} | error_type={safe_exception_name(e)}"
        )
    
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
            logger.error(
                f"Chat hide error | post_id={order.post_id} | error_type={safe_exception_name(e)}"
            )
    
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
        logger.warning(
            f"Review request SMS failed | order_id={order.id} | error_type={safe_exception_name(e)}"
        )
    
    return {
        "success": True,
        "message": "Заказ автоматически завершён (получен покупателем)",
        "order_id": order.id,
        "status": order.status,
        "delivered_at": order.delivered_at,
        "completed_at": order.completed_at
    }


# === ФАЗА 4: ENDPOINT ДЛЯ ПОДТВЕРЖДЕНИЯ СОСТОЯНИЯ (PICKUP) ===
@order_router.post("/shipments/{tracking_number}/confirm-condition")
async def confirm_order_condition(
    tracking_number: str,
    request: Request,
    access_token: str = Cookie(None),
    db: Session = Depends(get_session)
):
    """
    Подтверждение покупателем состояния товара при личной встрече (pickup).
    После подтверждения заказ не может быть возвращен по причине несоответствия состояния.
    
    ✓ Работает для авторизованных пользователей (через JWT токен)
    ✓ Работает для анонимных покупателей (только по tracking_number)
    
    Для анонимного: просто POST на /shipments/{tracking_number}/confirm-condition
    Для авторизованного: JWT должен принадлежать покупателю заказа
    """
    buyer_id = None
    
    # Пытаемся получить buyer_id из JWT (если авторизован)
    if access_token:
        try:
            payload = jwt.decode(access_token, Configs.secret_key, algorithms=[Configs.token_algoritm])
            buyer_id = payload.get("user_id")
        except Exception:
            # Токен невалидный, но это не критично для анонимного заказа
            pass
    
    try:
        # Находим заказ по tracking_number
        stmt = select(Order).where(Order.tracking_number == tracking_number)
        order = db.exec(stmt).first()
        
        if not order:
            raise HTTPException(status_code=404, detail="Заказ не найден")
        
        # Проверяем что это либо личная встреча (pickup), либо доставка
        is_pickup = order.delivery_method == "pickup"
        is_delivery = order.delivery_method in ["dpd", "omniva"]
        
        if not (is_pickup or is_delivery):
            raise HTTPException(
                status_code=400,
                detail="Подтверждение состояния доступно только для личных встреч (pickup) и доставок (courier)"
            )
        
        # Если пользователь авторизован - проверяем что это его заказ
        if buyer_id:
            if order.buyer_id != buyer_id:
                raise HTTPException(status_code=403, detail="Только покупатель может подтвердить состояние")
        # Если не авторизован - проверяем что заказ анонимный
        elif order.buyer_id is not None:
            raise HTTPException(
                status_code=403, 
                detail="Авторизованные покупатели должны подтвердить заказ в аккаунте"
            )
        
        # === КОНСИСТЕНТНОСТЬ: Синхронизируем статусы перед проверкой ===
        # ВАЖНО: Синхронизируем ТОЛЬКО если order еще не подтвержден!
        # Не меняем if order.status == CONFIRMED (user уже подтвердил)
        if is_delivery:
            # Получаем актуальный статус из delivery service
            try:
                delivery_data = await get_delivery_by_tracking(tracking_number)
                if delivery_data:
                    delivery_status = delivery_data.get("status")
                    # ВАЖНО: Не перезаписываем if order уже был подтвержден (status == CONFIRMED)
                    if delivery_status == "picked_up" and order.status not in [OrderStatus.PICKED_UP.value, OrderStatus.CONFIRMED.value]:
                        logger.info(
                            f"Auto-syncing order status from delivery | tracking={tracking_number} | from {order.status} to picked_up"
                        )
                        order.status = OrderStatus.PICKED_UP.value
                        order.delivered_at = datetime.utcnow()
                        db.add(order)
                        db.commit()
                        db.refresh(order)
            except Exception as e:
                logger.warning(f"Failed to sync status from delivery | tracking={tracking_number} | error={str(e)}")
                # Продолжаем с текущим статусом order
        
        # === БИЗНЕС-ПРАВИЛА: Подтверждение по способу доставки ===
        # 
        # PICKUP (личная встреча):
        #   - Может подтвердить при статусе PAID (товар передан/получен)
        #   - После подтверждения больше жалобы не поддаются
        #
        # DPD/OMNIVA (курьерская доставка):
        #   - Может подтвердить при статусе PICKED_UP (забран с паромата)
        #   - После подтверждения может оставить отзыв
        
        # Идемпотентность: если уже подтвержден, просто возвращаем успех
        if order.status == OrderStatus.CONFIRMED.value:
            logger.info(f"Order already confirmed | order_id={order.id} | tracking={tracking_number}")
            return {
                "status": "success",
                "message": "Заказ уже был подтвержден",
                "order_id": order.id,
                "confirmed_at": order.order_confirmed_at
            }
        
        # Проверяем статус в зависимости от способа доставки
        if is_pickup:
            # PICKUP: может подтвердить при PAID
            if order.status != OrderStatus.PAID.value:
                raise HTTPException(
                    status_code=400,
                    detail=f"Для личной встречи заказ можно подтвердить только когда статус 'paid'. Текущий статус: {order.status}"
                )
        else:  # is_delivery
            # DPD/OMNIVA: может подтвердить только при PICKED_UP
            if order.status != OrderStatus.PICKED_UP.value:
                raise HTTPException(
                    status_code=400,
                    detail=f"Заказ можно подтвердить только когда он забран с паромата (статус 'picked_up'). Текущий статус: {order.status}"
                )
        
        # Обновляем заказ
        order.order_confirmed_at = datetime.utcnow()
        order.confirmed_by_buyer = True
        order.status = "confirmed"  # Новый статус - подтверждено
        
        db.add(order)
        db.commit()
        db.refresh(order)
        
        logger.info(f"Order condition confirmed | order_id={order.id} | tracking={tracking_number} | buyer={'auth:' + str(buyer_id) if buyer_id else 'anonymous'}")
        
        return {
            "status": "success",
            "message": "Состояние подтверждено",
            "order_id": order.id,
            "confirmed_at": order.order_confirmed_at
        }
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error confirming condition | tracking={tracking_number} | error={str(e)}")
        raise HTTPException(status_code=500, detail="Ошибка при подтверждении состояния")


# === ФАЗА 5: ENDPOINT ДЛЯ ПРЕДЛОЖЕНИЯ СКИДКИ (ОПЦИОНАЛЬНО) ===
@order_router.post("/{order_id}/offer-discount")
async def offer_discount(
    order_id: int,
    discount_amount: float,
    request: Request,
    access_token: str = Cookie(None),
    db: Session = Depends(get_session)
):
    """
    Продавец предлагает скидку покупателю в случае обнаружения дефектов.
    Требует JWT токен продавца в cookies.
    """
    if not access_token:
        raise HTTPException(status_code=401, detail="Требуется авторизация")
    
    if discount_amount <= 0:
        raise HTTPException(status_code=400, detail="Скидка должна быть больше 0")
    
    try:
        payload = jwt.decode(access_token, Configs.secret_key, algorithms=[Configs.token_algoritm])
        seller_id = payload.get("user_id")
        if not seller_id:
            raise HTTPException(status_code=401, detail="Некорректный токен")
    except Exception as e:
        raise HTTPException(status_code=401, detail=f"Недействительный токен: {str(e)}")
    
    try:
        stmt = select(Order).where(Order.id == order_id)
        order = db.exec(stmt).first()
        
        if not order:
            raise HTTPException(status_code=404, detail="Заказ не найден")
        
        # Проверяем что это продавец
        if order.seller_id != seller_id:
            raise HTTPException(status_code=403, detail="Только продавец может предложить скидку")
        
        # Проверяем что заказ в нужном статусе
        if order.status not in ["paid", "confirmed"]:
            raise HTTPException(status_code=400, detail="Скидка может быть предложена только после оплаты")
        
        # Проверяем что скидка не превышает цену
        if discount_amount > order.price:
            raise HTTPException(status_code=400, detail="Скидка не может превышать цену товара")
        
        # Предлагаем скидку
        order.discount_offered = discount_amount
        order.discount_status = "pending"
        
        db.add(order)
        db.commit()
        db.refresh(order)
        
        logger.info(f"Discount offered | order_id={order_id} | amount={discount_amount}")
        
        return {
            "status": "success",
            "message": "Скидка предложена",
            "order_id": order.id,
            "discount_offered": order.discount_offered
        }
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error offering discount | order_id={order_id} | error={str(e)}")
        raise HTTPException(status_code=500, detail="Ошибка при предложении скидки")


# === ФАЗА 5: ENDPOINT ДЛЯ ОТВЕТА НА СКИДКУ ===
@order_router.patch("/{order_id}/discount-response")
async def respond_to_discount(
    order_id: int,
    accepted: bool,
    request: Request,
    access_token: str = Cookie(None),
    db: Session = Depends(get_session)
):
    """
    Покупатель принимает или отклоняет предложенную скидку.
    Требует JWT токен покупателя в cookies.
    """
    if not access_token:
        raise HTTPException(status_code=401, detail="Требуется авторизация")
    
    try:
        payload = jwt.decode(access_token, Configs.secret_key, algorithms=[Configs.token_algoritm])
        buyer_id = payload.get("user_id")
        if not buyer_id:
            raise HTTPException(status_code=401, detail="Некорректный токен")
    except Exception as e:
        raise HTTPException(status_code=401, detail=f"Недействительный токен: {str(e)}")
    
    try:
        stmt = select(Order).where(Order.id == order_id)
        order = db.exec(stmt).first()
        
        if not order:
            raise HTTPException(status_code=404, detail="Заказ не найден")
        
        # Проверяем что это покупатель
        if order.buyer_id != buyer_id:
            raise HTTPException(status_code=403, detail="Только покупатель может ответить на скидку")
        
        # Проверяем что скидка была предложена
        if order.discount_status != "pending":
            raise HTTPException(status_code=400, detail="Нет активного предложения скидки")
        
        # Обновляем статус скидки
        order.discount_status = "accepted" if accepted else "rejected"
        
        db.add(order)
        db.commit()
        db.refresh(order)
        
        logger.info(
            f"Discount response | order_id={order_id} | "
            f"accepted={accepted} | discount_status={order.discount_status}"
        )
        
        return {
            "status": "success",
            "message": f"Скидка {'принята' if accepted else 'отклонена'}",
            "order_id": order.id,
            "discount_status": order.discount_status
        }
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error responding to discount | order_id={order_id} | error={str(e)}")
        raise HTTPException(status_code=500, detail="Ошибка при ответе на скидку")

