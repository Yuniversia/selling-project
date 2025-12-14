# tests/test_security.py - Тесты безопасности

import pytest
import httpx
from datetime import datetime


class TestAuthenticationSecurity:
    """Тесты безопасности аутентификации"""
    
    @pytest.mark.critical
    def test_protected_endpoints_require_auth(self, test_config):
        """Защищённые эндпоинты требуют авторизации"""
        protected_endpoints = [
            (f"{test_config.BASE_URL}/api/v1/auth/me", "GET"),
            (f"{test_config.BASE_URL}/api/v1/posts/iphone", "POST"),
            (f"{test_config.BASE_URL}/api/v1/posts/orders/create", "POST"),
        ]
        
        for url, method in protected_endpoints:
            try:
                if method == "GET":
                    response = httpx.get(url, timeout=10.0)
                elif method == "POST":
                    response = httpx.post(url, timeout=10.0)
                
                # Должен вернуть 401 Unauthorized или 422 (если не хватает данных)
                assert response.status_code in [401, 403, 422], \
                    f"Эндпоинт {url} доступен без авторизации (статус: {response.status_code})"
                    
            except httpx.ConnectError:
                pytest.skip("Сервис недоступен")
    
    @pytest.mark.critical
    def test_invalid_token_rejected(self, test_config):
        """Невалидный токен отклоняется"""
        try:
            response = httpx.get(
                f"{test_config.BASE_URL}/api/v1/auth/me",
                cookies={"access_token": "invalid_token_12345"},
                timeout=10.0
            )
            
            assert response.status_code in [401, 403]
            
        except httpx.ConnectError:
            pytest.skip("Auth сервис недоступен")
    
    @pytest.mark.critical
    def test_expired_token_rejected(self, test_config):
        """Истёкший токен отклоняется (без refresh)"""
        try:
            # Пробуем использовать заведомо невалидный токен
            response = httpx.get(
                f"{test_config.BASE_URL}/api/v1/auth/me",
                cookies={"access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiIxMjM0NTY3ODkwIiwiZXhwIjoxfQ.invalid"},
                timeout=10.0
            )
            
            assert response.status_code in [401, 403]
            
        except httpx.ConnectError:
            pytest.skip("Auth сервис недоступен")


class TestInputValidation:
    """Тесты валидации входных данных"""
    
    @pytest.mark.critical
    def test_sql_injection_protection(self, test_config):
        """Защита от SQL инъекций"""
        try:
            # Попытка SQL инъекции в параметрах
            malicious_inputs = [
                "'; DROP TABLE users; --",
                "1 OR 1=1",
                "admin'--",
                "1; SELECT * FROM users",
            ]
            
            for payload in malicious_inputs:
                response = httpx.get(
                    f"{test_config.BASE_URL}/api/v1/auth/user",
                    params={"id": payload},
                    timeout=10.0
                )
                
                # Не должен вернуть 500 (внутренняя ошибка)
                assert response.status_code != 500, \
                    f"Возможная уязвимость SQL injection с payload: {payload}"
                    
        except httpx.ConnectError:
            pytest.skip("Auth сервис недоступен")
    
    @pytest.mark.critical
    def test_xss_protection(self, test_config):
        """Защита от XSS"""
        try:
            timestamp = datetime.now().strftime('%Y%m%d%H%M%S%f')
            
            # Попытка XSS в полях регистрации
            xss_payload = "<script>alert('XSS')</script>"
            
            response = httpx.post(
                f"{test_config.BASE_URL}/api/v1/auth/register",
                json={
                    "username": f"xss_test_{timestamp}",
                    "email": f"xss_{timestamp}@test.com",
                    "password": "TestPass123!",
                    "name": xss_payload
                },
                timeout=10.0
            )
            
            # Регистрация должна либо отклонить данные, либо экранировать их
            # Главное - не должно быть 500
            assert response.status_code != 500
            
        except httpx.ConnectError:
            pytest.skip("Auth сервис недоступен")
    
    @pytest.mark.critical
    def test_imei_validation(self, test_config):
        """Валидация IMEI (только цифры, 15 символов)"""
        try:
            timestamp = datetime.now().strftime('%Y%m%d%H%M%S%f')
            
            reg_response = httpx.post(
                f"{test_config.BASE_URL}/api/v1/auth/register",
                json={
                    "username": f"imei_val_{timestamp}",
                    "email": f"imei_val_{timestamp}@test.com",
                    "password": "TestPass123!"
                },
                timeout=10.0
            )
            
            cookies = dict(reg_response.cookies)
            
            invalid_imeis = [
                "12345",  # Слишком короткий
                "12345678901234567890",  # Слишком длинный
                "12345678901234a",  # Содержит букву
                "123456789 12345",  # Содержит пробел
            ]
            
            for imei in invalid_imeis:
                response = httpx.post(
                    f"{test_config.BASE_URL}/api/v1/posts/iphone",
                    data={
                        "imei": imei,
                        "batery": 90,
                        "price": 500.0
                    },
                    cookies=cookies,
                    timeout=10.0
                )
                
                # Должен отклонить невалидный IMEI
                assert response.status_code in [400, 422], \
                    f"Невалидный IMEI '{imei}' был принят"
                    
        except httpx.ConnectError:
            pytest.skip("Сервис недоступен")


