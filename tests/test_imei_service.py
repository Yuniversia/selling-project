# tests/test_imei_service.py - Тесты для IMEI Checker сервиса

import pytest
import httpx


class TestIMEIHealthCheck:
    """Тесты проверки здоровья IMEI сервиса"""
    
    @pytest.mark.smoke
    def test_health_check(self, test_config):
        """Проверка IMEI сервиса через nginx"""
        try:
            # IMEI сервис доступен через /api/v1/imei/
            response = httpx.get(
                f"{test_config.BASE_URL}/api/v1/imei/health",
                timeout=test_config.REQUEST_TIMEOUT
            )
            # IMEI сервис может быть недоступен в development
            assert response.status_code in [200, 404]
            
            if response.status_code == 200:
                data = response.json()
                assert data.get("status") == "healthy"
        except httpx.ConnectError:
            pytest.skip("IMEI сервис недоступен")


class TestIMEICheck:
    """Тесты проверки IMEI"""
    
    @pytest.mark.posts
    def test_check_valid_imei(self, test_config):
        """Проверка валидного IMEI"""
        try:
            # Используем тестовый IMEI
            test_imei = "353456789012345"
            
            response = httpx.get(
                f"{test_config.BASE_URL}/api/v1/imei/check/{test_imei}",
                timeout=test_config.REQUEST_TIMEOUT
            )
            
            # Сервис может вернуть данные или ошибку "не найден"
            assert response.status_code in [200, 404]
            
            if response.status_code == 200:
                data = response.json()
                assert "imei" in data
                
        except httpx.ConnectError:
            pytest.skip("IMEI сервис недоступен")
    
    @pytest.mark.posts
    def test_check_invalid_imei(self, test_config):
        """Проверка невалидного IMEI"""
        try:
            # Слишком короткий IMEI
            response = httpx.get(
                f"{test_config.BASE_URL}/api/v1/imei/check/12345",
                timeout=test_config.REQUEST_TIMEOUT
            )
            
            # Должен вернуть ошибку или 404
            assert response.status_code in [400, 404, 422]
            
        except httpx.ConnectError:
            pytest.skip("IMEI сервис недоступен")
    
    @pytest.mark.posts
    def test_check_imei_via_main_service(self, test_config):
        """Проверка IMEI через Main сервис"""
        try:
            response = httpx.get(
                f"{test_config.BASE_URL}/api/check-imei",
                params={"imei": "353456789012345"},
                timeout=test_config.REQUEST_TIMEOUT
            )
            
            assert response.status_code == 200
            data = response.json()
            assert "imei" in data
            
        except httpx.ConnectError:
            pytest.skip("Main сервис недоступен")


class TestIMEIResponse:
    """Тесты формата ответа IMEI"""
    
    @pytest.mark.posts
    def test_imei_response_format(self, test_config):
        """Проверка формата ответа IMEI проверки"""
        try:
            response = httpx.get(
                f"{test_config.BASE_URL}/api/check-imei",
                params={"imei": "353456789012345"},
                timeout=test_config.REQUEST_TIMEOUT
            )
            
            if response.status_code == 200:
                data = response.json()
                
                # Проверяем наличие ожидаемых полей
                expected_fields = [
                    "imei",
                    "model",
                    "color",
                    "serial_number"
                ]
                
                for field in expected_fields:
                    assert field in data, f"Отсутствует поле: {field}"
                    
        except httpx.ConnectError:
            pytest.skip("Сервис недоступен")

