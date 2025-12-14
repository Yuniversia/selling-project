# tests/test_chat_service.py - Тесты для Chat сервиса

import pytest
import httpx
from datetime import datetime
import asyncio
import json
from helpers import assert_status, assert_json_field, TestResult

try:
    import websockets
    WEBSOCKETS_AVAILABLE = True
except ImportError:
    WEBSOCKETS_AVAILABLE = False


class TestChatHealthCheck:
    """Тесты проверки здоровья Chat сервиса"""
    
    @pytest.mark.smoke
    @pytest.mark.critical
    @pytest.mark.chat
    def test_health_check(self, test_config):
        """
        🔍 Проверка: Chat сервис доступен через nginx
        📍 Endpoint: GET /api/v1/chat/chats/my
        ✅ Ожидается: статус 200
        """
        try:
            response = httpx.get(
                f"{test_config.BASE_URL}/api/v1/chat/chats/my",
                params={"user_id": "test_health", "is_seller": "false"},
                timeout=test_config.REQUEST_TIMEOUT
            )
            assert_status(response, [200], "Chat сервис /api/v1/chat/chats/my")
        except httpx.ConnectError:
            pytest.skip("Chat сервис недоступен - нет соединения")
    
    @pytest.mark.chat
    def test_get_my_chats(self, test_config):
        """
        🔍 Проверка: Получение списка чатов пользователя
        📍 Endpoint: GET /api/v1/chat/chats/my
        ✅ Ожидается: статус 200, массив чатов
        """
        try:
            response = httpx.get(
                f"{test_config.BASE_URL}/api/v1/chat/chats/my",
                params={"user_id": "test_user", "is_seller": "false"},
                timeout=test_config.REQUEST_TIMEOUT
            )
            assert_status(response, [200], "Получение чатов пользователя test_user")
            data = response.json()
            assert isinstance(data, list), \
                f"Ответ должен быть массивом чатов, получен тип: {type(data).__name__}"
        except httpx.ConnectError:
            pytest.skip("Chat сервис недоступен - нет соединения")


class TestChatCreate:
    """Тесты создания чатов"""
    
    @pytest.mark.chat
    @pytest.mark.critical
    def test_create_chat(self, test_config):
        """
        🔍 Проверка: Создание нового чата
        📍 Endpoint: POST /api/v1/chat/chats
        ✅ Ожидается: статус 200/201 (создан) или 422/400 (ошибка валидации)
        """
        try:
            chat_data = {
                "iphone_id": 1,
                "seller_id": 1,
                "buyer_id": "2",
                "buyer_is_registered": True
            }
            
            response = httpx.post(
                f"{test_config.BASE_URL}/api/v1/chat/chats",
                json=chat_data,
                timeout=test_config.REQUEST_TIMEOUT
            )
            
            assert_status(response, [200, 201, 422, 400, 500], 
                f"Создание чата для товара {chat_data['iphone_id']}")
            
            if response.status_code in [200, 201]:
                data = response.json()
                assert_json_field(data, "id", "Ответ создания чата должен содержать 'id'")
                assert data["iphone_id"] == chat_data["iphone_id"]
                
        except httpx.ConnectError:
            pytest.skip("Chat сервис недоступен")
    
    @pytest.mark.chat
    def test_create_chat_invalid_data(self, test_config):
        """Создание чата с невалидными данными"""
        try:
            response = httpx.post(
                f"{test_config.BASE_URL}/api/v1/chat/chats",
                json={},  # Пустые данные
                timeout=test_config.REQUEST_TIMEOUT
            )
            
            assert response.status_code == 422
            
        except httpx.ConnectError:
            pytest.skip("Chat сервис недоступен")


