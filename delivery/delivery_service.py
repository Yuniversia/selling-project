# delivery_service.py - Бизнес-логика delivery service (УЛУЧШЕННАЯ ВЕРСИЯ)

import secrets
import string
import httpx
import logging
from datetime import datetime, timedelta
from typing import Optional, Dict, Any
from sqlmodel import Session, select

from models import (
    Delivery, DeliveryStatusHistory, DeliveryStatus, 
    DeliveryProvider, DeliveryCreate, DeliveryStatusUpdate,
    PickupPoint
)
from configs import configs
from providers.factory import DeliveryProviderFactory


logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class DeliveryService:
    """
    Сервис для управления доставками с универсальной интеграцией DPD.
    
    Key features:
    1. Сохраняет provider_tracking_number (DPD parcelNumber) в БД
    2. Автоматически подписывается на webhook от DPD
    3. Может синхронизировать статус по demand
    4. Уведомляет внешние сервисы об обновлениях
    """
    
    def __init__(self, db: Session):
        self.db = db
        self.provider_factory = DeliveryProviderFactory()
        self.dpd_client = self.provider_factory.get("dpd")

    @staticmethod
    def _normalize_provider(provider: str) -> str:
        return (provider or "").strip().lower()

    def get_pickup_points(
        self,
        *,
        provider: Optional[str] = None,
        country_code: Optional[str] = None,
        city: Optional[str] = None,
        limit: int = 200
    ) -> list[PickupPoint]:
        """Получить список пунктов выдачи с фильтрацией"""
        query = select(PickupPoint).where(PickupPoint.is_active == True)

        if provider:
            query = query.where(PickupPoint.provider == self._normalize_provider(provider))
        if country_code:
            query = query.where(PickupPoint.country_code == country_code.strip().upper())
        if city:
            query = query.where(PickupPoint.city == city.strip())

        query = query.order_by(PickupPoint.city, PickupPoint.name).limit(limit)
        return self.db.exec(query).all()

    def resolve_pickup_point(self, *, provider: str, system_point_id: str) -> Optional[PickupPoint]:
        """Проверить существование пункта выдачи"""
        return self.db.exec(
            select(PickupPoint)
            .where(PickupPoint.provider == self._normalize_provider(provider))
            .where(PickupPoint.system_point_id == system_point_id)
            .where(PickupPoint.is_active == True)
        ).first()

    def _dispatch_provider_integration(self, delivery_data: DeliveryCreate) -> Optional[Dict[str, Any]]:
        """
        Интеграция с провайдером доставки.
        
        Returns:
            {
                "provider_tracking_number": "12345678901234",  # DPD parcelNumber
                "pin_code": "123456",
                "shipment_id": "uuid",
                "status": "created"
            }
        """
        client = self.provider_factory.get(delivery_data.provider.value)
        if not client:
            return None
        
        payload_preview = {
            "order_id": delivery_data.order_id,
            "provider": delivery_data.provider.value,
            "pickup_point_id": delivery_data.pickup_point_id,
            "pickup_point_name": delivery_data.pickup_point_name,
            "delivery_country": delivery_data.delivery_country,
            "delivery_city": delivery_data.delivery_city,
            "delivery_zip": delivery_data.delivery_zip,
            "has_sender_email": bool(delivery_data.sender_email),
            "has_sender_address": bool(delivery_data.sender_address),
            "weight": delivery_data.weight,
        }
        
        logger.info(
            "Provider integration start | provider=%s | payload=%s",
            delivery_data.provider.value,
            payload_preview,
        )
        
        try:
            result = client.create_shipment(delivery_data)
            
            # Результат должен быть dict с provider_tracking_number
            if isinstance(result, dict):
                return result
            else:
                # Обратная совместимость: конвертируем string в dict
                return {"provider_response": result}
        
        except Exception as exc:
            logger.error(
                "Provider integration failed | provider=%s | error=%s",
                delivery_data.provider.value,
                str(exc),
            )
            raise ValueError(
                f"Provider integration failed for {delivery_data.provider.value}: {str(exc)}"
            ) from exc
    
    @staticmethod
    def generate_tracking_number(provider: str) -> str:
        """Генерация внутреннего трекинг-номера (для фронтенда)"""
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
        """
        Создание новой доставки с интеграцией в провайдера.
        
        Процесс:
        1. Проверяем что доставка еще не существует
        2. Разрешаем пункт выдачи если нужен
        3. Интегрируемся с провайдером (DPD/Omniva) для получения parcelNumber
        4. Сохраняем provider_tracking_number в БД
        5. Подписываемся на webhook обновлений (для DPD)
        """
        
        # === 1. ПРОВЕРКА ДУБЛЕЙ ===
        existing = self.db.exec(
            select(Delivery).where(Delivery.order_id == delivery_data.order_id)
        ).first()
        
        if existing:
            raise ValueError(f"Delivery for order {delivery_data.order_id} already exists")
        
        # === 2. РАЗРЕШЕНИЕ ПУНКТА ВЫДАЧИ ===
        if delivery_data.pickup_point_id and delivery_data.provider in [DeliveryProvider.DPD, DeliveryProvider.OMNIVA]:
            pickup_point = self.resolve_pickup_point(
                provider=delivery_data.provider.value,
                system_point_id=delivery_data.pickup_point_id
            )
            if not pickup_point:
                raise ValueError(
                    f"Pickup point {delivery_data.pickup_point_id} not available"
                )
            
            delivery_data.pickup_point_name = pickup_point.name
            delivery_data.pickup_point_address = pickup_point.address
            delivery_data.delivery_city = pickup_point.city
            delivery_data.delivery_zip = pickup_point.postal_code
            delivery_data.delivery_country = pickup_point.country_code
            if not delivery_data.delivery_address:
                delivery_data.delivery_address = pickup_point.address

        # === 3. ИНТЕГРАЦИЯ С ПРОВАЙДЕРОМ ===
        provider_tracking_number = None
        pin_code = None
        shipment_id = None
        
        if delivery_data.provider in [DeliveryProvider.DPD, DeliveryProvider.OMNIVA]:
            integration_result = self._dispatch_provider_integration(delivery_data)
            
            if integration_result:
                # Извлекаем данные из ответа провайдера
                provider_tracking_number = integration_result.get("provider_tracking_number")
                pin_code = integration_result.get("pin_code")
                shipment_id = integration_result.get("shipment_id")
                
                logger.info(
                    "Provider integration success | order_id=%s | "
                    "provider=%s | provider_tracking_number=%s | pin_code=%s",
                    delivery_data.order_id,
                    delivery_data.provider.value,
                    provider_tracking_number,
                    pin_code or "N/A",
                )

        # === 4. ГЕНЕРАЦИЯ ВНУТРЕННЕГО ТРЕКИНГ-НОМЕРА ===
        tracking_number = self.generate_tracking_number(delivery_data.provider.value)
        
        # Рассчитываем примерную дату доставки
        estimated_delivery = datetime.utcnow() + timedelta(hours=configs.TRANSIT_TIME_HOURS)
        
        # === 5. СОЗДАНИЕ ДОСТАВКИ В БД ===
        delivery = Delivery(
            order_id=delivery_data.order_id,
            provider=delivery_data.provider.value,
            tracking_number=tracking_number,
            # ← ВАЖНО: сохраняем DPD parcelNumber
            provider_tracking_number=provider_tracking_number,
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
            pickup_code=pin_code,  # PIN код из пакомата
            estimated_delivery_date=estimated_delivery,
            notes=f"Shipment ID: {shipment_id}" if shipment_id else None,
        )
        
        self.db.add(delivery)
        self.db.commit()
        self.db.refresh(delivery)
        
        # === 6. ПОДПИСКА НА WEBHOOK (для DPD) ===
        if delivery_data.provider == DeliveryProvider.DPD and provider_tracking_number:
            self._subscribe_to_dpd_updates(delivery, provider_tracking_number)
        
        # === 7. УВЕДОМЛЕНИЕ POSTS-SERVICE ===
        self._notify_posts_service_delivery_created(delivery)
        
        logger.info(
            "Delivery created | order_id=%s | delivery_id=%s | "
            "tracking_number=%s | provider_tracking_number=%s",
            delivery_data.order_id,
            delivery.id,
            tracking_number,
            provider_tracking_number or "N/A",
        )
        
        return delivery
    
    def _subscribe_to_dpd_updates(self, delivery: Delivery, parcel_number: str):
        """
        Подписаться на webhook обновления от DPD.
        
        DPD будет отправлять POST запросы на /api/v1/delivery/dpd/webhook
        при каждом изменении статуса посылки.
        """
        if not parcel_number:
            return
        
        # Конструируем callback URL
        # В production должен быть внешний HTTPS URL
        # callback_url = f"{configs.DELIVERY_SERVICE_URL}/api/v1/delivery/dpd/webhook"
        callback_url = f"{configs.FRONTEND_URL}api/v1/delivery/dpd/webhook"
        
        try:
            success = self.dpd_client.subscribe_to_tracking(parcel_number, callback_url)
            
            if success:
                logger.info(
                    "DPD webhook subscription | order_id=%s | parcel=%s | callback=%s",
                    delivery.order_id,
                    parcel_number,
                    callback_url,
                )
            else:
                logger.warning(
                    "DPD webhook subscription failed | order_id=%s | parcel=%s",
                    delivery.order_id,
                    parcel_number,
                )
        
        except Exception as e:
            logger.error(
                "Failed to subscribe to DPD webhook | parcel=%s | error=%s",
                parcel_number,
                str(e),
            )

    def get_delivery_by_tracking(self, tracking_number: str) -> Optional[Delivery]:
        """Получить доставку по внутреннему трекинг-номеру"""
        return self.db.exec(
            select(Delivery).where(Delivery.tracking_number == tracking_number)
        ).first()

    def get_delivery_by_order(self, order_id: int) -> Optional[Delivery]:
        """Получить доставку по ID заказа"""
        return self.db.exec(
            select(Delivery).where(Delivery.order_id == order_id)
        ).first()
    
    def get_delivery_by_provider_tracking(self, provider_tracking_number: str) -> Optional[Delivery]:
        """Получить доставку по provider_tracking_number (DPD parcelNumber)"""
        return self.db.exec(
            select(Delivery).where(Delivery.provider_tracking_number == provider_tracking_number)
        ).first()

    def get_delivery_history(self, delivery_id: int) -> list[DeliveryStatusHistory]:
        """Получить историю изменений статуса доставки"""
        return self.db.exec(
            select(DeliveryStatusHistory)
            .where(DeliveryStatusHistory.delivery_id == delivery_id)
            .order_by(DeliveryStatusHistory.created_at.desc())
        ).all()

    def update_delivery_status(
        self,
        delivery_id: int,
        status_update: DeliveryStatusUpdate
    ) -> Delivery:
        """
        Обновить статус доставки и отправить уведомления.
        
        Вызывается:
        - При обновлении от DPD webhook
        - При синхронизации по demand
        - При ручном изменении статуса
        """
        delivery = self.db.get(Delivery, delivery_id)
        if not delivery:
            raise ValueError(f"Delivery {delivery_id} not found")

        # Проверяем что статус действительно изменился
        if delivery.status == status_update.status.value:
            logger.info(f"Status unchanged for delivery {delivery_id}")
            return delivery

        old_status = delivery.status
        new_status = status_update.status.value

        # Обновляем статус
        delivery.status = new_status
        self.db.add(delivery)
        
        # Сохраняем в историю
        history = DeliveryStatusHistory(
            delivery_id=delivery.id,
            status=new_status,
            notes=status_update.notes,
        )
        self.db.add(history)
        
        # Обновляем временные метки в зависимости от статуса
        if new_status == DeliveryStatus.IN_TRANSIT.value:
            delivery.shipped_at = datetime.utcnow()
        elif new_status == DeliveryStatus.AT_PICKUP_POINT.value:
            delivery.arrived_at_pickup_point_at = datetime.utcnow()
            # Генерируем PIN код если его нет
            if not delivery.pickup_code:
                delivery.pickup_code = self.generate_pickup_code()
        elif new_status == DeliveryStatus.PICKED_UP.value:
            delivery.picked_up_at = datetime.utcnow()

        self.db.commit()
        self.db.refresh(delivery)

        logger.info(
            "Delivery status updated | delivery_id=%s | order_id=%s | "
            "%s -> %s | notes=%s",
            delivery.id,
            delivery.order_id,
            old_status,
            new_status,
            status_update.notes or "N/A",
        )

        # === ОТПРАВКА УВЕДОМЛЕНИЙ ===
        
        # SMS при прибытии в пункт выдачи
        if new_status == DeliveryStatus.AT_PICKUP_POINT.value:
            self._notify_pickup_point_arrival(delivery)
        
        # SMS при получении
        elif new_status == DeliveryStatus.PICKED_UP.value:
            self._notify_pickup_confirmation(delivery)
            self._notify_posts_service_delivery_received(delivery)

        return delivery
    
    def sync_dpd_tracking(self, delivery_id: int) -> Optional[Delivery]:
        """
        Синхронизировать статус с DPD по demand.
        
        Используется:
        - При обновлении страницы отслеживания на фронте
        - При периодической проверке статуса
        - Для отладки
        """
        delivery = self.db.get(Delivery, delivery_id)
        if not delivery:
            raise ValueError(f"Delivery {delivery_id} not found")

        if delivery.provider != "dpd":
            raise ValueError("Only DPD deliveries can be synced this way")

        parcel_number = delivery.provider_tracking_number
        if not parcel_number:
            logger.warning(f"No DPD parcel number for delivery {delivery_id}")
            return delivery

        # Запрашиваем текущий статус у DPD
        tracking_data = self.dpd_client.get_tracking_status(parcel_number)

        if tracking_data.get("dpd_status") in ("error", "unknown"):
            logger.warning(f"DPD tracking unavailable for parcel {parcel_number}")
            return delivery

        dpd_status_text = tracking_data.get("dpd_status", "")
        internal_status = self.dpd_client.map_dpd_status_to_internal(dpd_status_text)

        # Если статус не изменился, не обновляем
        if not internal_status or internal_status == delivery.status:
            logger.info(f"No status change for delivery {delivery_id}")
            return delivery

        logger.info(
            f"DPD status sync | delivery_id={delivery_id} | "
            f"{delivery.status} -> {internal_status} | dpd={dpd_status_text}"
        )

        # Обновляем статус
        return self.update_delivery_status(
            delivery_id,
            DeliveryStatusUpdate(
                status=internal_status,
                notes=f"DPD: {dpd_status_text}"
            )
        )

    # === УВЕДОМЛЕНИЯ ===

    def _notify_pickup_point_arrival(self, delivery: Delivery):
        """
        Отправить уведомление о прибытии в пункт выдачи.
        
        SMS: "Посылка прибыла в пункт выдачи. Код: 123456"
        """
        if delivery.notification_sent_at_pickup_point:
            return
        
        try:
            logger.info(f"Notifying about pickup point arrival | order_id={delivery.order_id}")
            
            # Здесь можно добавить реальную отправку SMS
            # Пока просто логируем
            
            delivery.notification_sent_at_pickup_point = True
            self.db.add(delivery)
            self.db.commit()
            
            logger.info(f"Pickup point notification sent | order_id={delivery.order_id}")
        
        except Exception as e:
            logger.error(f"Failed to send pickup point notification: {e}")

    def _notify_pickup_confirmation(self, delivery: Delivery):
        """
        Отправить уведомление о получении посылки.
        
        SMS: "Спасибо за покупку! Оставить отзыв: [ссылка]"
        """
        if delivery.notification_sent_picked_up:
            return
        
        try:
            logger.info(f"Notifying about delivery receipt | order_id={delivery.order_id}")
            
            # Здесь можно добавить реальную отправку SMS
            
            delivery.notification_sent_picked_up = True
            self.db.add(delivery)
            self.db.commit()
            
            logger.info(f"Delivery confirmation sent | order_id={delivery.order_id}")
        
        except Exception as e:
            logger.error(f"Failed to send confirmation: {e}")

    def _notify_posts_service_delivery_created(self, delivery: Delivery):
        """Уведомить posts-service что доставка создана"""
        try:
            logger.info(f"Notifying posts-service about delivery creation | order_id={delivery.order_id}")
            
            with httpx.Client(timeout=5.0) as client:
                response = client.post(
                    f"{configs.POSTS_SERVICE_URL}/api/v1/orders/delivery-events/created",
                    json={
                        "order_id": delivery.order_id,
                        "tracking_number": delivery.tracking_number,
                        "provider": delivery.provider,
                        "provider_tracking_number": delivery.provider_tracking_number,
                        "created_at": delivery.created_at.isoformat()
                    }
                )
                
                if response.status_code == 200:
                    logger.info(f"Posts-service notified | order_id={delivery.order_id}")
                else:
                    logger.warning(f"Posts-service notification failed: {response.status_code}")
        
        except Exception as e:
            logger.error(f"Failed to notify posts-service: {e}")

    def _notify_posts_service_delivery_received(self, delivery: Delivery):
        """Уведомить posts-service что доставка получена"""
        try:
            logger.info(f"Notifying posts-service about delivery receipt | order_id={delivery.order_id}")
            
            with httpx.Client(timeout=5.0) as client:
                response = client.post(
                    f"{configs.POSTS_SERVICE_URL}/api/v1/orders/delivery-events/receipts",
                    json={
                        "order_id": delivery.order_id,
                        "tracking_number": delivery.tracking_number,
                        "picked_up_at": delivery.picked_up_at.isoformat() if delivery.picked_up_at else None
                    }
                )
                
                if response.status_code == 200:
                    logger.info(f"Posts-service receipt notified | order_id={delivery.order_id}")
                else:
                    logger.warning(f"Posts-service receipt notification failed: {response.status_code}")
        
        except Exception as e:
            logger.error(f"Failed to notify posts-service about receipt: {e}")

    def simulate_delivery_process(self, delivery_id: int):
        """Имитация процесса доставки для тестирования"""
        delivery = self.db.get(Delivery, delivery_id)
        if not delivery:
            raise ValueError(f"Delivery {delivery_id} not found")
        
        if delivery.status == DeliveryStatus.CREATED.value:
            self.update_delivery_status(
                delivery_id,
                DeliveryStatusUpdate(
                    status=DeliveryStatus.IN_TRANSIT,
                    notes="Simulation: Package is in transit"
                )
            )
        
        logger.info(f"Delivery simulation started | order_id={delivery.order_id}")
        return delivery