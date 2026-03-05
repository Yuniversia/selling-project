# order_router.py - Роутер для системы покупки и доставки

from fastapi import APIRouter, Depends, HTTPException, Request, Cookie
from sqlmodel import Session, select
from typing import Optional
from jose import jwt
import secrets
import string
from datetime import datetime
import httpx

from database import get_session
from models import (
    Order, OrderCreate, OrderResponse, OrderConfirmation,
    Iphone, DeliveryMethod, OrderStatus, User
)
from configs import Configs

order_router = APIRouter(prefix="/api/v1/orders", tags=["Orders"])


async def send_notification_async(endpoint: str, data: dict):
    """Асинхронная отправка уведомления через notification service"""
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            # Используем универсальный endpoint /send
            response = await client.post(
                f"{Configs.NOTIFICATION_SERVICE_URL}/api/v1/notifications/send",
                json={
                    "notification_type": endpoint.replace("-", "_"),  # order-created -> order_created
                    "channel": "both",
                    "order_data": data
                }
            )
            if response.status_code == 200:
                print(f"✅ Notification sent: {endpoint}")
                return response.json()
            else:
                print(f"⚠️ Notification failed: {response.status_code} - {response.text}")
                return None
    except Exception as e:
        print(f"❌ Error sending notification: {e}")
        return None


