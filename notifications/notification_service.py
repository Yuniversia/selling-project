# notification_service.py - Сервис для работы с SendPulse API

import base64
import requests
import time
import logging
from typing import Optional, Tuple
from datetime import datetime
from sqlmodel import Session

from configs import configs
from models import NotificationLog, NotificationTemplate, NotificationStatus, OrderNotificationData


# Настройка логирования
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class SendPulseService:
    """Сервис для отправки SMS и Email через SendPulse API"""
    
    API_BASE_URL = "https://api.sendpulse.com"
    TOKEN_URL = f"{API_BASE_URL}/oauth/access_token"
    SMS_URL = f"{API_BASE_URL}/sms/send"
    EMAIL_URL = f"{API_BASE_URL}/smtp/emails"
    
    def __init__(self):
        self.api_id = configs.sendpulse_api_id
        self.api_secret = configs.sendpulse_api_secret
        self._access_token = None
        self._token_expires_at = 0
        
        if not self.api_id or not self.api_secret:
            logger.warning("⚠️ SendPulse API credentials not configured!")
    
    def _get_access_token(self) -> str:
        """Получение OAuth токена от SendPulse"""
        # Проверяем, не истек ли токен
        if self._access_token and time.time() < self._token_expires_at:
            return self._access_token
        
        logger.info("🔑 Requesting new SendPulse access token...")
        
        try:
            response = requests.post(
                self.TOKEN_URL,
                json={
                    "grant_type": "client_credentials",
                    "client_id": self.api_id,
                    "client_secret": self.api_secret
                },
                headers={"Content-Type": "application/json"}
            )
            response.raise_for_status()
            
            data = response.json()
            self._access_token = data.get("access_token")
            expires_in = data.get("expires_in", 3600)
            self._token_expires_at = time.time() + expires_in - 60  # Обновляем за минуту до истечения
            
            logger.info("✅ SendPulse access token received")
            return self._access_token
            
        except Exception as e:
            logger.error(f"❌ Failed to get SendPulse token: {e}")
            raise
    
    def send_sms(self, phone: str, message: str) -> Tuple[bool, Optional[str], Optional[str]]:
        """
        Отправка SMS через SendPulse
        
        Returns:
            Tuple[success, external_id, error_message]
        """
        if not phone or not message:
            return False, None, "Phone or message is empty"
        
        try:
            token = self._get_access_token()
            
            # Форматируем телефон (SendPulse требует формат: +код без пробелов)
            formatted_phone = phone.strip().replace(" ", "").replace("-", "")
            if not formatted_phone.startswith("+"):
                formatted_phone = f"+{formatted_phone}"
            
            logger.info(f"📱 Sending SMS to {formatted_phone}")
            
            response = requests.post(
                self.SMS_URL,
                json={
                    "phones": [formatted_phone],
                    "body": message,
                    "sender": "LaisMarket"  # Можно настроить отправителя
                },
                headers={
                    "Authorization": f"Bearer {token}",
                    "Content-Type": "application/json"
                }
            )
            
            if response.status_code == 200:
                data = response.json()
                logger.info(f"✅ SMS sent successfully: {data}")
                
                # SendPulse возвращает массив результатов для каждого телефона
                if data.get("result"):
                    return True, str(data.get("id", "")), None
                else:
                    error = data.get("error", "Unknown error")
                    return False, None, error
            else:
                error = f"HTTP {response.status_code}: {response.text}"
                logger.error(f"❌ SMS send failed: {error}")
                return False, None, error
                
        except Exception as e:
            logger.error(f"❌ SMS send exception: {e}")
            return False, None, str(e)
    
    def send_email(self, 
                   email: str, 
                   subject: str, 
                   html_body: str,
                   from_name: str = "Lais Marketplace",
                   from_email: str = "noreply@yuniversia.eu") -> Tuple[bool, Optional[str], Optional[str]]:
        """
        Отправка Email через SendPulse SMTP
        
        Returns:
            Tuple[success, external_id, error_message]
        """
        if not email or not subject or not html_body:
            return False, None, "Email, subject or body is empty"
        
        try:
            token = self._get_access_token()
            
            logger.info(f"📧 Sending email to {email}")
            
            response = requests.post(
                self.EMAIL_URL,
                json={
                    "email": {
                        "html": html_body,
                        "text": html_body,  # Текстовая версия
                        "subject": subject,
                        "from": {
                            "name": from_name,
                            "email": from_email
                        },
                        "to": [
                            {
                                "email": email
                            }
                        ]
                    }
                },
                headers={
                    "Authorization": f"Bearer {token}",
                    "Content-Type": "application/json"
                }
            )
            
            if response.status_code == 200:
                data = response.json()
                logger.info(f"✅ Email sent successfully: {data}")
                return True, str(data.get("id", "")), None
            else:
                error = f"HTTP {response.status_code}: {response.text}"
                logger.error(f"❌ Email send failed: {error}")
                return False, None, error
                
        except Exception as e:
            logger.error(f"❌ Email send exception: {e}")
            return False, None, str(e)


