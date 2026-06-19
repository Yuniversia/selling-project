"""DPD провайдер доставки: simulation / test (sandbox) / real.

Универсальный подход:
- Сохраняет provider_tracking_number (DPD parcelNumber) в БД
- Подписывается на webhook для получения обновлений статуса
- Может запрашивать статус по demand через get_tracking_status
"""

import logging
import httpx
import urllib.parse
from typing import Optional, Dict, Any

from configs import configs
from models import DeliveryCreate
from providers.base import DeliveryProviderClient


logger = logging.getLogger(__name__)


class DPDProviderClient(DeliveryProviderClient):
    """
    Универсальный клиент DPD API с поддержкой всех режимов.
    
    Key improvements:
    1. Сохраняет DPD parcelNumber в provider_tracking_number
    2. Возвращает структурированный ответ
    3. Поддерживает подписку на webhook
    4. Универсальный код для test и real сред
    """
    
    def get_provider_name(self) -> str:
        return "dpd"

    def create_shipment(self, delivery_data: DeliveryCreate) -> Dict[str, Any]:
        """
        Создание shipment в DPD и возврат parcelNumber.
        
        Returns:
            {
                "provider_tracking_number": "12345678901234",  # DPD parcelNumber
                "pin_code": "123456",  # Код для пакомата (если есть)
                "shipment_id": "uuid",  # ID shipment в DPD
                "status": "created",
            }
        """
        mode = configs.get_dpd_mode()
        
        if mode == "simulation":
            return self._simulate(delivery_data)
        
        return self._create_shipment_universal(delivery_data)

    def _simulate(self, delivery_data: DeliveryCreate) -> Dict[str, Any]:
        """Режим симуляции для локальной разработки"""
        logger.info(
            f"DPD simulation mode | order_id={delivery_data.order_id} | "
            f"pickup_point={delivery_data.pickup_point_id}"
        )
        
        # Генерируем фейковый parcelNumber (14 цифр как в DPD)
        fake_parcel_number = f"{delivery_data.order_id:014d}"
        
        return {
            "provider_tracking_number": fake_parcel_number,
            "pin_code": "999999",  # Фиксированный код для теста
            "shipment_id": f"SIM-{delivery_data.order_id}",
            "status": "created",
        }

    def _create_shipment_universal(self, delivery_data: DeliveryCreate) -> Dict[str, Any]:
        """
        Универсальный метод для test и real окружений.
        
        Разница только в:
        - URL базы (TEST_API_BASE_URL vs REAL_API_BASE_URL)
        - Аутентификации (Bearer token vs Basic auth)
        - Всё остальное идентично
        """
        mode = configs.get_dpd_mode()
        is_test_mode = mode == "test"
        
        # Выбираем параметры в зависимости от режима
        if is_test_mode:
            base_url = configs.DPD_TEST_API_BASE_URL
            auth_header = {"Authorization": f"Bearer {configs.DPD_TEST_API_KEY}"}
            auth_tuple = None
        else:
            base_url = configs.DPD_REAL_API_BASE_URL
            auth_header = {}
            auth_tuple = (configs.DPD_API_KEY, configs.DPD_API_SECRET)
        
        endpoint = f"{base_url}/shipments"
        
        # === ПОДГОТОВКА ДАННЫХ ОТПРАВИТЕЛЯ ===
        sender_address = {
            "name": delivery_data.sender_name[:35],
            "phone": self._format_phone(delivery_data.sender_phone, delivery_data.sender_country or "LV"),
            "email": delivery_data.sender_email or "noreply@marketplace.local",
            "street": (delivery_data.sender_address or "Marketplace Sender")[:35],
            "streetNo": "1",
            "city": (delivery_data.sender_city or "Riga")[:35],
            "postalCode": (delivery_data.sender_zip or "1001")[:7],
            "country": (delivery_data.sender_country or "LV").upper()[:2],
        }
        
        # === ПОДГОТОВКА ДАННЫХ ПОЛУЧАТЕЛЯ ===
        receiver_address = {
            "name": delivery_data.recipient_name[:35],
            "phone": self._format_phone(delivery_data.recipient_phone, delivery_data.delivery_country or "LV"),
            "email": delivery_data.recipient_email,
            "street": (delivery_data.delivery_address or "Pickup Point")[:35],
            "streetNo": "1",
            "city": (delivery_data.delivery_city or "City")[:35],
            "postalCode": (delivery_data.delivery_zip or "0000")[:7],
            "country": (delivery_data.delivery_country or "LV").upper()[:2],
        }
        
        # Если указана точка выдачи, добавляем pudoId вместо адреса
        if delivery_data.pickup_point_id:
            receiver_address["pudoId"] = delivery_data.pickup_point_id[:20]
        
        # === ПОДГОТОВКА ПАРАМЕТ SHIPMENT ===
        payload = [{
            "senderAddress": sender_address,
            "receiverAddress": receiver_address,
            "service": {
                "serviceAlias": "DPD PICKUP"
            },
            "shipmentFlags": {
                "generatesDplPin": True  # Генерируем PIN для цифровой метки
            },
            "parcels": [
                {"weight": float(delivery_data.weight or 1.0)}
            ],
            "shipmentReferences": [str(delivery_data.order_id)]
        }]
        
        logger.info(
            "DPD shipment creation | order_id=%s | mode=%s | endpoint=%s",
            delivery_data.order_id,
            "test" if is_test_mode else "real",
            endpoint,
        )
        
        try:
            headers = {
                "Content-Type": "application/json",
                **auth_header
            }
            
            with httpx.Client(timeout=15.0) as client:
                response = client.post(endpoint, json=payload, headers=headers, auth=auth_tuple)
                
                # Логируем для отладки
                if response.status_code not in (200, 201):
                    logger.error(
                        "DPD API failed | order_id=%s | status=%s | response=%s",
                        delivery_data.order_id,
                        response.status_code,
                        response.text[:500],
                    )
                
                if response.status_code not in (200, 201):
                    raise ValueError(
                        f"DPD API failed with status {response.status_code}: {response.text[:500]}"
                    )
                
                response_data = response.json()
                
                # DPD возвращает список если payload был список
                if isinstance(response_data, list):
                    response_data = response_data[0] if response_data else {}
                
                # === ИЗВЛЕЧЕНИЕ ДАННЫХ ИЗ ОТВЕТА ===
                
                # DPD parcelNumber (14 цифр) - это основной трекинг номер
                parcel_number = None
                parcel_numbers = response_data.get("parcelNumbers", [])
                if parcel_numbers:
                    parcel_number = str(parcel_numbers[0])
                
                if not parcel_number:
                    # Если parcelNumbers не в списке, смотрим в parcels
                    parcels = response_data.get("parcels", [])
                    for parcel in parcels:
                        if isinstance(parcel, dict) and "parcelNumber" in parcel:
                            parcel_number = str(parcel["parcelNumber"])
                            break
                
                if not parcel_number:
                    raise ValueError("DPD API did not return parcelNumber")
                
                # PIN код для цифровой метки (для пакоматов)
                pin_code = self._extract_pin_from_response(response_data)
                
                # Shipment ID для будущих операций
                shipment_id = response_data.get("id")
                
                logger.info(
                    "DPD shipment created | order_id=%s | parcel_number=%s | pin_code=%s",
                    delivery_data.order_id,
                    parcel_number,
                    pin_code or "N/A",
                )
                
                return {
                    "provider_tracking_number": parcel_number,  # ← ВАЖНО: сохраняем в БД
                    "pin_code": pin_code,
                    "shipment_id": shipment_id,
                    "status": "created",
                }
        
        except httpx.RequestError as e:
            logger.error(
                "DPD API request error | order_id=%s | error=%s",
                delivery_data.order_id,
                str(e),
            )
            raise ValueError(f"DPD API request failed: {str(e)}")
    
    def get_tracking_status(self, parcel_number: str) -> Dict[str, Any]:
        """
        Получить статус посылки из DPD по demand.
        
        Args:
            parcel_number: 14-значный номер посылки из DPD
        
        Returns:
            {
                "dpd_status": "En route",  # Текстовый статус от DPD
                "dpd_datetime": "2024-01-15 14:30:00",
                "events": [...]  # История всех событий
            }
        """
        mode = configs.get_dpd_mode()
        
        if mode == "simulation":
            return {
                "dpd_status": "En route",
                "dpd_datetime": "",
                "events": [],
                "parcel_number": parcel_number,
            }
        
        is_test_mode = mode == "test"
        
        if is_test_mode:
            base_url = configs.DPD_TEST_API_BASE_URL
            auth_header = {"Authorization": f"Bearer {configs.DPD_TEST_API_KEY}"}
            auth_tuple = None
        else:
            base_url = configs.DPD_REAL_API_BASE_URL
            auth_header = {}
            auth_tuple = (configs.DPD_API_KEY, configs.DPD_API_SECRET)
        
        try:
            headers = {
                "Accept": "application/json",
                **auth_header
            }
            
            with httpx.Client(timeout=10.0) as client:
                response = client.get(
                    f"{base_url}/status/tracking",
                    headers=headers,
                    auth=auth_tuple,
                    params={
                        "pknr": parcel_number,  # 14-значный номер
                        "detail": 0,  # basic: только текстовый статус + dateTime
                        "show_all": 1,  # Вся история
                        "lang": "en",
                    },
                )
                
                if response.status_code != 200:
                    logger.warning(
                        f"DPD tracking failed | parcel={parcel_number} | status={response.status_code}"
                    )
                    return {"dpd_status": "unknown", "dpd_datetime": "", "events": []}
                
                data = response.json()
                
                # Ответ - список событий для каждой посылки
                parcel_data = next(
                    (p for p in data if str(p.get("parcelNumber")) == str(parcel_number)),
                    data[0] if data else {}
                )
                
                if "error" in parcel_data:
                    logger.warning(f"DPD error for {parcel_number}: {parcel_data['error']}")
                    return {"dpd_status": "unknown", "dpd_datetime": "", "events": []}
                
                events = parcel_data.get("details", [])
                latest = events[0] if events else {}
                
                return {
                    "dpd_status": latest.get("status", "unknown"),
                    "dpd_datetime": latest.get("dateTime", ""),
                    "events": events,
                    "parcel_number": parcel_number,
                }
        
        except Exception as e:
            logger.error(f"DPD tracking error | parcel={parcel_number} | error={e}")
            return {"dpd_status": "error", "dpd_datetime": "", "events": []}
    
    def subscribe_to_tracking(self, parcel_number: str, callback_url: str) -> bool:
        """
        Подписаться на обновления статуса посылки.
        
        DPD будет шлать POST на callback_url при каждом изменении статуса.
        
        Args:
            parcel_number: 14-значный номер посылки
            callback_url: HTTPS URL для получения webhooks
        
        Returns:
            True если подписка успешна
        """
        mode = configs.get_dpd_mode()
        
        if mode == "simulation":
            logger.info(f"DPD: simulated subscription for {parcel_number}")
            return True
        
        is_test_mode = mode == "test"
        
        if is_test_mode:
            base_url = configs.DPD_TEST_API_BASE_URL
            auth_header = {"Authorization": f"Bearer {configs.DPD_TEST_API_KEY}"}
            auth_tuple = None
        else:
            base_url = configs.DPD_REAL_API_BASE_URL
            auth_header = {}
            auth_tuple = (configs.DPD_API_KEY, configs.DPD_API_SECRET)
        
        try:
            headers = {**auth_header}
            
            with httpx.Client(timeout=5.0) as client:
                response = client.get(
                    f"{base_url}/status/events/subscribetoparcel",
                    headers=headers,
                    auth=auth_tuple,
                    params={
                        "parcelnumber": parcel_number,
                        "callbackurl": urllib.parse.quote(callback_url, safe=""),
                    },
                )
            
            success = response.status_code == 200
            logger.info(
                f"DPD subscription | parcel={parcel_number} | "
                f"callback={callback_url} | status={response.status_code}"
            )
            return success
        
        except Exception as e:
            logger.error(f"DPD subscription error | parcel={parcel_number} | error={e}")
            return False
    
    def unsubscribe_from_tracking(self, parcel_number: str, callback_url: str) -> bool:
        """Отписаться от обновлений статуса посылки"""
        mode = configs.get_dpd_mode()
        
        if mode == "simulation":
            return True
        
        is_test_mode = mode == "test"
        
        if is_test_mode:
            base_url = configs.DPD_TEST_API_BASE_URL
            auth_header = {"Authorization": f"Bearer {configs.DPD_TEST_API_KEY}"}
            auth_tuple = None
        else:
            base_url = configs.DPD_REAL_API_BASE_URL
            auth_header = {}
            auth_tuple = (configs.DPD_API_KEY, configs.DPD_API_SECRET)
        
        try:
            headers = {**auth_header}
            
            with httpx.Client(timeout=5.0) as client:
                response = client.get(
                    f"{base_url}/status/events/unsubscribetoparcel",
                    headers=headers,
                    auth=auth_tuple,
                    params={
                        "parcelnumber": parcel_number,
                        "callbackurl": urllib.parse.quote(callback_url, safe=""),
                    },
                )
            
            return response.status_code == 200
        
        except Exception as e:
            logger.error(f"DPD unsubscription error | parcel={parcel_number} | error={e}")
            return False
    
    # === HELPERS ===
    
    @staticmethod
    def _format_phone(phone: str, country_code: str) -> str:
        """
        Форматирование телефона в международный формат.
        
        DPD требует формат: +37112345678 или похожий с + и кодом страны.
        """
        phone = phone.strip()
        
        # Если уже есть +, вернём как есть
        if phone.startswith("+"):
            return phone
        
        # Если нет кода страны, добавляем
        country_codes = {
            "LV": "371",
            "LT": "370",
            "EE": "372",
        }
        
        code = country_codes.get(country_code.upper(), "371")
        
        # Убираем ноль в начале если есть
        if phone.startswith("0"):
            phone = phone[1:]
        
        return f"+{code}{phone}"
    
    @staticmethod
    def _extract_pin_from_response(response_data: Dict[str, Any]) -> Optional[str]:
        """Извлечение PIN кода из ответа DPD"""
        
        # Вариант 1: dplPin на верхнем уровне
        if "dplPin" in response_data and response_data["dplPin"]:
            pin_list = response_data["dplPin"]
            if isinstance(pin_list, list) and len(pin_list) > 0:
                if isinstance(pin_list[0], dict):
                    return pin_list[0].get("pin") or pin_list[0].get("pinCode")
        
        # Вариант 2: parcels
        parcels = response_data.get("parcels", [])
        if parcels and isinstance(parcels, list):
            for parcel in parcels:
                if isinstance(parcel, dict):
                    pin = parcel.get("pin") or parcel.get("pinCode") or parcel.get("dplPin")
                    if pin:
                        return pin
        
        # Вариант 3: additionalServices
        if "additionalServices" in response_data:
            for service in response_data.get("additionalServices", []):
                if isinstance(service, dict):
                    pin = service.get("pin") or service.get("pinCode")
                    if pin:
                        return pin
        
        return None
    
    @staticmethod
    def map_dpd_status_to_internal(dpd_status: str) -> Optional[str]:
        """
        Маппинг текстовых статусов от DPD на внутренние статусы системы.
        
        Статусы из DPD документации (раздел 6.1.2, английский язык).
        """
        mapping = {
            "Dropped in Pickup Point": "created",
            "Picked up by Courier": "in_transit",
            "En route": "in_transit",
            "Delivered to Pickup Point": "at_pickup_point",
            "Picked up by Consignee from Pickup point": "picked_up",
            "Delivered to Consignee": "picked_up",
            "Returning to Sender": "returned",
            "Returned to Sender": "returned",
        }
        return mapping.get(dpd_status)