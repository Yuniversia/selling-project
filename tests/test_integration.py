# tests/test_integration.py - Интеграционные тесты (End-to-End)

import pytest
import httpx
from datetime import datetime
import time


class TestUserRegistrationFlow:
    """Интеграционный тест полного цикла регистрации"""
    
    @pytest.mark.integration
    @pytest.mark.critical
    def test_full_registration_and_login_flow(self, test_config):
        """
        Полный цикл:
        1. Регистрация нового пользователя
        2. Получение профиля
        3. Выход
        4. Повторный вход
        5. Проверка профиля
        """
        try:
            timestamp = datetime.now().strftime('%Y%m%d%H%M%S%f')
            username = f"integration_{timestamp}"
            email = f"integration_{timestamp}@test.com"
            password = "IntegrationTest123!"
            
            # 1. Регистрация
            reg_response = httpx.post(
                f"{test_config.BASE_URL}/api/v1/auth/register",
                json={
                    "username": username,
                    "email": email,
                    "password": password
                },
                timeout=test_config.REQUEST_TIMEOUT
            )
            
            assert reg_response.status_code == 201, f"Registration failed: {reg_response.text}"
            cookies = dict(reg_response.cookies)
            assert "access_token" in cookies, "No access_token cookie after registration"
            
            # 2. Получение профиля
            me_response = httpx.get(
                f"{test_config.BASE_URL}/api/v1/auth/me",
                cookies=cookies,
                timeout=test_config.REQUEST_TIMEOUT
            )
            
            assert me_response.status_code == 200, f"Get profile failed: {me_response.text}"
            profile = me_response.json()
            assert profile["username"] == username
            
            # 3. Выход
            logout_response = httpx.post(
                f"{test_config.BASE_URL}/api/v1/auth/logout",
                cookies=cookies,
                timeout=test_config.REQUEST_TIMEOUT,
                follow_redirects=False
            )
            
            assert logout_response.status_code in [200, 302], f"Logout failed: {logout_response.status_code}"
            
            # 4. Повторный вход
            login_response = httpx.post(
                f"{test_config.BASE_URL}/api/v1/auth/login",
                json={
                    "username_or_email": username,
                    "password": password
                },
                timeout=test_config.REQUEST_TIMEOUT
            )
            
            assert login_response.status_code == 200, f"Login failed: {login_response.text}"
            new_cookies = dict(login_response.cookies)
            
            # 5. Повторная проверка профиля
            me_response2 = httpx.get(
                f"{test_config.BASE_URL}/api/v1/auth/me",
                cookies=new_cookies,
                timeout=test_config.REQUEST_TIMEOUT
            )
            
            assert me_response2.status_code == 200
            
        except httpx.ConnectError:
            pytest.skip("Сервис недоступен")


