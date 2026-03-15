# notification_service.py - Сервис для работы с SendBerry API

import requests
import time
import logging
from typing import Optional, Tuple
from datetime import datetime
from sqlmodel import Session
from urllib.parse import urlencode

from configs import configs
from models import NotificationLog, NotificationTemplate, NotificationStatus, OrderNotificationData


# Настройка логирования
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class SendBerryService:
    """Сервис для отправки SMS через SendBerry API"""
    
    API_URL = "https://api.sendberry.com/SMS/SEND"
    
    def __init__(self):
        self.api_key = configs.sendberry_api_key
        self.api_name = configs.sendberry_api_name
        self.api_password = configs.sendberry_api_password
        self.sender_id = configs.sendberry_sender_id
        
        if not self.api_key or not self.api_name or not self.api_password:
            logger.warning("⚠️ SendBerry API credentials not configured!")
    
    def send_sms(self, phone: str, message: str, sms_id: Optional[str] = None) -> Tuple[bool, Optional[str], Optional[str]]:
        """
        Отправка SMS через SendBerry API
        
        Args:
            phone: Номер телефона в международном формате E.164
            message: Текст сообщения (UTF-8)
            sms_id: Опциональный custom message ID
        
        Returns:
            Tuple[success, external_id, error_message]
        """
        if not phone or not message:
            return False, None, "Phone or message is empty"
        
        # Форматируем телефон (E.164 формат)
        formatted_phone = phone.strip().replace(" ", "").replace("-", "")
        if not formatted_phone.startswith("+"):
            formatted_phone = f"+{formatted_phone}"
        
        logger.info(f"📱 Sending SMS to {formatted_phone} via SendBerry")
        
        try:
            # Подготавливаем параметры запроса
            params = {
                "key": self.api_key,
                "name": self.api_name,
                "password": self.api_password,
                "from": self.sender_id,
                "to[]": formatted_phone,
                "content": message,
                "response": "JSON"  # Получаем ответ в JSON формате
            }
            
            # Добавляем опциональный SMS_ID если указан
            if sms_id:
                params["SMS_ID"] = sms_id
            
            # Отправляем POST запрос
            response = requests.post(
                self.API_URL,
                data=params,
                headers={"Content-Type": "application/x-www-form-urlencoded"},
                timeout=30
            )
            
            # Логируем сырой ответ для отладки
            logger.info(f"SendBerry response status: {response.status_code}")
            logger.info(f"SendBerry response body: {response.text}")
            
            # Парсим ответ
            if response.status_code == 200:
                try:
                    data = response.json()
                    
                    if data.get("status") == "ok":
                        external_id = data.get("ID", "")
                        cost = data.get("cost", 0)
                        count = data.get("count", 1)
                        
                        logger.info(f"✅ SMS sent successfully! ID: {external_id}, Cost: {cost}, Parts: {count}")
                        return True, external_id, None
                    else:
                        # Статус error
                        error_msg = data.get("message", "Unknown error from SendBerry")
                        logger.error(f"❌ SendBerry returned error status: {error_msg}")
                        return False, None, error_msg
                        
                except Exception as e:
                    logger.error(f"❌ Failed to parse SendBerry JSON response: {e}")
                    return False, None, f"Invalid response format: {response.text}"
            else:
                error = f"HTTP {response.status_code}: {response.text}"
                logger.error(f"❌ SMS send failed: {error}")
                return False, None, error
                
        except requests.exceptions.Timeout:
            logger.error("❌ SendBerry API request timeout")
            return False, None, "Request timeout"
        except requests.exceptions.RequestException as e:
            logger.error(f"❌ SendBerry API request failed: {e}")
            return False, None, str(e)
        except Exception as e:
            logger.error(f"❌ SMS send exception: {e}")
            return False, None, str(e)


