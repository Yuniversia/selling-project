"""
Web Push Notification Service
Handles push notification subscriptions and sending
"""
import os
import json
import logging
from typing import Optional, List
from pywebpush import webpush, WebPushException
from sqlmodel import Session, select
from push_models import PushSubscription, PushSubscriptionCreate
from database import engine

logger = logging.getLogger(__name__)


class PushNotificationService:
    """Service for managing web push notifications"""
    
    def __init__(self):
        # VAPID keys for push notifications
        # In production, these should be stored in environment variables
        self.vapid_private_key = os.getenv("VAPID_PRIVATE_KEY")
        self.vapid_public_key = os.getenv("VAPID_PUBLIC_KEY")
        self.vapid_claims = {
            "sub": os.getenv("VAPID_SUBJECT", "mailto:admin@ss.lv")
        }
        
        if not self.vapid_private_key or not self.vapid_public_key:
            logger.warning("⚠️ VAPID keys not configured. Push notifications will not work.")
            logger.warning(f"VAPID_PRIVATE_KEY: {'SET' if self.vapid_private_key else 'NOT SET'}")
            logger.warning(f"VAPID_PUBLIC_KEY: {'SET' if self.vapid_public_key else 'NOT SET'}")
        else:
            logger.info("✅ VAPID keys configured successfully")
            logger.info(f"VAPID Public Key: {self.vapid_public_key[:20]}...")
    
    def save_subscription(self, user_id: str, subscription_data: PushSubscriptionCreate) -> Optional[PushSubscription]:
        """
        Save or update a push subscription for a user
        
        Args:
            user_id: User ID (registered or anonymous UUID)
            subscription_data: Subscription data from browser
            
        Returns:
            PushSubscription object or None if failed
        """
        try:
            with Session(engine) as session:
                # Check if subscription already exists
                statement = select(PushSubscription).where(
                    PushSubscription.endpoint == subscription_data.endpoint
                )
                existing = session.exec(statement).first()
                
                if existing:
                    # Update existing subscription
                    existing.user_id = user_id
                    existing.p256dh = subscription_data.keys.get("p256dh", "")
                    existing.auth = subscription_data.keys.get("auth", "")
                    existing.is_active = True
                    session.add(existing)
                    session.commit()
                    session.refresh(existing)
                    logger.info(f"✅ Updated push subscription for user {user_id}, endpoint: {subscription_data.endpoint[:50]}...")
                    return existing
                else:
                    # Create new subscription
                    subscription = PushSubscription(
                        user_id=user_id,
                        endpoint=subscription_data.endpoint,
                        p256dh=subscription_data.keys.get("p256dh", ""),
                        auth=subscription_data.keys.get("auth", "")
                    )
                    session.add(subscription)
                    session.commit()
                    session.refresh(subscription)
                    logger.info(f"✅ Created push subscription for user {user_id}, endpoint: {subscription_data.endpoint[:50]}...")
                    return subscription
                    
        except Exception as e:
            logger.error(f"Error saving push subscription: {e}")
            return None
    
    def get_user_subscriptions(self, user_id: str) -> List[PushSubscription]:
        """
        Get all active subscriptions for a user
        
        Args:
            user_id: User ID
            
        Returns:
            List of active PushSubscription objects
        """
        try:
            with Session(engine) as session:
                statement = select(PushSubscription).where(
                    PushSubscription.user_id == user_id,
                    PushSubscription.is_active == True
                )
                subscriptions = session.exec(statement).all()
                return list(subscriptions)
        except Exception as e:
            logger.error(f"Error getting user subscriptions: {e}")
            return []
    
    def remove_subscription(self, endpoint: str) -> bool:
        """
        Remove/deactivate a subscription by endpoint
        
        Args:
            endpoint: Push service endpoint URL
            
        Returns:
            True if successful, False otherwise
        """
        try:
            with Session(engine) as session:
                statement = select(PushSubscription).where(
                    PushSubscription.endpoint == endpoint
                )
                subscription = session.exec(statement).first()
                
                if subscription:
                    subscription.is_active = False
                    session.add(subscription)
                    session.commit()
                    logger.info(f"Deactivated push subscription: {endpoint}")
                    return True
                return False
                
        except Exception as e:
            logger.error(f"Error removing subscription: {e}")
            return False
    
    def send_notification(self, user_id: str, title: str, body: str, 
                         data: Optional[dict] = None) -> int:
        """
        Send push notification to all active subscriptions of a user
        
        Args:
            user_id: User ID to send notification to
            title: Notification title
            body: Notification body text
            data: Additional data to include (e.g., chatId, url)
            
        Returns:
            Number of successfully sent notifications
        """
        if not self.vapid_private_key or not self.vapid_public_key:
            logger.warning("Cannot send push: VAPID keys not configured")
            return 0
        
        subscriptions = self.get_user_subscriptions(user_id)
        if not subscriptions:
            logger.info(f"📭 No active subscriptions found for user {user_id}")
            return 0
        
        logger.info(f"📨 Sending push to {len(subscriptions)} subscription(s) for user {user_id}")
        
        # Prepare notification payload
        payload = {
            "title": title,
            "body": body,
            "icon": "/templates/static/icon-192.png.svg",
            "badge": "/templates/static/badge-72.png.svg",
            "tag": data.get("tag", "chat-notification") if data else "chat-notification",
            "vibrate": [200, 100, 200],
            "sound": "/templates/static/sounds/notification.mp3",
            "data": data or {}
        }
        
        # Log what data we're sending
        logger.info(f"📦 Push payload data: {payload.get('data')}")
        
        success_count = 0
        failed_endpoints = []
        
        for subscription in subscriptions:
            try:
                subscription_info = {
                    "endpoint": subscription.endpoint,
                    "keys": {
                        "p256dh": subscription.p256dh,
                        "auth": subscription.auth
                    }
                }
                
                webpush(
                    subscription_info=subscription_info,
                    data=json.dumps(payload),
                    vapid_private_key=self.vapid_private_key,
                    vapid_claims=self.vapid_claims
                )
                
                success_count += 1
                logger.info(f"✅ Push notification sent to {subscription.endpoint[:50]}... (user: {user_id})")
                
            except WebPushException as e:
                logger.error(f"Push failed for {subscription.endpoint[:50]}: {e}")
                
                # If subscription is invalid (410 Gone), mark as inactive
                if e.response and e.response.status_code == 410:
                    failed_endpoints.append(subscription.endpoint)
                    
            except Exception as e:
                logger.error(f"Unexpected error sending push: {e}")
        
        # Remove failed subscriptions
        for endpoint in failed_endpoints:
            self.remove_subscription(endpoint)
        
        logger.info(f"Sent {success_count}/{len(subscriptions)} notifications to user {user_id}")
        return success_count
    
    def send_chat_notification(self, user_id: str, sender_name: str, 
                              message_text: str, chat_id: int) -> int:
        """
        Send chat message notification
        
        Args:
            user_id: Recipient user ID
            sender_name: Name of message sender
            message_text: Message content (will be truncated)
            chat_id: Chat ID
            
        Returns:
            Number of successfully sent notifications
        """
        title = f"Новое сообщение от {sender_name}"
        
        # Truncate long messages
        body = message_text if len(message_text) <= 100 else message_text[:97] + "..."
        
        data = {
            "chatId": chat_id,
            "url": "/profile",
            "tag": f"chat-{chat_id}"
        }
        
        return self.send_notification(user_id, title, body, data)


# Global service instance
push_service = PushNotificationService()