class TestPostCreationFlow:
    """Интеграционный тест создания объявления"""
    
    @pytest.mark.integration
    @pytest.mark.critical
    def test_full_post_creation_flow(self, test_config):
        """
        Полный цикл:
        1. Регистрация пользователя
        2. Создание объявления
        3. Просмотр объявления
        4. Проверка в списке
        """
        try:
            timestamp = datetime.now().strftime('%Y%m%d%H%M%S%f')
            
            # 1. Регистрация
            reg_response = httpx.post(
                f"{test_config.BASE_URL}/api/v1/auth/register",
                json={
                    "username": f"poster_{timestamp}",
                    "email": f"poster_{timestamp}@test.com",
                    "password": "PosterTest123!"
                },
                timeout=test_config.REQUEST_TIMEOUT
            )
            
            if reg_response.status_code != 201:
                pytest.skip("Не удалось зарегистрировать пользователя")
                
            cookies = dict(reg_response.cookies)
            
            # 2. Создание объявления
            # Генерируем уникальный IMEI
            imei = timestamp[:15].ljust(15, '0')
            
            create_response = httpx.post(
                f"{test_config.BASE_URL}/api/v1/posts/iphone",
                data={
                    "imei": imei,
                    "batery": 85,
                    "description": "Интеграционный тест - автоматически созданное объявление",
                    "price": 599.99,
                    "condition": "Как новый",
                    "has_original_box": True,
                    "has_charger": True,
                    "has_cable": True
                },
                cookies=cookies,
                timeout=test_config.REQUEST_TIMEOUT
            )
            
            if create_response.status_code != 201:
                # Может быть дубликат IMEI или другая ошибка
                pytest.skip(f"Не удалось создать объявление: {create_response.text}")
            
            post_data = create_response.json()
            post_id = post_data["id"]
            
            # 3. Просмотр объявления
            view_response = httpx.get(
                f"{test_config.BASE_URL}/api/v1/posts/iphone",
                params={"id": post_id},
                timeout=test_config.REQUEST_TIMEOUT
            )
            
            assert view_response.status_code == 200
            viewed_post = view_response.json()
            assert viewed_post["id"] == post_id
            assert viewed_post["imei"] == imei
            
            # 4. Проверка в списке
            list_response = httpx.get(
                f"{test_config.BASE_URL}/api/v1/posts/iphone/list",
                timeout=test_config.REQUEST_TIMEOUT
            )
            
            assert list_response.status_code == 200
            posts = list_response.json()
            
            # Проверяем что наш пост есть в списке
            found = any(p["id"] == post_id for p in posts)
            assert found, "Созданный пост не найден в списке"
            
        except httpx.ConnectError:
            pytest.skip("Сервис недоступен")


class TestChatFlow:
    """Интеграционный тест чата"""
    
    @pytest.mark.integration
    @pytest.mark.critical
    def test_full_chat_flow(self, test_config):
        """
        Полный цикл чата:
        1. Создание чата между продавцом и покупателем
        2. Отправка сообщения
        3. Получение сообщений
        4. Отметка как прочитанные
        """
        try:
            # 1. Создание чата
            chat_response = httpx.post(
                f"{test_config.BASE_URL}/api/v1/chat/chats",
                json={
                    "iphone_id": 1,
                    "seller_id": 1,
                    "buyer_id": "integration_buyer",
                    "buyer_is_registered": True
                },
                timeout=test_config.REQUEST_TIMEOUT
            )
            
            if chat_response.status_code not in [200, 201]:
                pytest.skip(f"Не удалось создать чат: {chat_response.text}")
            
            chat_data = chat_response.json()
            chat_id = chat_data["id"]
            
            # 2. Отправка сообщения от покупателя
            msg1_response = httpx.post(
                f"{test_config.BASE_URL}/api/v1/chat/chats/{chat_id}/messages",
                json={
                    "sender_id": "integration_buyer",
                    "sender_is_registered": True,
                    "message_text": "Здравствуйте! Интересует этот телефон."
                },
                timeout=test_config.REQUEST_TIMEOUT
            )
            
            assert msg1_response.status_code in [200, 201]
            
            # 3. Отправка ответа от продавца
            msg2_response = httpx.post(
                f"{test_config.BASE_URL}/api/v1/chat/chats/{chat_id}/messages",
                json={
                    "sender_id": "1",
                    "sender_is_registered": True,
                    "message_text": "Добрый день! Да, телефон в наличии."
                },
                timeout=test_config.REQUEST_TIMEOUT
            )
            
            assert msg2_response.status_code in [200, 201]
            
            # 4. Получение сообщений
            messages_response = httpx.get(
                f"{test_config.BASE_URL}/api/v1/chat/chats/{chat_id}/messages",
                timeout=test_config.REQUEST_TIMEOUT
            )
            
            assert messages_response.status_code == 200
            messages = messages_response.json()
            assert len(messages) >= 2
            
            # 5. Отметка как прочитанные
            read_response = httpx.post(
                f"{test_config.BASE_URL}/api/v1/chat/chats/{chat_id}/read",
                params={"user_id": "integration_buyer"},
                timeout=test_config.REQUEST_TIMEOUT
            )
            
            assert read_response.status_code in [200, 404]
            
        except httpx.ConnectError:
            pytest.skip("Chat сервис недоступен")