class NotificationService:
    """Сервис для управления уведомлениями"""
    
    def __init__(self, db: Session):
        self.db = db
        self.sendpulse = SendPulseService()
    
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
    
    def send_order_notification_to_seller(self, order_data: OrderNotificationData) -> Tuple[bool, list[int], list[str]]:
        """Отправка уведомления продавцу о новом заказе (SMS + Email)"""
        notification_ids = []
        errors = []
        
        # Получаем шаблон
        template = self._get_template("order_created_seller")
        
        # Подготавливаем данные для шаблона
        template_data = {
            "seller_name": order_data.seller_name,
            "buyer_name": order_data.buyer_name,
            "product_name": order_data.product_name,
            "product_model": order_data.product_model or "",
            "order_price": f"{order_data.order_price:.2f}",
            "order_id": order_data.order_id,
            "frontend_url": configs.frontend_url
        }
        
        # Отправка SMS
        if order_data.seller_phone:
            if template and template.sms_text:
                sms_message = self._render_template(template.sms_text, template_data)
            else:
                sms_message = f"Новый заказ #{order_data.order_id}! {order_data.buyer_name} купил {order_data.product_name}. Сумма: €{order_data.order_price:.2f}"
            
            success, external_id, error = self._send_with_retry(
                "sms", order_data.seller_phone, None, sms_message, order_data.order_id
            )
            
            if success and external_id:
                notification_ids.append(external_id)
            elif error:
                errors.append(f"SMS: {error}")
        
        # Отправка Email
        if order_data.seller_email:
            if template and template.email_subject and template.email_body:
                email_subject = self._render_template(template.email_subject, template_data)
                email_body = self._render_template(template.email_body, template_data)
            else:
                email_subject = f"Новый заказ #{order_data.order_id}"
                email_body = f"""
                <html>
                <body>
                    <h2>Новый заказ!</h2>
                    <p>Здравствуйте, {order_data.seller_name}!</p>
                    <p>У вас новый заказ:</p>
                    <ul>
                        <li><strong>Товар:</strong> {order_data.product_name} {order_data.product_model or ""}</li>
                        <li><strong>Покупатель:</strong> {order_data.buyer_name}</li>
                        <li><strong>Сумма:</strong> €{order_data.order_price:.2f}</li>
                        <li><strong>Доставка:</strong> {order_data.delivery_method}</li>
                    </ul>
                    <p><a href="{configs.frontend_url}/orders/{order_data.order_id}">Посмотреть заказ</a></p>
                </body>
                </html>
                """
            
            success, external_id, error = self._send_with_retry(
                "email", None, order_data.seller_email, email_body, 
                order_data.order_id, email_subject
            )
            
            if success and external_id:
                notification_ids.append(external_id)
            elif error:
                errors.append(f"Email: {error}")
        
        return len(errors) == 0, notification_ids, errors
    
    def send_order_confirmation_to_buyer(self, order_data: OrderNotificationData) -> Tuple[bool, list[int], list[str]]:
        """Отправка подтверждения заказа покупателю (Email)"""
        notification_ids = []
        errors = []
        
        template = self._get_template("order_created_buyer")
        
        tracking_url = order_data.tracking_url or f"{configs.frontend_url}/orders/{order_data.order_id}"
        
        template_data = {
            "buyer_name": order_data.buyer_name,
            "product_name": order_data.product_name,
            "product_model": order_data.product_model or "",
            "order_price": f"{order_data.order_price:.2f}",
            "order_id": order_data.order_id,
            "tracking_url": tracking_url,
            "delivery_method": order_data.delivery_method
        }
        
        if template and template.email_subject and template.email_body:
            email_subject = self._render_template(template.email_subject, template_data)
            email_body = self._render_template(template.email_body, template_data)
        else:
            email_subject = f"Подтверждение заказа #{order_data.order_id}"
            email_body = f"""
            <html>
            <body>
                <h2>Заказ подтвержден!</h2>
                <p>Здравствуйте, {order_data.buyer_name}!</p>
                <p>Ваш заказ успешно создан:</p>
                <ul>
                    <li><strong>Номер заказа:</strong> #{order_data.order_id}</li>
                    <li><strong>Товар:</strong> {order_data.product_name} {order_data.product_model or ""}</li>
                    <li><strong>Сумма:</strong> €{order_data.order_price:.2f}</li>
                    <li><strong>Доставка:</strong> {order_data.delivery_method}</li>
                </ul>
                <p><a href="{tracking_url}">Отследить заказ</a></p>
                <p>Спасибо за покупку!</p>
            </body>
            </html>
            """
        
        success, external_id, error = self._send_with_retry(
            "email", None, order_data.buyer_email, email_body,
            order_data.order_id, email_subject
        )
        
        if success and external_id:
            notification_ids.append(external_id)
        elif error:
            errors.append(f"Email: {error}")
        
        return len(errors) == 0, notification_ids, errors
    
    def send_review_request(self, order_data: OrderNotificationData) -> Tuple[bool, list[int], list[str]]:
        """Отправка запроса на отзыв после получения заказа"""
        notification_ids = []
        errors = []
        
        template = self._get_template("order_review_request")
        
        review_url = order_data.review_url or f"{configs.frontend_url}/orders/{order_data.order_id}/review"
        
        template_data = {
            "buyer_name": order_data.buyer_name,
            "product_name": order_data.product_name,
            "seller_name": order_data.seller_name,
            "order_id": order_data.order_id,
            "review_url": review_url
        }
        
        if template and template.email_subject and template.email_body:
            email_subject = self._render_template(template.email_subject, template_data)
            email_body = self._render_template(template.email_body, template_data)
        else:
            email_subject = "Оцените продавца"
            email_body = f"""
            <html>
            <body>
                <h2>Оцените ваш опыт покупки</h2>
                <p>Здравствуйте, {order_data.buyer_name}!</p>
                <p>Вы получили заказ #{order_data.order_id} ({order_data.product_name}).</p>
                <p>Пожалуйста, оцените продавца {order_data.seller_name} и оставьте отзыв:</p>
                <p><a href="{review_url}" style="background-color: #4CAF50; color: white; padding: 10px 20px; text-decoration: none; border-radius: 5px;">Оставить отзыв</a></p>
                <p>Ваш отзыв поможет другим покупателям!</p>
            </body>
            </html>
            """
        
        success, external_id, error = self._send_with_retry(
            "email", None, order_data.buyer_email, email_body,
            order_data.order_id, email_subject
        )
        
        if success and external_id:
            notification_ids.append(external_id)
        elif error:
            errors.append(f"Email: {error}")
        
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
                    success, external_id, error = self.sendpulse.send_sms(phone, message)
                elif channel == "email":
                    success, external_id, error = self.sendpulse.send_email(email, subject, message)
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
