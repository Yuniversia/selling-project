# tests/test_auth_service.py - Тесты для Auth сервиса
# API доступно через nginx: /api/v1/auth/*

import pytest
import httpx
from datetime import datetime
from helpers import assert_status, assert_json_field, TestResult


class TestAuthHealthCheck:
    """Тесты проверки здоровья Auth сервиса"""
    
    @pytest.mark.smoke
    @pytest.mark.critical
    @pytest.mark.auth
    def test_health_check(self, test_config):
        """
        🔍 Проверка: Auth сервис доступен через nginx
        📍 Endpoint: GET /api/v1/auth/me
        ✅ Ожидается: статус 200, 401 или 403 (сервис отвечает)
        """
        try:
            response = httpx.get(
                f"{test_config.BASE_URL}/api/v1/auth/me",
                timeout=test_config.REQUEST_TIMEOUT
            )
            assert_status(response, [200, 401, 403], 
                "Auth сервис должен отвечать (200/401/403)")
        except httpx.ConnectError:
            pytest.skip("Auth сервис недоступен - нет соединения")


class TestAuthRegistration:
    """Тесты регистрации пользователей"""
    
    @pytest.mark.auth
    @pytest.mark.critical
    def test_register_new_user(self, test_config, session_state, test_data_tracker):
        """
        🔍 Проверка: Регистрация нового пользователя
        📍 Endpoint: POST /api/v1/auth/register
        ✅ Ожидается: статус 201 (создан) или 406 (уже существует)
        """
        try:
            timestamp = datetime.now().strftime('%Y%m%d%H%M%S%f')
            # Используем префикс _test_ для идентификации тестовых данных
            user_data = {
                "username": f"{test_config.TEST_PREFIX}user_{timestamp}",
                "email": f"{test_config.TEST_PREFIX}{timestamp}@test.com",
                "password": "TestPass123!"
            }
            
            response = httpx.post(
                f"{test_config.BASE_URL}/api/v1/auth/register",
                json=user_data,
                timeout=test_config.REQUEST_TIMEOUT
            )
            
            assert_status(response, [201, 406], 
                f"Регистрация пользователя {user_data['username']}")
            
            if response.status_code == 201:
                session_state.cookies = dict(response.cookies)
                data = response.json()
                assert_json_field(data, "username", 
                    "Ответ регистрации должен содержать username")
                # Отслеживаем для очистки
                test_data_tracker.track_user(
                    user_id=data.get("id"),
                    username=user_data["username"]
                )
                
        except httpx.ConnectError:
            pytest.skip("Auth сервис недоступен - нет соединения")
    
    @pytest.mark.auth
    def test_register_duplicate_username(self, test_config, test_data_tracker):
        """
        🔍 Проверка: Повторная регистрация с тем же username
        📍 Endpoint: POST /api/v1/auth/register
        ✅ Ожидается: статус 406 (пользователь уже существует)
        """
        try:
            timestamp = datetime.now().strftime('%Y%m%d%H%M%S')
            user_data = {
                "username": f"{test_config.TEST_PREFIX}dup_{timestamp}",
                "email": f"_test_dup1_{timestamp}@test.com",
                "password": "TestPass123!"
            }
            
            # Первая регистрация
            httpx.post(
                f"{test_config.BASE_URL}/api/v1/auth/register",
                json=user_data,
                timeout=test_config.REQUEST_TIMEOUT
            )
            
            # Повторная регистрация с тем же username
            user_data["email"] = f"_test_dup2_{timestamp}@test.com"
            response = httpx.post(
                f"{test_config.BASE_URL}/api/v1/auth/register",
                json=user_data,
                timeout=test_config.REQUEST_TIMEOUT
            )
            
            assert_status(response, [406], 
                f"Повторная регистрация username '{user_data['username']}' должна вернуть 406")
            
            data = response.json()
            assert_json_field(data, "errors", 
                "Ответ ошибки должен содержать поле 'errors'")
            
        except httpx.ConnectError:
            pytest.skip("Auth сервис недоступен - нет соединения")
    
    @pytest.mark.auth
    def test_register_invalid_email(self, test_config):
        """
        🔍 Проверка: Регистрация с невалидным email
        📍 Endpoint: POST /api/v1/auth/register
        ✅ Ожидается: статус 422, 400 или 406 (ошибка валидации)
        """
        try:
            timestamp = datetime.now().strftime('%Y%m%d%H%M%S%f')
            invalid_email = "not-an-email"
            
            response = httpx.post(
                f"{test_config.BASE_URL}/api/v1/auth/register",
                json={
                    "username": f"_test_{timestamp}", 
                    "email": invalid_email,
                    "password": "pass123"
                },
                timeout=test_config.REQUEST_TIMEOUT
            )
            
            assert_status(response, [422, 400, 406], 
                f"Невалидный email '{invalid_email}' должен вернуть ошибку валидации")
            
        except httpx.ConnectError:
            pytest.skip("Auth сервис недоступен - нет соединения")