class NotificationService:
    """Сервис для управления уведомлениями"""
    
    def __init__(self, db: Session):
        self.db = db
        self.sendberry = SendBerryService()
    
    def _get_template(self, notification_type: str) -> Optional[NotificationTemplate]:
        """Получение шаблона уведомления"""
        from sqlmodel import select
        
        statement = select(NotificationTemplate).where(
            NotificationTemplate.notification_type == notification_type,
            NotificationTemplate.is_active == True
        )
        return self.db.exec(statement).first()
    
    def _render_template(self, template_text: str, data: dict) -> str:
        """Простая замена переменных в шаблоне"""
        result = template_text
        for key, value in data.items():
            placeholder = f"{{{key}}}"
            result = result.replace(placeholder, str(value))
        return result
    
    def send_order_paid_notification(self, order_data: OrderNotificationData) -> Tuple[bool, list[int], list[str]]:
        """Отправка SMS уведомлений после оплаты заказа (продавцу и покупателю)"""
        notification_ids = []
        errors = []

        logger.info(
            f"ORDER_PAID notification | order_id={order_data.order_id} | "
            f"product='{order_data.product_name}' | price=€{order_data.order_price:.2f} | "
            f"seller='{order_data.seller_name}' (phone={'set' if order_data.seller_phone else 'MISSING'}) | "
            f"buyer='{order_data.buyer_name}' (phone={'set' if order_data.buyer_phone else 'missing'})"
        )
        
        # Отправляем продавцу
        if order_data.seller_phone:
            template = self._get_template("order_paid_seller")
            
            template_data = {
                "seller_name": order_data.seller_name,
                "buyer_name": order_data.buyer_name,
                "product_name": order_data.product_name,
                "product_model": order_data.product_model or "",
                "order_price": f"{order_data.order_price:.2f}",
                "order_id": order_data.order_id,
                "frontend_url": configs.frontend_url
            }
            
            if template and template.sms_text:
                sms_message = self._render_template(template.sms_text, template_data)
            else:
                sms_message = f"Товар '{order_data.product_name}' куплен! Заказ #{order_data.order_id} оплачен (€{order_data.order_price:.2f}). Подготовьте к отгрузке."
            
            success, external_id, error = self._send_with_retry(
                "sms", order_data.seller_phone, None, sms_message, order_data.order_id
            )
            
            if success and external_id:
                notification_ids.append(external_id)
            elif error:
                errors.append(f"SMS to seller: {error}")
        else:
            logger.warning(
                f"Seller has no phone number — SMS skipped | "
                f"order_id={order_data.order_id} | seller='{order_data.seller_name}' | "
                f"product='{order_data.product_name}'"
            )
            errors.append("Seller phone number not provided")
        
        # Отправляем покупателю
        if order_data.buyer_phone:
            template = self._get_template("order_paid_buyer")
            
            tracking_url = order_data.tracking_url or f"{configs.frontend_url}api/v1/delivery/order/{order_data.order_id}"
            tracking_number = order_data.tracking_url.split('/')[-1] if order_data.tracking_url else "будет предоставлен"
            
            template_data = {
                "buyer_name": order_data.buyer_name,
                "product_name": order_data.product_name,
                "product_model": order_data.product_model or "",
                "order_price": f"{order_data.order_price:.2f}",
                "order_id": order_data.order_id,
                "tracking_url": tracking_url,
                "tracking_number": tracking_number,
                "delivery_method": order_data.delivery_method
            }
            
            if template and template.sms_text:
                sms_message = self._render_template(template.sms_text, template_data)
            else:
                sms_message = f"Оплата успешна! Заказ #{order_data.order_id} {order_data.product_name} за €{order_data.order_price:.2f}. Товар будет отправлен. Отслеживание: {tracking_url}"
            
            success, external_id, error = self._send_with_retry(
                "sms", order_data.buyer_phone, None, sms_message, order_data.order_id
            )
            
            if success and external_id:
                notification_ids.append(external_id)
            elif error:
                errors.append(f"SMS to buyer: {error}")
        
        return len(errors) == 0, notification_ids, errors
    
    def send_review_request(self, order_data: OrderNotificationData) -> Tuple[bool, list[int], list[str]]:
        """Отправка SMS запроса на отзыв после получения заказа"""
        notification_ids = []
        errors = []

        logger.info(
            f"ORDER_REVIEW_REQUEST notification | order_id={order_data.order_id} | "
            f"product='{order_data.product_name}' | seller='{order_data.seller_name}' | "
            f"buyer='{order_data.buyer_name}' (phone={'set' if order_data.buyer_phone else 'missing — SMS skipped'})"
        )

        if not order_data.buyer_phone:
            # Если нет телефона покупателя, просто возвращаем успех (не критично)
            return True, [], []
        
        template = self._get_template("order_review_request")
        
        review_url = order_data.review_url or f"{configs.frontend_url}orders/{order_data.order_id}/review"
        
        template_data = {
            "buyer_name": order_data.buyer_name,
            "product_name": order_data.product_name,
            "seller_name": order_data.seller_name,
            "order_id": order_data.order_id,
            "review_url": review_url
        }
        
        # SMS сообщение покупателю после получения
        if template and template.sms_text:
            sms_message = self._render_template(template.sms_text, template_data)
        else:
            sms_message = f"Спасибо за использование нашего сервиса! Заказ #{order_data.order_id} получен. Пожалуйста, оставьте отзыв о товаре '{order_data.product_name}': {review_url}"
        
        success, external_id, error = self._send_with_retry(
            "sms", order_data.buyer_phone, None, sms_message, order_data.order_id
        )
        
        if success and external_id:
            notification_ids.append(external_id)
        elif error:
            errors.append(f"SMS: {error}")
        
        return len(errors) == 0, notification_ids, errors
    
    def _send_with_retry(self, 
                        channel: str, 
                        phone: Optional[str], 
                        email: Optional[str],
                        message: str,
                        order_id: int,
                        subject: Optional[str] = None,
                        max_retries: int = 3) -> Tuple[bool, Optional[int], Optional[str]]:
        """Отправка уведомления с retry механизмом"""
        
        # Создаем лог в БД
        log = NotificationLog(
            notification_type="order_notification",
            channel=channel,
            recipient_phone=phone,
            recipient_email=email,
            subject=subject,
            message=message,
            order_id=order_id,
            status=NotificationStatus.PENDING.value
        )
        self.db.add(log)
        self.db.commit()
        self.db.refresh(log)
        
        # Пытаемся отправить с retry
        for attempt in range(max_retries):
            try:
                if channel == "sms":
                    success, external_id, error = self.sendberry.send_sms(phone, message)
                else:
                    success, external_id, error = False, None, f"Unknown channel: {channel}"
                
                if success:
                    log.status = NotificationStatus.SENT.value
                    log.sent_at = datetime.utcnow()
                    log.external_id = external_id
                    self.db.commit()
                    return True, log.id, None
                else:
                    log.retry_count = attempt + 1
                    log.error_message = error
                    log.status = NotificationStatus.RETRY.value if attempt < max_retries - 1 else NotificationStatus.FAILED.value
                    self.db.commit()
                    
                    if attempt < max_retries - 1:
                        logger.warning(f"Send attempt {attempt + 1}/{max_retries} failed, retrying — order_id={order_id} | error={error}")
                        time.sleep(2 ** attempt)  # Exponential backoff
                    
            except Exception as e:
                logger.error(f"❌ Send attempt {attempt + 1} failed: {e}")
                log.retry_count = attempt + 1
                log.error_message = str(e)
                log.status = NotificationStatus.RETRY.value if attempt < max_retries - 1 else NotificationStatus.FAILED.value
                self.db.commit()
                
                if attempt < max_retries - 1:
                    time.sleep(2 ** attempt)
        
        return False, log.id, log.error_message