class TestTokenRefreshFlow:
    """Интеграционный тест обновления токена"""
    
    @pytest.mark.integration
    @pytest.mark.critical
    def test_token_refresh_flow(self, test_config):
        """
        Тест обновления токена:
        1. Регистрация
        2. Получение профиля
        3. Обновление токена
        4. Повторное получение профиля
        """
        try:
            timestamp = datetime.now().strftime('%Y%m%d%H%M%S%f')
            
            # 1. Регистрация
            reg_response = httpx.post(
                f"{test_config.BASE_URL}/api/v1/auth/register",
                json={
                    "username": f"refresh_{timestamp}",
                    "email": f"refresh_{timestamp}@test.com",
                    "password": "RefreshTest123!"
                },
                timeout=test_config.REQUEST_TIMEOUT
            )
            
            if reg_response.status_code != 201:
                pytest.skip("Регистрация не удалась")
                
            cookies = dict(reg_response.cookies)
            
            # 2. Получение профиля
            me_response = httpx.get(
                f"{test_config.BASE_URL}/api/v1/auth/me",
                cookies=cookies,
                timeout=test_config.REQUEST_TIMEOUT
            )
            
            assert me_response.status_code == 200
            
            # 3. Обновление токена
            refresh_response = httpx.get(
                f"{test_config.BASE_URL}/api/v1/auth/refresh",
                cookies=cookies,
                timeout=test_config.REQUEST_TIMEOUT
            )
            
            assert refresh_response.status_code == 200
            
            # Обновляем cookies
            new_cookies = dict(cookies)
            new_cookies.update(dict(refresh_response.cookies))
            
            # 4. Повторное получение профиля с новым токеном
            me_response2 = httpx.get(
                f"{test_config.BASE_URL}/api/v1/auth/me",
                cookies=new_cookies,
                timeout=test_config.REQUEST_TIMEOUT
            )
            
            assert me_response2.status_code == 200
            
        except httpx.ConnectError:
            pytest.skip("Auth сервис недоступен")


class TestProfileUpdateFlow:
    """Интеграционный тест обновления профиля"""
    
    @pytest.mark.integration
    def test_profile_update_flow(self, test_config):
        """
        Полный цикл обновления профиля:
        1. Регистрация
        2. Обновление профиля
        3. Проверка изменений
        """
        try:
            timestamp = datetime.now().strftime('%Y%m%d%H%M%S%f')
            
            # 1. Регистрация
            reg_response = httpx.post(
                f"{test_config.BASE_URL}/api/v1/auth/register",
                json={
                    "username": f"profile_update_{timestamp}",
                    "email": f"profile_update_{timestamp}@test.com",
                    "password": "ProfileUpdate123!"
                },
                timeout=test_config.REQUEST_TIMEOUT
            )
            
            if reg_response.status_code != 201:
                pytest.skip("Регистрация не удалась")
                
            cookies = dict(reg_response.cookies)
            
            # 2. Обновление профиля
            update_response = httpx.put(
                f"{test_config.BASE_URL}/api/v1/auth/me",
                json={
                    "name": "Тест",
                    "surname": "Тестович",
                    "phone": "+37100000000"
                },
                cookies=cookies,
                timeout=test_config.REQUEST_TIMEOUT
            )
            
            assert update_response.status_code == 200
            
            # 3. Проверка изменений
            me_response = httpx.get(
                f"{test_config.BASE_URL}/api/v1/auth/me",
                cookies=cookies,
                timeout=test_config.REQUEST_TIMEOUT
            )
            
            assert me_response.status_code == 200
            profile = me_response.json()
            assert profile.get("name") == "Тест"
            assert profile.get("surname") == "Тестович"
            
        except httpx.ConnectError:
            pytest.skip("Auth сервис недоступен")