def get_current_user(access_token: str) -> dict:
    """Извлечение пользователя из JWT токена"""
    if not access_token:
        raise HTTPException(status_code=401, detail="Not authenticated")
    
    # БЕЗОПАСНОСТЬ: НЕ логируем токены и секретные ключи
    # print(f"[AUTH] Attempting to decode token: {access_token[:50]}...")
    # print(f"[AUTH] Using secret_key: {Configs.secret_key[:10]}... algorithm: {Configs.token_algoritm}")
    
    try:
        payload = jwt.decode(access_token, Configs.secret_key, algorithms=[Configs.token_algoritm])
        # НЕ логируем payload - может содержать чувствительную информацию
        # print(f"[AUTH] ✅ Token decoded successfully! Payload: {payload}")
        user_id = payload.get("user_id")
        if not user_id:
            print(f"[AUTH] ❌ No user_id in payload!")
            raise HTTPException(status_code=401, detail="Invalid token")
        return {
            "user_id": user_id,
            "username": payload.get("username"),
            "user_type": payload.get("user_type", "regular")
        }
    except Exception as e:
        # Ловим все исключения JWT (ExpiredSignatureError, InvalidTokenError, DecodeError и т.д.)
        print(f"[AUTH] ❌ Token validation failed: {type(e).__name__}")
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
    post = db.get(Iphone, order_data.post_id)
    if not post:
        raise HTTPException(status_code=404, detail="Товар не найден")
    
    if not post.active:
        raise HTTPException(status_code=400, detail="Товар уже не активен")
    
    if post.price is None:
        raise HTTPException(status_code=400, detail="Цена товара не указана")
    
    # Проверяем, что покупатель не продавец (только для авторизованных)
    if buyer_id and post.author_id == buyer_id:
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
        post.author_id,
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
            seller_id=post.author_id,
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
        print(f"[CREATE ORDER] ✅ Order #{order.id} created successfully")
        print(f"  buyer_id: {order.buyer_id} (None = anonymous)")
        print(f"  seller_id: {order.seller_id}")
        print(f"  post_id: {order.post_id}")
        print(f"  price: {order.price}")
        print(f"  status: {order.status}")
        
        # Отправляем уведомления продавцу и покупателю
        try:
            # Получаем информацию о продавце
            seller = db.get(User, post.author_id)
            
            notification_data = {
                "order_id": order.id,
                "seller_name": seller.name or seller.username if seller else "Продавец",
                "seller_email": seller.email if seller else None,
                "seller_phone": seller.phone if seller else None,
                "buyer_name": f"{order.buyer_first_name} {order.buyer_last_name}",
                "buyer_email": order.buyer_email,
                "buyer_phone": order.buyer_phone,
                "product_name": post.model or "iPhone",
                "product_model": f"{post.memory}GB {post.color}" if post.memory and post.color else None,
                "order_price": order.price,
                "delivery_method": order.delivery_method,
                "tracking_url": f"{Configs.FRONTEND_URL}/orders/{order.id}"
            }
            
            # Асинхронно отправляем уведомления
            await send_notification_async("order-created", notification_data)
            
        except Exception as e:
            print(f"[CREATE ORDER] ⚠️ Failed to send notifications: {e}")
            # Продолжаем выполнение даже если уведомления не отправились
            
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        print(f"[ERROR] Ошибка создания заказа: {e}")
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
    4. Отправляем email с кодом (пока имитация)
    """
    # Пытаемся получить текущего пользователя (может быть None для анонимных)
    user_id = None
    if access_token:
        try:
            user = get_current_user(access_token)
            user_id = user["user_id"]
        except HTTPException:
            user_id = None
    
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
    post = db.get(Iphone, order.post_id)
    if post:
        post.active = False
    
    db.commit()
    db.refresh(order)
    
    # Создаем доставку через delivery service (если не pickup)
    if order.delivery_method in [DeliveryMethod.DPD.value, DeliveryMethod.OMNIVA.value]:
        print(f"[PAY] 🚚 Creating delivery for order {order.id}, method: {order.delivery_method}")
        try:
            # Получаем информацию о продавце для отправки
            seller = db.get(User, order.seller_id)
            
            delivery_data = {
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
                "delivery_country": order.delivery_country or "Latvia"
            }
            
            print(f"[PAY] 📦 Sending request to: {Configs.DELIVERY_SERVICE_URL}/api/v1/delivery/create")
            
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.post(
                    f"{Configs.DELIVERY_SERVICE_URL}/api/v1/delivery/create",
                    json=delivery_data
                )
                
                if response.status_code == 201:
                    delivery_info = response.json()
                    order.tracking_number = delivery_info.get("tracking_number")
                    db.commit()
                    print(f"✅ Delivery created for order {order.id}: {order.tracking_number}")
                else:
                    print(f"⚠️ Failed to create delivery: {response.status_code} - {response.text}")
                    
        except Exception as e:
            print(f"❌ Error creating delivery: {e}")
            import traceback
            traceback.print_exc()
            # Продолжаем выполнение даже если доставка не создалась
    else:
        print(f"[PAY] ⏭️ Skipping delivery creation (method: {order.delivery_method})")
    
    # Отправляем уведомление об оплате
    try:
        seller = db.get(User, order.seller_id)
        post = db.get(Iphone, order.post_id)
        
        notification_data = {
            "order_id": order.id,
            "seller_name": seller.name or seller.username if seller else "Продавец",
            "seller_email": seller.email if seller else None,
            "seller_phone": seller.phone if seller else None,
            "buyer_name": f"{order.buyer_first_name} {order.buyer_last_name}",
            "buyer_email": order.buyer_email,
            "buyer_phone": order.buyer_phone,
            "product_name": post.model or "iPhone" if post else "iPhone",
            "product_model": f"{post.memory}GB {post.color}" if post and post.memory and post.color else None,
            "order_price": order.price,
            "delivery_method": order.delivery_method,
            "tracking_url": f"{Configs.FRONTEND_URL}/orders/{order.id}"
        }
        
        # Отправляем асинхронно
        await send_notification_async("order-paid", notification_data)
    except Exception as e:
        print(f"[PAY] ⚠️ Failed to send payment notification: {e}")
    
    return {
        "success": True,
        "order_id": order.id,
        "status": order.status,
        "message": "Товар успешно куплен! Продавец получил уведомление и отправит товар в ближайшее время."
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
    
    print(f"[SHIP] Order #{order.id} marked as shipped by seller {user['user_id']}")
    
    # Обновляем статус доставки в delivery service (если не pickup)
    if order.delivery_method in [DeliveryMethod.DPD.value, DeliveryMethod.OMNIVA.value]:
        print(f"[SHIP] 🚚 Updating delivery status for order {order.id}")
        try:
            # Получаем доставку по order_id
            async with httpx.AsyncClient(timeout=10.0) as client:
                print(f"[SHIP] 📦 Getting delivery: {Configs.DELIVERY_SERVICE_URL}/api/v1/delivery/order/{order.id}")
                
                # Получаем delivery_id
                delivery_response = await client.get(
                    f"{Configs.DELIVERY_SERVICE_URL}/api/v1/delivery/order/{order.id}"
                )
                
                if delivery_response.status_code == 200:
                    delivery = delivery_response.json()
                    delivery_id = delivery.get("id")
                    
                    print(f"[SHIP] 📦 Updating delivery {delivery_id} status to in_transit")
                    
                    # Обновляем статус на "in_transit"
                    update_response = await client.patch(
                        f"{Configs.DELIVERY_SERVICE_URL}/api/v1/delivery/{delivery_id}/status",
                        json={"status": "in_transit", "notes": "Посылка отправлена продавцом"}
                    )
                    
                    if update_response.status_code == 200:
                        print(f"✅ Delivery status updated to in_transit for order {order.id}")
                    else:
                        print(f"⚠️ Failed to update delivery status: {update_response.status_code} - {update_response.text}")
                else:
                    print(f"⚠️ Delivery not found for order {order.id}: {delivery_response.status_code}")
                    
        except Exception as e:
            print(f"❌ Error updating delivery status: {e}")
            import traceback
            traceback.print_exc()
            # Продолжаем выполнение
    else:
        print(f"[SHIP] ⏭️ Skipping delivery update (method: {order.delivery_method})")
    
    # Уведомляем покупателя об отправке
    try:
        seller = db.get(User, order.seller_id)
        post = db.get(Iphone, order.post_id)
        
        notification_data = {
            "order_id": order.id,
            "seller_name": seller.name or seller.username if seller else "Продавец",
            "seller_email": seller.email if seller else None,
            "seller_phone": seller.phone if seller else None,
            "buyer_name": f"{order.buyer_first_name} {order.buyer_last_name}",
            "buyer_email": order.buyer_email,
            "product_name": post.model or "iPhone" if post else "iPhone",
            "product_model": f"{post.memory}GB {post.color}" if post and post.memory and post.color else None,
            "order_price": order.price,
            "delivery_method": order.delivery_method,
            "tracking_url": f"{Configs.FRONTEND_URL}/orders/{order.id}",
            "review_url": f"{Configs.FRONTEND_URL}/orders/{order.id}/review"
        }
        
        # Отправляем асинхронно
        await send_notification_async("order-shipped", notification_data)
    except Exception as e:
        print(f"[SHIP] ⚠️ Failed to send shipping notification: {e}")
    
    return {
        "success": True,
        "message": "Товар отмечен как отправленный. Покупатель получит уведомление.",
        "order_id": order.id,
        "shipped_at": order.shipped_at
    }


@order_router.post("/confirm", response_model=dict)
async def confirm_receipt(
    confirmation: OrderConfirmation,
    access_token: str = Cookie(None),
    db: Session = Depends(get_session)
):
    """
    Покупатель подтверждает или отклоняет получение товара + оставляет отзыв
    
    После отправки товара продавцом, покупатель может:
    - Подтвердить получение (accepted=True) + оценка 0-5 + текст отзыва
    - Отклонить (accepted=False) + оценка 0-5 + причина
    
    При подтверждении: +1 к sells_count продавцу, обновляется рейтинг
    """
    if not access_token:
        raise HTTPException(status_code=401, detail="Not authenticated")
    user = get_current_user(access_token)
    
    order = db.get(Order, confirmation.order_id)
    if not order:
        raise HTTPException(status_code=404, detail="Заказ не найден")
    
    # Проверяем, что это покупатель
    if order.buyer_id != user["user_id"]:
        raise HTTPException(status_code=403, detail="Только покупатель может подтвердить получение")
    
    if order.status != OrderStatus.SHIPPED.value:
        raise HTTPException(status_code=400, detail="Товар ещё не отправлен")
    
    if order.confirmed_by_buyer or order.rejected_by_buyer:
        raise HTTPException(status_code=400, detail="Вы уже оставили отзыв на этот заказ")
    
    # Сохраняем отзыв
    order.review_rating = confirmation.rating
    order.review_text = confirmation.review_text
    order.completed_at = datetime.utcnow()
    
    if confirmation.accepted:
        # Покупатель подтверждает получение
        order.confirmed_by_buyer = True
        order.status = OrderStatus.COMPLETED.value
        
        print(f"[CONFIRM] ✅ Order #{order.id} confirmed by buyer {user['user_id']}")
        print(f"[CONFIRM] Post ID: {order.post_id}, Buyer ID: {user['user_id']}")
        
        # Скрываем чаты связанные с этим заказом через HTTP-запрос к chat-service
        try:
            import httpx
            
            buyer_id_for_chat = str(user["user_id"])
            chat_api_url = "http://chat-service:4000/api/chat/chats/hide-for-order"
            
            print(f"[CONFIRM] Calling chat-service API: {chat_api_url}")
            print(f"[CONFIRM] Params: post_id={order.post_id}, buyer_id={buyer_id_for_chat}")
            
            with httpx.Client(timeout=5.0) as client:
                response = client.post(
                    chat_api_url,
                    params={
                        "post_id": order.post_id,
                        "buyer_id": buyer_id_for_chat
                    }
                )
                
                if response.status_code == 200:
                    result = response.json()
                    print(f"[CONFIRM] ✅ Hidden {result.get('hidden_count', 0)} chat(s)")
                else:
                    print(f"[CONFIRM] ⚠️ Chat service returned status {response.status_code}: {response.text}")
        except Exception as e:
            import traceback
            print(f"[CONFIRM] ❌ Error hiding chats: {e}")
            print(traceback.format_exc())
            # Не прерываем выполнение если не удалось скрыть чаты
        
        # Обновляем статистику продавца
        seller_statement = select(User).where(User.id == order.seller_id)
        seller = db.exec(seller_statement).first()
        
        if seller:
            # +1 к продажам
            seller.sells_count += 1
            
            # Обновляем рейтинг (среднее арифметическое)
            # Находим все завершённые заказы продавца с отзывами
            completed_orders = db.exec(
                select(Order).where(
                    Order.seller_id == order.seller_id,
                    Order.review_rating.isnot(None)
                )
            ).all()
            
            if completed_orders:
                total_rating = sum(o.review_rating for o in completed_orders if o.review_rating is not None)
                seller.rating = round(total_rating / len(completed_orders), 2)
            
            print(f"[CONFIRM] Seller {seller.id} stats updated: sells={seller.sells_count}, rating={seller.rating}")
        
        message = "Спасибо за подтверждение! Продавец получил +1 к продажам."
    else:
        # Покупатель отклоняет
        order.rejected_by_buyer = True
        order.status = OrderStatus.CANCELLED.value
        message = "Заказ отклонён. Администрация рассмотрит вашу жалобу."
    
    db.commit()
    
    print(f"[CONFIRM] Order #{order.id} {'confirmed' if confirmation.accepted else 'rejected'} by buyer {user['user_id']}")
    print(f"  Rating: {confirmation.rating}/5, Review: {confirmation.review_text[:50] if confirmation.review_text else 'None'}")
    
    return {
        "success": True,
        "message": message,
        "order_id": order.id,
        "completed_at": order.completed_at,
        "accepted": confirmation.accepted
    }


@order_router.get("/my-orders")
async def get_my_orders(
    access_token: str = Cookie(None),
    db: Session = Depends(get_session)
):
    """Получить все заказы пользователя (как покупателя) - БЕЗ ЛИЧНЫХ ДАННЫХ"""
    print("[MY-ORDERS] Request received")
    if not access_token:
        print(f"[MY-ORDERS] No access_token - returning empty list")
        return {"orders": []}
    
    try:
        user = get_current_user(access_token)
        user_id = user["user_id"]
        print(f"[MY-ORDERS] Authenticated user: {user_id}")
    except HTTPException as e:
        print(f"[MY-ORDERS] Invalid token - returning empty list")
        return {"orders": []}
    
    statement = select(Order).where(Order.buyer_id == user_id)
    print(f"[MY-ORDERS] Executing query: SELECT * FROM order WHERE buyer_id = {user_id}")
    orders = db.exec(statement).all()
    
    print(f"[MY-ORDERS] User {user_id} has {len(orders)} orders")
    
    # Форматируем ответ БЕЗ личных данных (покупатель видит свои заказы)
    safe_orders = []
    for order in orders:
        safe_orders.append(OrderResponse(
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
        ))
    
    return {"orders": safe_orders}


@order_router.get("/my-sales")
async def get_my_sales(
    access_token: str = Cookie(None),
    db: Session = Depends(get_session)
):
    """Получить все продажи пользователя (как продавца) - ТОЛЬКО ИМЯ ПОКУПАТЕЛЯ"""
    print("[MY-SALES] Request received")
    print(f"[MY-SALES] access_token present: {bool(access_token)}")
    if access_token:
        print(f"[MY-SALES] Token preview: {access_token[:50]}...")
    
    if not access_token:
        print(f"[MY-SALES] No access_token - returning empty list")
        return {"sales": []}
    
    try:
        user = get_current_user(access_token)
        user_id = user["user_id"]
        print(f"[MY-SALES] Authenticated user: {user_id}")
    except HTTPException as e:
        print(f"[MY-SALES] Invalid token - returning empty list")
        return {"sales": []}
    
    statement = select(Order).where(Order.seller_id == user_id)
    print(f"[MY-SALES] Executing query: SELECT * FROM order WHERE seller_id = {user_id}")
    orders = db.exec(statement).all()
    
    print(f"[MY-SALES] User {user_id} has {len(orders)} sales")
    
    # Форматируем ответ: продавец видит ТОЛЬКО ИМЯ покупателя (БЕЗ email/phone/адреса)
    safe_sales = []
    for order in orders:
        safe_sales.append(OrderResponse(
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
        ))
    
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
    post = db.get(Iphone, order.post_id)
    
    return {
        "order": order,
        "post": post
    }