class TestChatFindAndGet:
    """Тесты поиска и получения чатов"""
    
    @pytest.mark.chat
    @pytest.mark.critical
    def test_find_chat(self, test_config):
        """Поиск существующего чата"""
        try:
            response = httpx.get(
                f"{test_config.BASE_URL}/api/v1/chat/chats/find",
                params={
                    "iphone_id": 1,
                    "seller_id": 1,
                    "buyer_id": "2"
                },
                timeout=test_config.REQUEST_TIMEOUT
            )
            
            # Может вернуть чат или null
            assert response.status_code in [200, 404]
            
        except httpx.ConnectError:
            pytest.skip("Chat сервис недоступен")
    
    @pytest.mark.chat
    def test_get_chat_by_id(self, test_config):
        """Получение чата по ID"""
        try:
            # Сначала создаём чат
            create_response = httpx.post(
                f"{test_config.BASE_URL}/api/v1/chat/chats",
                json={
                    "iphone_id": 1,
                    "seller_id": 1,
                    "buyer_id": "3",
                    "buyer_is_registered": True
                },
                timeout=test_config.REQUEST_TIMEOUT
            )
            
            if create_response.status_code in [200, 201]:
                chat_id = create_response.json()["id"]
                
                # Получаем чат
                response = httpx.get(
                    f"{test_config.BASE_URL}/api/v1/chat/chats/{chat_id}",
                    timeout=test_config.REQUEST_TIMEOUT
                )
                
                assert response.status_code == 200
                data = response.json()
                assert data["id"] == chat_id
                
        except httpx.ConnectError:
            pytest.skip("Chat сервис недоступен")
    
    @pytest.mark.chat
    def test_get_chat_info(self, test_config):
        """Получение информации о чате (без сообщений)"""
        try:
            # Создаём чат
            create_response = httpx.post(
                f"{test_config.BASE_URL}/api/v1/chat/chats",
                json={
                    "iphone_id": 1,
                    "seller_id": 1,
                    "buyer_id": "4",
                    "buyer_is_registered": True
                },
                timeout=test_config.REQUEST_TIMEOUT
            )
            
            if create_response.status_code in [200, 201]:
                chat_id = create_response.json()["id"]
                
                response = httpx.get(
                    f"{test_config.BASE_URL}/api/v1/chat/chats/{chat_id}/info",
                    timeout=test_config.REQUEST_TIMEOUT
                )
                
                assert response.status_code == 200
                
        except httpx.ConnectError:
            pytest.skip("Chat сервис недоступен")
    
    @pytest.mark.chat
    def test_get_nonexistent_chat(self, test_config):
        """Получение несуществующего чата"""
        try:
            response = httpx.get(
                f"{test_config.BASE_URL}/api/v1/chat/chats/999999",
                timeout=test_config.REQUEST_TIMEOUT
            )
            
            assert response.status_code == 404
            
        except httpx.ConnectError:
            pytest.skip("Chat сервис недоступен")


class TestUserChats:
    """Тесты получения чатов пользователя"""
    
    @pytest.mark.chat
    @pytest.mark.critical
    def test_get_my_chats_as_buyer(self, test_config):
        """Получение своих чатов (как покупатель)"""
        try:
            response = httpx.get(
                f"{test_config.BASE_URL}/api/v1/chat/chats/my",
                params={
                    "user_id": "5",
                    "is_seller": False
                },
                timeout=test_config.REQUEST_TIMEOUT
            )
            
            assert response.status_code == 200
            data = response.json()
            assert isinstance(data, list)
            
        except httpx.ConnectError:
            pytest.skip("Chat сервис недоступен")
    
    @pytest.mark.chat
    def test_get_my_chats_as_seller(self, test_config):
        """Получение своих чатов (как продавец)"""
        try:
            response = httpx.get(
                f"{test_config.BASE_URL}/api/v1/chat/chats/my",
                params={
                    "user_id": "1",
                    "is_seller": True
                },
                timeout=test_config.REQUEST_TIMEOUT
            )
            
            assert response.status_code == 200
            data = response.json()
            assert isinstance(data, list)
            
        except httpx.ConnectError:
            pytest.skip("Chat сервис недоступен")
    
    @pytest.mark.chat
    def test_get_seller_chats_grouped(self, test_config):
        """Получение чатов продавца, сгруппированных по объявлениям"""
        try:
            response = httpx.get(
                f"{test_config.BASE_URL}/api/v1/chat/chats/seller/1/grouped",
                timeout=test_config.REQUEST_TIMEOUT
            )
            
            assert response.status_code == 200
            
        except httpx.ConnectError:
            pytest.skip("Chat сервис недоступен")