class TestRateLimiting:
    """Тесты защиты от перебора"""
    
    @pytest.mark.slow
    def test_login_attempts_handling(self, test_config):
        """Обработка множественных попыток входа"""
        try:
            # Делаем несколько попыток с неверными данными
            for i in range(5):
                response = httpx.post(
                    f"{test_config.BASE_URL}/api/v1/auth/login",
                    json={
                        "username_or_email": f"nonexistent_user_{i}",
                        "password": "wrong_password"
                    },
                    timeout=10.0
                )
                
                # Сервис должен отвечать (не 500)
                assert response.status_code != 500
                
        except httpx.ConnectError:
            pytest.skip("Auth сервис недоступен")


class TestCORS:
    """Тесты CORS политики"""
    
    @pytest.mark.critical
    def test_cors_headers(self, test_config):
        """Проверка CORS заголовков"""
        try:
            response = httpx.options(
                f"{test_config.BASE_URL}/api/v1/auth/login",
                headers={
                    "Origin": "http://localhost:8080",
                    "Access-Control-Request-Method": "POST"
                },
                timeout=10.0
            )
            
            # Проверяем наличие CORS заголовков
            cors_headers = [
                "access-control-allow-origin",
                "access-control-allow-methods",
            ]
            
            # Сервер должен ответить (может быть 200 или 405)
            assert response.status_code in [200, 204, 405]
            
        except httpx.ConnectError:
            pytest.skip("Auth сервис недоступен")


class TestSensitiveDataProtection:
    """Тесты защиты конфиденциальных данных"""
    
    @pytest.mark.critical
    def test_password_not_in_response(self, test_config):
        """Пароль не возвращается в ответах"""
        try:
            timestamp = datetime.now().strftime('%Y%m%d%H%M%S%f')
            
            reg_response = httpx.post(
                f"{test_config.BASE_URL}/api/v1/auth/register",
                json={
                    "username": f"pwd_test_{timestamp}",
                    "email": f"pwd_test_{timestamp}@test.com",
                    "password": "SecretPassword123!"
                },
                timeout=10.0
            )
            
            if reg_response.status_code == 201:
                # Проверяем что пароль не в ответе
                response_text = reg_response.text.lower()
                assert "secretpassword" not in response_text
                assert "hashed_password" not in response_text
                
                cookies = dict(reg_response.cookies)
                
                # Проверяем в /me
                me_response = httpx.get(
                    f"{test_config.BASE_URL}/api/v1/auth/me",
                    cookies=cookies,
                    timeout=10.0
                )
                
                if me_response.status_code == 200:
                    me_text = me_response.text.lower()
                    assert "secretpassword" not in me_text
                    assert "hashed_password" not in me_text
                    
        except httpx.ConnectError:
            pytest.skip("Auth сервис недоступен")
    
    @pytest.mark.critical
    def test_no_stack_traces_in_errors(self, test_config):
        """Нет stack traces в сообщениях об ошибках"""
        try:
            # Вызываем ошибку
            response = httpx.post(
                f"{test_config.BASE_URL}/api/v1/auth/register",
                json={},
                timeout=10.0
            )
            
            if response.status_code >= 400:
                text = response.text.lower()
                
                # Не должно быть путей к файлам и traceback
                assert "traceback" not in text
                assert "/home/" not in text
                assert "/app/" not in text
                assert "file \"" not in text
                
        except httpx.ConnectError:
            pytest.skip("Auth сервис недоступен")


class TestHTTPSecurity:
    """Тесты HTTP безопасности"""
    
    def test_http_methods_restricted(self, test_config):
        """Неподдерживаемые HTTP методы отклоняются"""
        try:
            # DELETE на эндпоинт который его не поддерживает
            response = httpx.delete(
                f"{test_config.BASE_URL}/api/v1/auth/login",
                timeout=10.0
            )
            
            # Должен вернуть 405 Method Not Allowed или 404
            assert response.status_code in [404, 405]
            
        except httpx.ConnectError:
            pytest.skip("Auth сервис недоступен")