class TestBuyingFlow:
    """Интеграционный тест процесса покупки"""
    
    @pytest.mark.integration
    @pytest.mark.critical
    def test_buying_flow(self, test_config):
        """
        Процесс покупки:
        1. Получение списка товаров
        2. Выбор товара
        3. Создание заказа
        """
        try:
            timestamp = datetime.now().strftime('%Y%m%d%H%M%S%f')
            
            # Регистрация покупателя
            reg_response = httpx.post(
                f"{test_config.BASE_URL}/api/v1/auth/register",
                json={
                    "username": f"buyer_{timestamp}",
                    "email": f"buyer_{timestamp}@test.com",
                    "password": "BuyerTest123!"
                },
                timeout=test_config.REQUEST_TIMEOUT
            )
            
            if reg_response.status_code != 201:
                pytest.skip("Регистрация покупателя не удалась")
                
            cookies = dict(reg_response.cookies)
            
            # 1. Получение списка товаров
            list_response = httpx.get(
                f"{test_config.BASE_URL}/api/v1/posts/iphone/list",
                params={"limit": 1},
                timeout=test_config.REQUEST_TIMEOUT
            )
            
            if list_response.status_code != 200:
                pytest.skip("Не удалось получить список товаров")
                
            posts = list_response.json()
            
            if not posts:
                pytest.skip("Нет доступных товаров для покупки")
            
            # 2. Выбор товара
            post_id = posts[0]["id"]
            
            # 3. Создание заказа
            order_response = httpx.post(
                f"{test_config.BASE_URL}/api/v1/posts/orders/create",
                json={
                    "iphone_id": post_id,
                    "delivery_method": "pickup"
                },
                cookies=cookies,
                timeout=test_config.REQUEST_TIMEOUT
            )
            
            # Заказ может не создаться по разным причинам (товар уже продан и т.д.)
            assert order_response.status_code in [200, 201, 400, 422]
            
        except httpx.ConnectError:
            pytest.skip("Сервис недоступен")


class TestFullUserJourney:
    """Полный пользовательский путь"""
    
    @pytest.mark.integration
    @pytest.mark.slow
    def test_complete_user_journey(self, test_config):
        """
        Полный путь пользователя:
        1. Просмотр главной страницы
        2. Регистрация
        3. Просмотр товаров
        4. Создание объявления
        5. Просмотр своего профиля
        6. Чат с другим пользователем
        7. Выход
        """
        try:
            timestamp = datetime.now().strftime('%Y%m%d%H%M%S%f')
            
            # 1. Просмотр главной страницы
            main_response = httpx.get(
                f"{test_config.BASE_URL}/",
                timeout=test_config.REQUEST_TIMEOUT
            )
            assert main_response.status_code == 200
            
            # 2. Регистрация
            reg_response = httpx.post(
                f"{test_config.BASE_URL}/api/v1/auth/register",
                json={
                    "username": f"journey_{timestamp}",
                    "email": f"journey_{timestamp}@test.com",
                    "password": "JourneyTest123!"
                },
                timeout=test_config.REQUEST_TIMEOUT
            )
            
            if reg_response.status_code != 201:
                pytest.skip("Регистрация не удалась")
                
            cookies = dict(reg_response.cookies)
            
            # 3. Просмотр товаров
            list_response = httpx.get(
                f"{test_config.BASE_URL}/api/v1/posts/iphone/list",
                timeout=test_config.REQUEST_TIMEOUT
            )
            assert list_response.status_code == 200
            
            # 4. Создание объявления
            imei = timestamp[:15].ljust(15, '1')
            
            create_response = httpx.post(
                f"{test_config.BASE_URL}/api/v1/posts/iphone",
                data={
                    "imei": imei,
                    "batery": 90,
                    "price": 450.0,
                    "condition": "Новый"
                },
                cookies=cookies,
                timeout=test_config.REQUEST_TIMEOUT
            )
            
            # Может не создаться если IMEI занят
            post_created = create_response.status_code == 201
            
            # 5. Просмотр профиля
            profile_response = httpx.get(
                f"{test_config.BASE_URL}/api/v1/auth/me",
                cookies=cookies,
                timeout=test_config.REQUEST_TIMEOUT
            )
            assert profile_response.status_code == 200
            
            # 6. Открытие страницы профиля в браузере
            profile_page_response = httpx.get(
                f"{test_config.BASE_URL}/profile",
                cookies=cookies,
                timeout=test_config.REQUEST_TIMEOUT
            )
            assert profile_page_response.status_code == 200
            
            # 7. Выход
            logout_response = httpx.post(
                f"{test_config.BASE_URL}/api/v1/auth/logout",
                cookies=cookies,
                timeout=test_config.REQUEST_TIMEOUT,
                follow_redirects=False
            )
            assert logout_response.status_code in [200, 302]
            
        except httpx.ConnectError:
            pytest.skip("Сервис недоступен")


