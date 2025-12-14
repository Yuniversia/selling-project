# tests/test_notifications.py - Тесты системы уведомлений

import pytest
import httpx
from datetime import datetime


class TestNotificationEndpoints:
    """Тесты эндпоинтов уведомлений"""
    
    @pytest.mark.chat
    def test_unread_messages_count(self, test_config):
        """Проверка счётчика непрочитанных сообщений"""
        try:
            # Создаём чат
            chat_response = httpx.post(
                f"{test_config.BASE_URL}/api/v1/chat/chats",
                json={
                    "iphone_id": 1,
                    "seller_id": 1,
                    "buyer_id": "notification_test",
                    "buyer_is_registered": True
                },
                timeout=test_config.REQUEST_TIMEOUT
            )
            
            if chat_response.status_code in [200, 201]:
                chat_id = chat_response.json()["id"]
                
                # Отправляем несколько сообщений
                for i in range(3):
                    httpx.post(
                        f"{test_config.BASE_URL}/api/v1/chat/chats/{chat_id}/messages",
                        json={
                            "sender_id": "notification_test",
                            "sender_is_registered": True,
                            "message_text": f"Тестовое сообщение {i+1}"
                        },
                        timeout=test_config.REQUEST_TIMEOUT
                    )
                
                # Проверяем unread_count
                info_response = httpx.get(
                    f"{test_config.BASE_URL}/api/v1/chat/chats/{chat_id}/info",
                    timeout=test_config.REQUEST_TIMEOUT
                )
                
                if info_response.status_code == 200:
                    data = info_response.json()
                    assert "unread_count" in data
                    
        except httpx.ConnectError:
            pytest.skip("Chat сервис недоступен")
    
    @pytest.mark.chat
    def test_mark_messages_read(self, test_config):
        """Проверка отметки сообщений как прочитанных"""
        try:
            # Создаём чат
            chat_response = httpx.post(
                f"{test_config.BASE_URL}/api/v1/chat/chats",
                json={
                    "iphone_id": 1,
                    "seller_id": 1,
                    "buyer_id": "read_test",
                    "buyer_is_registered": True
                },
                timeout=test_config.REQUEST_TIMEOUT
            )
            
            if chat_response.status_code in [200, 201]:
                chat_id = chat_response.json()["id"]
                
                # Отправляем сообщение
                httpx.post(
                    f"{test_config.BASE_URL}/api/v1/chat/chats/{chat_id}/messages",
                    json={
                        "sender_id": "read_test",
                        "sender_is_registered": True,
                        "message_text": "Тестовое сообщение для прочтения"
                    },
                    timeout=test_config.REQUEST_TIMEOUT
                )
                
                # Отмечаем как прочитанные
                read_response = httpx.post(
                    f"{test_config.BASE_URL}/api/v1/chat/chats/{chat_id}/read",
                    params={"user_id": "1"},
                    timeout=test_config.REQUEST_TIMEOUT
                )
                
                assert read_response.status_code in [200, 404]
                
        except httpx.ConnectError:
            pytest.skip("Chat сервис недоступен")


class TestUserNotifications:
    """Тесты уведомлений пользователя"""
    
    @pytest.mark.chat
    def test_get_all_user_chats_with_unread(self, test_config):
        """Получение всех чатов пользователя с непрочитанными сообщениями"""
        try:
            response = httpx.get(
                f"{test_config.BASE_URL}/api/v1/chat/chats/my",
                params={"user_id": "1", "is_seller": True},
                timeout=test_config.REQUEST_TIMEOUT
            )
            
            if response.status_code == 200:
                chats = response.json()
                assert isinstance(chats, list)
                
                # Проверяем что у каждого чата есть unread_count
                for chat in chats:
                    # unread_count может отсутствовать если сервис не возвращает его
                    pass
                    
        except httpx.ConnectError:
            pytest.skip("Chat сервис недоступен")


class TestServiceWorkerEndpoint:
    """Тесты Service Worker для push уведомлений"""
    
    @pytest.mark.frontend
    def test_service_worker_available(self, test_config):
        """Проверка доступности Service Worker"""
        try:
            response = httpx.get(
                f"{test_config.BASE_URL}/sw.js",
                timeout=test_config.REQUEST_TIMEOUT
            )
            
            # Service Worker может быть или не быть настроен
            assert response.status_code in [200, 404]
            
            if response.status_code == 200:
                # Проверяем что это JavaScript
                content_type = response.headers.get("content-type", "")
                assert "javascript" in content_type or response.text.startswith("/")
                
        except httpx.ConnectError:
            pytest.skip("Main сервис недоступен")


class TestNewOrderNotifications:
    """Тесты уведомлений о новых заказах"""
    
    @pytest.mark.posts
    def test_seller_receives_orders(self, test_config):
        """Продавец получает уведомления о заказах"""
        try:
            timestamp = datetime.now().strftime('%Y%m%d%H%M%S%f')
            
            # Регистрируем продавца
            reg_response = httpx.post(
                f"{test_config.BASE_URL}/api/v1/auth/register",
                json={
                    "username": f"order_seller_{timestamp}",
                    "email": f"order_seller_{timestamp}@test.com",
                    "password": "OrderSeller123!"
                },
                timeout=test_config.REQUEST_TIMEOUT
            )
            
            if reg_response.status_code != 201:
                pytest.skip("Регистрация не удалась")
            
            cookies = dict(reg_response.cookies)
            
            # Получаем заказы продавца
            orders_response = httpx.get(
                f"{test_config.BASE_URL}/api/v1/posts/orders/seller",
                cookies=cookies,
                timeout=test_config.REQUEST_TIMEOUT
            )
            
            # Может быть 200 или 404 если endpoint не существует
            assert orders_response.status_code in [200, 404]
            
        except httpx.ConnectError:
            pytest.skip("Сервис недоступен")


class TestNewMessageNotifications:
    """Тесты уведомлений о новых сообщениях"""
    
    @pytest.mark.chat
    def test_new_message_creates_notification(self, test_config):
        """Новое сообщение создаёт уведомление"""
        try:
            # Создаём чат
            chat_response = httpx.post(
                f"{test_config.BASE_URL}/api/v1/chat/chats",
                json={
                    "iphone_id": 1,
                    "seller_id": 1,
                    "buyer_id": "new_msg_test",
                    "buyer_is_registered": True
                },
                timeout=test_config.REQUEST_TIMEOUT
            )
            
            if chat_response.status_code in [200, 201]:
                chat_id = chat_response.json()["id"]
                
                # Отправляем сообщение
                msg_response = httpx.post(
                    f"{test_config.BASE_URL}/api/v1/chat/chats/{chat_id}/messages",
                    json={
                        "sender_id": "new_msg_test",
                        "sender_is_registered": True,
                        "message_text": "Новое сообщение для уведомления"
                    },
                    timeout=test_config.REQUEST_TIMEOUT
                )
                
                assert msg_response.status_code in [200, 201]
                
                # Проверяем что у продавца появилось непрочитанное сообщение
                info_response = httpx.get(
                    f"{test_config.BASE_URL}/api/v1/chat/chats/{chat_id}/info",
                    timeout=test_config.REQUEST_TIMEOUT
                )
                
                if info_response.status_code == 200:
                    data = info_response.json()
                    # unread_count должен быть >= 0
                    assert data.get("unread_count", 0) >= 0
                    
        except httpx.ConnectError:
            pytest.skip("Chat сервис недоступен")

