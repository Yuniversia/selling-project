# delivery_service.py - Бизнес-логика delivery service

import secrets
import string
import httpx
import logging
from datetime import datetime, timedelta
from typing import Optional, Tuple
from sqlmodel import Session, select

from models import (
    Delivery, DeliveryStatusHistory, DeliveryStatus, 
    DeliveryProvider, DeliveryCreate, DeliveryStatusUpdate
)
from configs import configs

# Настройка логирования
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class DeliveryService:
    """Сервис для управления доставками"""
    
    def __init__(self, db: Session):
        self.db = db
    
    @staticmethod
    def generate_tracking_number(provider: str) -> str:
        """Генерация трекинг-номера"""
        prefix = {
            "omniva": "OM",
            "dpd": "DPD",
            "pickup": "PICK"
        }.get(provider.lower(), "DEL")
        
        random_part = ''.join(secrets.choice(string.ascii_uppercase + string.digits) for _ in range(10))
        return f"{prefix}{random_part}"
    
    @staticmethod
    def generate_pickup_code() -> str:
        """Генерация 6-значного кода для получения из пакомата"""
        return ''.join(secrets.choice(string.digits) for _ in range(6))
    
    def create_delivery(self, delivery_data: DeliveryCreate) -> Delivery:
        """Создание новой доставки"""
        
        # Проверяем, что доставка для этого заказа еще не создана
        existing = self.db.exec(
            select(Delivery).where(Delivery.order_id == delivery_data.order_id)
        ).first()
        
        if existing:
            raise ValueError(f"Delivery for order {delivery_data.order_id} already exists")
        
        # Генерируем трекинг-номер
        tracking_number = self.generate_tracking_number(delivery_data.provider.value)
        
        # Рассчитываем примерную дату доставки
        estimated_delivery = datetime.utcnow() + timedelta(hours=configs.TRANSIT_TIME_HOURS)
        
        # Создаем доставку
        delivery = Delivery(
            order_id=delivery_data.order_id,
            provider=delivery_data.provider.value,
            tracking_number=tracking_number,
            status=DeliveryStatus.CREATED.value,
            delivery_address=delivery_data.delivery_address,
            delivery_city=delivery_data.delivery_city,
            delivery_zip=delivery_data.delivery_zip,
            delivery_country=delivery_data.delivery_country,
            pickup_point_id=delivery_data.pickup_point_id,
            pickup_point_name=delivery_data.pickup_point_name,
            pickup_point_address=delivery_data.pickup_point_address,
            recipient_name=delivery_data.recipient_name,
            recipient_phone=delivery_data.recipient_phone,
            recipient_email=delivery_data.recipient_email,
            sender_name=delivery_data.sender_name,
            sender_phone=delivery_data.sender_phone,
            estimated_delivery_date=estimated_delivery,
            notes=delivery_data.notes
        )
        
        self.db.add(delivery)
        self.db.commit()
        self.db.refresh(delivery)
        
        # Добавляем в историю
        self._add_status_history(delivery.id, DeliveryStatus.CREATED.value, "Доставка создана")
        
        logger.info(f"✅ Delivery created: {delivery.tracking_number} for order {delivery.order_id}")
        
        return delivery
    
    def update_delivery_status(
        self, 
        delivery_id: int, 
        status_update: DeliveryStatusUpdate
    ) -> Delivery:
        """Обновление статуса доставки"""
        
        delivery = self.db.get(Delivery, delivery_id)
        if not delivery:
            raise ValueError(f"Delivery {delivery_id} not found")
        
        old_status = delivery.status
        new_status = status_update.status.value
        
        # Обновляем статус
        delivery.status = new_status
        
        # Обновляем временные метки
        now = datetime.utcnow()
        
        if new_status == DeliveryStatus.IN_TRANSIT.value:
            delivery.shipped_at = now
        
        elif new_status == DeliveryStatus.AT_PICKUP_POINT.value:
            delivery.arrived_at_pickup_point_at = now
            
            # Генерируем код получения
            if not delivery.pickup_code:
                delivery.pickup_code = self.generate_pickup_code()
            
            # Отправляем уведомление с кодом
            self._send_pickup_code_notification(delivery)
        
        elif new_status == DeliveryStatus.PICKED_UP.value:
            delivery.picked_up_at = now
            
            # Отправляем уведомление о получении + ссылку на отзыв
            self._send_picked_up_notification(delivery)
        
        self.db.add(delivery)
        self.db.commit()
        self.db.refresh(delivery)
        
        # Добавляем в историю
        self._add_status_history(
            delivery.id, 
            new_status, 
            status_update.notes or f"Статус изменен с {old_status} на {new_status}"
        )
        
        logger.info(f"✅ Delivery {delivery.tracking_number} status updated: {old_status} → {new_status}")
        
        return delivery
    
    def get_delivery_by_tracking(self, tracking_number: str) -> Optional[Delivery]:
        """Получение доставки по трекинг-номеру"""
        return self.db.exec(
            select(Delivery).where(Delivery.tracking_number == tracking_number)
        ).first()
    
    def get_delivery_by_order(self, order_id: int) -> Optional[Delivery]:
        """Получение доставки по ID заказа"""
        return self.db.exec(
            select(Delivery).where(Delivery.order_id == order_id)
        ).first()
    
    def get_delivery_history(self, delivery_id: int) -> list[DeliveryStatusHistory]:
        """Получение истории статусов доставки"""
        return self.db.exec(
            select(DeliveryStatusHistory)
            .where(DeliveryStatusHistory.delivery_id == delivery_id)
            .order_by(DeliveryStatusHistory.created_at)
        ).all()
    
    def _add_status_history(self, delivery_id: int, status: str, notes: Optional[str] = None):
        """Добавление записи в историю статусов"""
        history = DeliveryStatusHistory(
            delivery_id=delivery_id,
            status=status,
            notes=notes
        )
        self.db.add(history)
        self.db.commit()
    
    def _send_pickup_code_notification(self, delivery: Delivery):
        """Отправка уведомления с кодом получения"""
        if delivery.notification_sent_at_pickup_point:
            logger.info(f"⏭️ Pickup code notification already sent for {delivery.tracking_number}")
            return
        
        try:
            # Формируем сообщение
            message = (
                f"Ваш заказ прибыл в пункт выдачи! "
                f"Код получения: {delivery.pickup_code}. "
                f"Трекинг: {delivery.tracking_number}. "
                f"Пункт выдачи: {delivery.pickup_point_name or delivery.delivery_city}."
            )
            
            # Отправляем через notification service
            self._send_notification_async(
                notification_type="delivery_arrived",
                recipient_phone=delivery.recipient_phone,
                recipient_email=delivery.recipient_email,
                recipient_name=delivery.recipient_name,
                message=message,
                order_id=delivery.order_id
            )
            
            delivery.notification_sent_at_pickup_point = True
            self.db.add(delivery)
            self.db.commit()
            
            logger.info(f"✅ Pickup code notification sent for {delivery.tracking_number}")
            
        except Exception as e:
            logger.error(f"❌ Failed to send pickup code notification: {e}")
    
    def _send_picked_up_notification(self, delivery: Delivery):
        """Отправка уведомления о получении + ссылка на отзыв"""
        if delivery.notification_sent_picked_up:
            logger.info(f"⏭️ Picked up notification already sent for {delivery.tracking_number}")
            return
        
        try:
            # Формируем ссылку на отзыв
            review_link = f"{configs.FRONTEND_URL}/orders/{delivery.order_id}/review"
            
            # Формируем сообщение
            message = (
                f"Посылка получена! "
                f"Спасибо за покупку. "
                f"Оставьте отзыв: {review_link}"
            )
            
            # Отправляем через notification service
            self._send_notification_async(
                notification_type="delivery_picked_up",
                recipient_phone=delivery.recipient_phone,
                recipient_email=delivery.recipient_email,
                recipient_name=delivery.recipient_name,
                message=message,
                order_id=delivery.order_id
            )
            
            delivery.notification_sent_picked_up = True
            self.db.add(delivery)
            self.db.commit()
            
            logger.info(f"✅ Picked up notification sent for {delivery.tracking_number}")
            
        except Exception as e:
            logger.error(f"❌ Failed to send picked up notification: {e}")
    
    def _send_notification_async(
        self,
        notification_type: str,
        recipient_phone: str,
        recipient_email: str,
        recipient_name: str,
        message: str,
        order_id: int
    ):
        """Асинхронная отправка уведомления в notification service"""
        try:
            # Формируем данные для notification service
            notification_data = {
                "notification_type": "order_delivered",  # Используем существующий тип
                "channel": "sms",  # Отправляем только SMS
                "order_data": {
                    "order_id": order_id,
                    "seller_name": "Продавец",
                    "buyer_name": recipient_name,
                    "buyer_email": recipient_email,
                    "buyer_phone": recipient_phone,
                    "product_name": "iPhone",
                    "order_price": 0,
                    "delivery_method": "delivery",
                    "tracking_url": f"{configs.FRONTEND_URL}/orders/{order_id}"
                }
            }
            
            # Отправляем запрос
            with httpx.Client(timeout=5.0) as client:
                response = client.post(
                    f"{configs.NOTIFICATION_SERVICE_URL}/api/v1/notifications/send",
                    json=notification_data
                )
                
                if response.status_code == 200:
                    logger.info(f"✅ Notification sent to notification service")
                else:
                    logger.warning(f"⚠️ Notification failed: {response.status_code}")
                    
        except Exception as e:
            logger.error(f"❌ Failed to send notification: {e}")
    
    def simulate_delivery_process(self, delivery_id: int):
        """
        Имитация процесса доставки для тестирования
        (в продакшене будет заменено на реальное API DPD/Omniva)
        """
        delivery = self.db.get(Delivery, delivery_id)
        if not delivery:
            raise ValueError(f"Delivery {delivery_id} not found")
        
        # Переводим в статус "В пути"
        if delivery.status == DeliveryStatus.CREATED.value:
            self.update_delivery_status(
                delivery_id,
                DeliveryStatusUpdate(
                    status=DeliveryStatus.IN_TRANSIT,
                    notes="Посылка передана курьеру"
                )
            )
        
        logger.info(f"✅ Delivery simulation started for {delivery.tracking_number}")
        return delivery