class TestAuthLogin:
    """Тесты авторизации"""
    
    @pytest.mark.auth
    @pytest.mark.critical
    def test_login_with_valid_credentials(self, test_config, session_state):
        """
        🔍 Проверка: Вход в систему с корректными данными
        📍 Endpoint: POST /api/v1/auth/login
        ✅ Ожидается: статус 200 и cookies авторизации
        """
        try:
            timestamp = datetime.now().strftime('%Y%m%d%H%M%S%f')
            username = f"_test_login_test_{timestamp}"
            password = "LoginPass123!"
            
            # Регистрируем пользователя
            reg_response = httpx.post(
                f"{test_config.BASE_URL}/api/v1/auth/register",
                json={
                    "username": username,
                    "email": f"_test_login_{timestamp}@test.com",
                    "password": password
                },
                timeout=test_config.REQUEST_TIMEOUT
            )
            
            # Входим
            login_response = httpx.post(
                f"{test_config.BASE_URL}/api/v1/auth/login",
                json={
                    "username_or_email": username,
                    "password": password
                },
                timeout=test_config.REQUEST_TIMEOUT
            )
            
            assert_status(login_response, [200], 
                f"Вход пользователя '{username}' с правильным паролем")
            
            session_state.cookies = dict(login_response.cookies)
            
        except httpx.ConnectError:
            pytest.skip("Auth сервис недоступен - нет соединения")
    
    @pytest.mark.auth
    def test_login_with_invalid_password(self, test_config):
        """Вход с неверным паролем"""
        try:
            response = httpx.post(
                f"{test_config.BASE_URL}/api/v1/auth/login",
                json={
                    "username_or_email": "nonexistent_user",
                    "password": "wrong_password"
                },
                timeout=test_config.REQUEST_TIMEOUT
            )
            
            assert response.status_code in [401, 406], f"Expected 401/406, got {response.status_code}"
            
        except httpx.ConnectError:
            pytest.skip("Auth сервис недоступен")
    
    @pytest.mark.auth
    def test_login_with_email(self, test_config):
        """Вход по email вместо username"""
        try:
            timestamp = datetime.now().strftime('%Y%m%d%H%M%S%f')
            email = f"_test_email_login_{timestamp}@test.com"
            password = "EmailPass123!"
            
            # Регистрация
            httpx.post(
                f"{test_config.BASE_URL}/api/v1/auth/register",
                json={
                    "username": f"_test_email_test_{timestamp}",
                    "email": email,
                    "password": password
                },
                timeout=test_config.REQUEST_TIMEOUT
            )
            
            # Вход по email
            response = httpx.post(
                f"{test_config.BASE_URL}/api/v1/auth/login",
                json={
                    "username_or_email": email,
                    "password": password
                },
                timeout=test_config.REQUEST_TIMEOUT
            )
            
            assert response.status_code == 200
            
        except httpx.ConnectError:
            pytest.skip("Auth сервис недоступен")


class TestAuthTokenRefresh:
    """Тесты обновления токенов"""
    
    @pytest.mark.auth
    @pytest.mark.critical
    def test_refresh_token(self, test_config, session_state):
        """Обновление access_token через refresh_token"""
        try:
            # Сначала логинимся
            timestamp = datetime.now().strftime('%Y%m%d%H%M%S%f')
            username = f"_test_refresh_test_{timestamp}"
            password = "RefreshPass123!"
            
            # Регистрация
            httpx.post(
                f"{test_config.BASE_URL}/api/v1/auth/register",
                json={
                    "username": username,
                    "email": f"_test_refresh_{timestamp}@test.com",
                    "password": password
                },
                timeout=test_config.REQUEST_TIMEOUT
            )
            
            # Логин
            login_response = httpx.post(
                f"{test_config.BASE_URL}/api/v1/auth/login",
                json={
                    "username_or_email": username,
                    "password": password
                },
                timeout=test_config.REQUEST_TIMEOUT
            )
            
            cookies = dict(login_response.cookies)
            
            # Запрос на обновление токена
            refresh_response = httpx.get(
                f"{test_config.BASE_URL}/api/v1/auth/refresh",
                cookies=cookies,
                timeout=test_config.REQUEST_TIMEOUT
            )
            
            assert refresh_response.status_code == 200, f"Refresh failed: {refresh_response.text}"
            
        except httpx.ConnectError:
            pytest.skip("Auth сервис недоступен")
    
    @pytest.mark.auth
    def test_refresh_without_token(self, test_config):
        """Обновление токена без refresh_token должно вернуть ошибку"""
        try:
            response = httpx.get(
                f"{test_config.BASE_URL}/api/v1/auth/refresh",
                timeout=test_config.REQUEST_TIMEOUT
            )
            
            assert response.status_code == 401
            
        except httpx.ConnectError:
            pytest.skip("Auth сервис недоступен")