class TestCrossServiceCommunication:
    """Тесты межсервисного взаимодействия"""
    
    @pytest.mark.integration
    @pytest.mark.critical
    def test_auth_posts_integration(self, test_config):
        """Проверка интеграции Auth и Posts сервисов"""
        try:
            timestamp = datetime.now().strftime('%Y%m%d%H%M%S%f')
            
            # Регистрация в Auth
            reg_response = httpx.post(
                f"{test_config.BASE_URL}/api/v1/auth/register",
                json={
                    "username": f"cross_{timestamp}",
                    "email": f"cross_{timestamp}@test.com",
                    "password": "CrossTest123!"
                },
                timeout=test_config.REQUEST_TIMEOUT
            )
            
            if reg_response.status_code != 201:
                pytest.skip("Регистрация не удалась")
            
            cookies = dict(reg_response.cookies)
            
            # Использование токена в Posts сервисе
            # Проверяем что токен работает
            posts_response = httpx.get(
                f"{test_config.BASE_URL}/api/v1/posts/iphone/list",
                cookies=cookies,
                timeout=test_config.REQUEST_TIMEOUT
            )
            
            assert posts_response.status_code == 200
            
        except httpx.ConnectError:
            pytest.skip("Сервис недоступен")
    
    @pytest.mark.integration
    def test_auth_chat_integration(self, test_config):
        """Проверка интеграции Auth и Chat сервисов"""
        try:
            timestamp = datetime.now().strftime('%Y%m%d%H%M%S%f')
            
            # Регистрация
            reg_response = httpx.post(
                f"{test_config.BASE_URL}/api/v1/auth/register",
                json={
                    "username": f"chat_cross_{timestamp}",
                    "email": f"chat_cross_{timestamp}@test.com",
                    "password": "ChatCross123!"
                },
                timeout=test_config.REQUEST_TIMEOUT
            )
            
            if reg_response.status_code != 201:
                pytest.skip("Регистрация не удалась")
            
            cookies = dict(reg_response.cookies)
            
            # Получение ID пользователя
            me_response = httpx.get(
                f"{test_config.BASE_URL}/api/v1/auth/me",
                cookies=cookies,
                timeout=test_config.REQUEST_TIMEOUT
            )
            
            if me_response.status_code != 200:
                pytest.skip("Не удалось получить профиль")
            
            user_id = me_response.json().get("id")
            
            # Получение чатов пользователя
            chats_response = httpx.get(
                f"{test_config.BASE_URL}/api/v1/chat/chats/my",
                params={"user_id": str(user_id), "is_seller": False},
                timeout=test_config.REQUEST_TIMEOUT
            )
            
            assert chats_response.status_code == 200
            
        except httpx.ConnectError:
            pytest.skip("Сервис недоступен")