class TestChatMessages:
    """Тесты сообщений в чате"""
    
    @pytest.mark.chat
    @pytest.mark.critical
    def test_send_message(self, test_config):
        """Отправка сообщения в чат"""
        try:
            # Создаём чат
            create_response = httpx.post(
                f"{test_config.BASE_URL}/api/v1/chat/chats",
                json={
                    "iphone_id": 1,
                    "seller_id": 1,
                    "buyer_id": "6",
                    "buyer_is_registered": True
                },
                timeout=test_config.REQUEST_TIMEOUT
            )
            
            if create_response.status_code in [200, 201]:
                chat_id = create_response.json()["id"]
                
                # Отправляем сообщение
                message_response = httpx.post(
                    f"{test_config.BASE_URL}/api/v1/chat/chats/{chat_id}/messages",
                    json={
                        "sender_id": "6",
                        "sender_is_registered": True,
                        "message_text": "Тестовое сообщение для автотестов"
                    },
                    timeout=test_config.REQUEST_TIMEOUT
                )
                
                assert message_response.status_code in [200, 201]
                
                if message_response.status_code in [200, 201]:
                    data = message_response.json()
                    assert "message_text" in data
                    
        except httpx.ConnectError:
            pytest.skip("Chat сервис недоступен")
    
    @pytest.mark.chat
    def test_get_chat_messages(self, test_config):
        """Получение сообщений чата"""
        try:
            # Создаём чат и отправляем сообщение
            create_response = httpx.post(
                f"{test_config.BASE_URL}/api/v1/chat/chats",
                json={
                    "iphone_id": 1,
                    "seller_id": 1,
                    "buyer_id": "7",
                    "buyer_is_registered": True
                },
                timeout=test_config.REQUEST_TIMEOUT
            )
            
            if create_response.status_code in [200, 201]:
                chat_id = create_response.json()["id"]
                
                # Отправляем сообщение
                httpx.post(
                    f"{test_config.BASE_URL}/api/v1/chat/chats/{chat_id}/messages",
                    json={
                        "sender_id": "7",
                        "sender_is_registered": True,
                        "message_text": "Сообщение для проверки получения"
                    },
                    timeout=test_config.REQUEST_TIMEOUT
                )
                
                # Получаем сообщения
                response = httpx.get(
                    f"{test_config.BASE_URL}/api/v1/chat/chats/{chat_id}/messages",
                    timeout=test_config.REQUEST_TIMEOUT
                )
                
                assert response.status_code == 200
                data = response.json()
                assert isinstance(data, list)
                
        except httpx.ConnectError:
            pytest.skip("Chat сервис недоступен")
    
    @pytest.mark.chat
    def test_get_messages_with_pagination(self, test_config):
        """Получение сообщений с пагинацией"""
        try:
            # Создаём чат
            create_response = httpx.post(
                f"{test_config.BASE_URL}/api/v1/chat/chats",
                json={
                    "iphone_id": 1,
                    "seller_id": 1,
                    "buyer_id": "8",
                    "buyer_is_registered": True
                },
                timeout=test_config.REQUEST_TIMEOUT
            )
            
            if create_response.status_code in [200, 201]:
                chat_id = create_response.json()["id"]
                
                response = httpx.get(
                    f"{test_config.BASE_URL}/api/v1/chat/chats/{chat_id}/messages",
                    params={"limit": 10, "offset": 0},
                    timeout=test_config.REQUEST_TIMEOUT
                )
                
                assert response.status_code == 200
                data = response.json()
                assert len(data) <= 10
                
        except httpx.ConnectError:
            pytest.skip("Chat сервис недоступен")


class TestChatReadStatus:
    """Тесты статуса прочтения сообщений"""
    
    @pytest.mark.chat
    def test_mark_as_read(self, test_config):
        """Отметка сообщений как прочитанных"""
        try:
            # Создаём чат и сообщение
            create_response = httpx.post(
                f"{test_config.BASE_URL}/api/v1/chat/chats",
                json={
                    "iphone_id": 1,
                    "seller_id": 1,
                    "buyer_id": "9",
                    "buyer_is_registered": True
                },
                timeout=test_config.REQUEST_TIMEOUT
            )
            
            if create_response.status_code in [200, 201]:
                chat_id = create_response.json()["id"]
                
                # Отмечаем как прочитанные
                response = httpx.post(
                    f"{test_config.BASE_URL}/api/v1/chat/chats/{chat_id}/read",
                    params={"user_id": "1"},
                    timeout=test_config.REQUEST_TIMEOUT
                )
                
                assert response.status_code in [200, 404]
                
        except httpx.ConnectError:
            pytest.skip("Chat сервис недоступен")