class TestAuthProfile:
    """Тесты получения и обновления профиля"""
    
    @pytest.mark.auth
    @pytest.mark.critical
    def test_get_current_user_profile(self, test_config):
        """Получение профиля текущего пользователя (/auth/me)"""
        try:
            # Регистрация и логин
            timestamp = datetime.now().strftime('%Y%m%d%H%M%S%f')
            username = f"_test_profile_test_{timestamp}"
            
            reg_response = httpx.post(
                f"{test_config.BASE_URL}/api/v1/auth/register",
                json={
                    "username": username,
                    "email": f"_test_profile_{timestamp}@test.com",
                    "password": "ProfilePass123!"
                },
                timeout=test_config.REQUEST_TIMEOUT
            )
            
            cookies = dict(reg_response.cookies)
            
            # Получение профиля
            me_response = httpx.get(
                f"{test_config.BASE_URL}/api/v1/auth/me",
                cookies=cookies,
                timeout=test_config.REQUEST_TIMEOUT
            )
            
            assert me_response.status_code == 200
            data = me_response.json()
            assert "username" in data
            assert data["username"] == username
            
        except httpx.ConnectError:
            pytest.skip("Auth сервис недоступен")
    
    @pytest.mark.auth
    def test_get_profile_without_auth(self, test_config):
        """Получение профиля без авторизации должно вернуть ошибку"""
        try:
            response = httpx.get(
                f"{test_config.BASE_URL}/api/v1/auth/me",
                timeout=test_config.REQUEST_TIMEOUT
            )
            
            assert response.status_code == 401
            
        except httpx.ConnectError:
            pytest.skip("Auth сервис недоступен")
    
    @pytest.mark.auth
    def test_update_profile(self, test_config):
        """Обновление профиля пользователя"""
        try:
            # Регистрация
            timestamp = datetime.now().strftime('%Y%m%d%H%M%S%f')
            
            reg_response = httpx.post(
                f"{test_config.BASE_URL}/api/v1/auth/register",
                json={
                    "username": f"_test_update_test_{timestamp}",
                    "email": f"_test_update_{timestamp}@test.com",
                    "password": "UpdatePass123!"
                },
                timeout=test_config.REQUEST_TIMEOUT
            )
            
            cookies = dict(reg_response.cookies)
            
            # Обновление профиля
            update_response = httpx.put(
                f"{test_config.BASE_URL}/api/v1/auth/me",
                json={
                    "name": "Test Name",
                    "surname": "Test Surname"
                },
                cookies=cookies,
                timeout=test_config.REQUEST_TIMEOUT
            )
            
            assert update_response.status_code == 200
            data = update_response.json()
            assert data.get("name") == "Test Name"
            
        except httpx.ConnectError:
            pytest.skip("Auth сервис недоступен")
    
    @pytest.mark.auth
    def test_get_user_by_id(self, test_config):
        """Получение информации о пользователе по ID"""
        try:
            # Регистрация
            timestamp = datetime.now().strftime('%Y%m%d%H%M%S%f')
            
            reg_response = httpx.post(
                f"{test_config.BASE_URL}/api/v1/auth/register",
                json={
                    "username": f"_test_userid_test_{timestamp}",
                    "email": f"_test_userid_{timestamp}@test.com",
                    "password": "UserIdPass123!"
                },
                timeout=test_config.REQUEST_TIMEOUT
            )
            
            cookies = dict(reg_response.cookies)
            
            # Получаем свой профиль чтобы узнать ID
            me_response = httpx.get(
                f"{test_config.BASE_URL}/api/v1/auth/me",
                cookies=cookies,
                timeout=test_config.REQUEST_TIMEOUT
            )
            
            if me_response.status_code == 200:
                user_id = me_response.json().get("id")
                
                if user_id:
                    # Получаем пользователя по ID
                    user_response = httpx.get(
                        f"{test_config.BASE_URL}/api/v1/auth/user",
                        params={"id": user_id},
                        timeout=test_config.REQUEST_TIMEOUT
                    )
                    
                    assert user_response.status_code == 200
                    
        except httpx.ConnectError:
            pytest.skip("Auth сервис недоступен")


class TestAuthLogout:
    """Тесты выхода из системы"""
    
    @pytest.mark.auth
    def test_logout(self, test_config):
        """Выход из системы"""
        try:
            # Регистрация
            timestamp = datetime.now().strftime('%Y%m%d%H%M%S%f')
            
            reg_response = httpx.post(
                f"{test_config.BASE_URL}/api/v1/auth/register",
                json={
                    "username": f"_test_logout_test_{timestamp}",
                    "email": f"_test_logout_{timestamp}@test.com",
                    "password": "LogoutPass123!"
                },
                timeout=test_config.REQUEST_TIMEOUT,
                follow_redirects=False
            )
            
            cookies = dict(reg_response.cookies)
            
            # Выход
            logout_response = httpx.post(
                f"{test_config.BASE_URL}/api/v1/auth/logout",
                cookies=cookies,
                timeout=test_config.REQUEST_TIMEOUT,
                follow_redirects=False
            )
            
            # Может быть редирект или 200
            assert logout_response.status_code in [200, 302]
            
        except httpx.ConnectError:
            pytest.skip("Auth сервис недоступен")