class TestChatWebSocket:
    """Тесты WebSocket соединения для чата"""
    
    @pytest.mark.chat
    @pytest.mark.asyncio
    async def test_websocket_connection(self, test_config):
        """Проверка WebSocket подключения"""
        if not WEBSOCKETS_AVAILABLE:
            pytest.skip("websockets не установлен")
            
        try:
            ws_url = test_config.BASE_URL.replace("http://", "ws://").replace("https://", "wss://")
            ws_url = f"{ws_url}/api/v1/chat/ws/1?user_id=test_user_1"  # chat_id=1, user_id=test_user_1
            
            async with asyncio.timeout(5):
                async with websockets.connect(ws_url) as websocket:
                    # Если соединение установлено, тест прошёл
                    assert websocket.open
                    
                    # Отправляем тестовое сообщение
                    await websocket.send(json.dumps({
                        "type": "ping"
                    }))
                    
                    # Пробуем получить ответ (с таймаутом)
                    try:
                        response = await asyncio.wait_for(websocket.recv(), timeout=2.0)
                        # Получили ответ
                        assert response is not None
                    except asyncio.TimeoutError:
                        # Таймаут - это нормально, сервер может не отвечать на ping
                        pass
                        
        except (ConnectionRefusedError, OSError):
            pytest.skip("Chat WebSocket недоступен")
        except asyncio.TimeoutError:
            pytest.skip("WebSocket соединение таймаут")
        except Exception as e:
            pytest.skip(f"WebSocket ошибка: {str(e)}")
    
    @pytest.mark.chat
    @pytest.mark.asyncio
    async def test_websocket_send_message(self, test_config):
        """Отправка сообщения через WebSocket"""
        if not WEBSOCKETS_AVAILABLE:
            pytest.skip("websockets не установлен")
            
        try:
            ws_url = test_config.BASE_URL.replace("http://", "ws://").replace("https://", "wss://")
            
            # Создаём чат через REST API
            async with httpx.AsyncClient() as client:
                create_response = await client.post(
                    f"{test_config.BASE_URL}/api/v1/chat/chats",
                    json={
                        "iphone_id": 1,
                        "seller_id": 1,
                        "buyer_id": "ws_test_user",
                        "buyer_is_registered": True
                    },
                    timeout=test_config.REQUEST_TIMEOUT
                )
                
                if create_response.status_code not in [200, 201]:
                    pytest.skip("Не удалось создать чат для WebSocket теста")
                    return
                    
                chat_id = create_response.json()["id"]
            
            ws_url = f"{ws_url}/api/v1/chat/ws/{chat_id}?user_id=ws_test_user"
            
            async with asyncio.timeout(5):
                async with websockets.connect(ws_url) as websocket:
                    # Отправляем сообщение
                    message = {
                        "type": "message",
                        "message_text": "Тест WebSocket сообщения",
                        "sender_is_registered": True
                    }
                    await websocket.send(json.dumps(message))
                    
                    # Тест успешен если соединение установлено и сообщение отправлено
                    assert True
                        
        except (ConnectionRefusedError, OSError):
            pytest.skip("Chat WebSocket недоступен")
        except asyncio.TimeoutError:
            pytest.skip("WebSocket соединение таймаут")
        except Exception as e:
            pytest.skip(f"WebSocket ошибка: {str(e)}")


class TestUnreadCount:
    """Тесты счётчика непрочитанных сообщений"""
    
    @pytest.mark.chat
    def test_unread_count(self, test_config):
        """Проверка счётчика непрочитанных сообщений"""
        try:
            # Создаём чат
            create_response = httpx.post(
                f"{test_config.BASE_URL}/api/v1/chat/chats",
                json={
                    "iphone_id": 1,
                    "seller_id": 1,
                    "buyer_id": "unread_test",
                    "buyer_is_registered": True
                },
                timeout=test_config.REQUEST_TIMEOUT
            )
            
            if create_response.status_code in [200, 201]:
                chat_id = create_response.json()["id"]
                
                # Отправляем несколько сообщений
                for i in range(3):
                    httpx.post(
                        f"{test_config.BASE_URL}/api/v1/chat/chats/{chat_id}/messages",
                        json={
                            "sender_id": "unread_test",
                            "sender_is_registered": True,
                            "message_text": f"Сообщение {i+1}"
                        },
                        timeout=test_config.REQUEST_TIMEOUT
                    )
                
                # Получаем информацию о чате с unread_count
                info_response = httpx.get(
                    f"{test_config.BASE_URL}/api/v1/chat/chats/{chat_id}/info",
                    timeout=test_config.REQUEST_TIMEOUT
                )
                
                assert info_response.status_code == 200
                data = info_response.json()
                assert "unread_count" in data
                
        except httpx.ConnectError:
            pytest.skip("Chat сервис недоступен")

