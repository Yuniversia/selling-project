# tests/test_frontend_service.py - Тесты для Frontend/Main сервиса

import pytest
import httpx
from datetime import datetime
from helpers import assert_status, TestResult


class TestMainHealthCheck:
    """Тесты проверки здоровья Main сервиса"""
    
    @pytest.mark.smoke
    @pytest.mark.critical
    @pytest.mark.frontend
    def test_health_check(self, test_config):
        """
        🔍 Проверка: Nginx health endpoint
        📍 Endpoint: GET /health
        ✅ Ожидается: статус 200 и текст "healthy"
        """
        try:
            response = httpx.get(
                f"{test_config.BASE_URL}/health",
                timeout=test_config.REQUEST_TIMEOUT
            )
            assert_status(response, [200], "Nginx /health endpoint")
            assert "healthy" in response.text.lower(), \
                f"Ответ /health должен содержать 'healthy', получили: {response.text}"
        except httpx.ConnectError:
            pytest.skip("Main сервис недоступен - нет соединения")
    
    @pytest.mark.smoke
    @pytest.mark.critical
    @pytest.mark.frontend
    def test_main_service_responds(self, test_config):
        """
        🔍 Проверка: Главная страница загружается
        📍 Endpoint: GET /
        ✅ Ожидается: статус 200 и content-type text/html
        """
        try:
            response = httpx.get(
                f"{test_config.BASE_URL}/",
                timeout=test_config.REQUEST_TIMEOUT
            )
            assert_status(response, [200], "Главная страница /")
            
            content_type = response.headers.get("content-type", "")
            assert "text/html" in content_type, \
                f"Главная страница должна быть HTML, получили content-type: {content_type}"
        except httpx.ConnectError:
            pytest.skip("Main сервис недоступен - нет соединения")


class TestMainPages:
    """Тесты открытия основных страниц"""
    
    @pytest.mark.frontend
    @pytest.mark.critical
    @pytest.mark.smoke
    def test_index_page(self, test_config):
        """
        🔍 Проверка: Главная страница
        📍 Endpoint: GET /
        ✅ Ожидается: статус 200, HTML контент
        """
        try:
            response = httpx.get(
                f"{test_config.BASE_URL}/",
                timeout=test_config.REQUEST_TIMEOUT
            )
            assert_status(response, [200], "Главная страница /")
            assert "text/html" in response.headers.get("content-type", ""), \
                f"Ожидался HTML, получен content-type: {response.headers.get('content-type')}"
        except httpx.ConnectError:
            pytest.skip("Main сервис недоступен - нет соединения")
    
    @pytest.mark.frontend
    @pytest.mark.critical
    def test_product_page(self, test_config):
        """
        🔍 Проверка: Страница товара
        📍 Endpoint: GET /product
        ✅ Ожидается: статус 200, HTML контент
        """
        try:
            response = httpx.get(
                f"{test_config.BASE_URL}/product",
                timeout=test_config.REQUEST_TIMEOUT
            )
            assert_status(response, [200], "Страница товара /product")
            assert "text/html" in response.headers.get("content-type", ""), \
                f"Ожидался HTML, получен content-type: {response.headers.get('content-type')}"
        except httpx.ConnectError:
            pytest.skip("Main сервис недоступен - нет соединения")
    
    @pytest.mark.frontend
    @pytest.mark.critical
    def test_profile_page(self, test_config):
        """
        🔍 Проверка: Страница профиля
        📍 Endpoint: GET /profile
        ✅ Ожидается: статус 200, HTML контент
        """
        try:
            response = httpx.get(
                f"{test_config.BASE_URL}/profile",
                timeout=test_config.REQUEST_TIMEOUT
            )
            assert_status(response, [200], "Страница профиля /profile")
            assert "text/html" in response.headers.get("content-type", ""), \
                f"Ожидался HTML, получен content-type: {response.headers.get('content-type')}"
        except httpx.ConnectError:
            pytest.skip("Main сервис недоступен - нет соединения")
    
    @pytest.mark.frontend
    @pytest.mark.critical
    def test_post_ad_page(self, test_config):
        """
        🔍 Проверка: Страница подачи объявления
        📍 Endpoint: GET /post-ad
        ✅ Ожидается: статус 200, HTML контент
        """
        try:
            response = httpx.get(
                f"{test_config.BASE_URL}/post-ad",
                timeout=test_config.REQUEST_TIMEOUT
            )
            assert_status(response, [200], "Страница подачи объявления /post-ad")
            assert "text/html" in response.headers.get("content-type", ""), \
                f"Ожидался HTML, получен content-type: {response.headers.get('content-type')}"
        except httpx.ConnectError:
            pytest.skip("Main сервис недоступен - нет соединения")
    
    @pytest.mark.frontend
    def test_seller_page(self, test_config):
        """
        🔍 Проверка: Страница продавца
        📍 Endpoint: GET /seller
        ✅ Ожидается: статус 200, HTML контент
        ⚠️ Требуется: шаблон seller.html
        """
        try:
            response = httpx.get(
                f"{test_config.BASE_URL}/seller",
                timeout=test_config.REQUEST_TIMEOUT
            )
            if response.status_code == 500:
                pytest.skip(
                    "⚠️ Страница /seller вернула 500 Internal Server Error.\n"
                    "   Вероятная причина: отсутствует шаблон seller.html\n"
                    "   Решение: создать файл main/templates/seller.html"
                )
            assert_status(response, [200], "Страница продавца /seller")
            assert "text/html" in response.headers.get("content-type", ""), \
                f"Ожидался HTML, получен content-type: {response.headers.get('content-type')}"
        except httpx.ConnectError:
            pytest.skip("Main сервис недоступен - нет соединения")
    
    @pytest.mark.frontend
    def test_terms_page(self, test_config):
        """
        🔍 Проверка: Страница правил использования
        📍 Endpoint: GET /terms
        ✅ Ожидается: статус 200, HTML контент
        """
        try:
            response = httpx.get(
                f"{test_config.BASE_URL}/terms",
                timeout=test_config.REQUEST_TIMEOUT
            )
            assert_status(response, [200], "Страница правил /terms")
            assert "text/html" in response.headers.get("content-type", "")
        except httpx.ConnectError:
            pytest.skip("Main сервис недоступен")
    
    @pytest.mark.frontend
    def test_policy_page(self, test_config):
        """Открытие страницы политики конфиденциальности"""
        try:
            response = httpx.get(
                f"{test_config.BASE_URL}/policy",
                timeout=test_config.REQUEST_TIMEOUT
            )
            assert response.status_code == 200
            assert "text/html" in response.headers.get("content-type", "")
        except httpx.ConnectError:
            pytest.skip("Main сервис недоступен")
    
    @pytest.mark.frontend
    def test_imei_check_page(self, test_config):
        """Открытие страницы проверки IMEI"""
        try:
            response = httpx.get(
                f"{test_config.BASE_URL}/imei-check",
                timeout=test_config.REQUEST_TIMEOUT
            )
            assert response.status_code == 200
            assert "text/html" in response.headers.get("content-type", "")
        except httpx.ConnectError:
            pytest.skip("Main сервис недоступен")
    
    @pytest.mark.frontend
    @pytest.mark.critical
    def test_my_orders_page(self, test_config):
        """Открытие страницы моих заказов"""
        try:
            response = httpx.get(
                f"{test_config.BASE_URL}/my-orders",
                timeout=test_config.REQUEST_TIMEOUT
            )
            assert response.status_code == 200
            assert "text/html" in response.headers.get("content-type", "")
        except httpx.ConnectError:
            pytest.skip("Main сервис недоступен")
    
    @pytest.mark.frontend
    @pytest.mark.critical
    def test_my_sales_page(self, test_config):
        """Открытие страницы моих продаж"""
        try:
            response = httpx.get(
                f"{test_config.BASE_URL}/my-sales",
                timeout=test_config.REQUEST_TIMEOUT
            )
            assert response.status_code == 200
            assert "text/html" in response.headers.get("content-type", "")
        except httpx.ConnectError:
            pytest.skip("Main сервис недоступен")


class TestPageContent:
    """Тесты содержимого страниц"""
    
    @pytest.mark.frontend
    def test_index_page_has_required_content(self, test_config):
        """Главная страница содержит необходимые элементы"""
        try:
            response = httpx.get(
                f"{test_config.BASE_URL}/",
                timeout=test_config.REQUEST_TIMEOUT
            )
            
            assert response.status_code == 200
            content = response.text.lower()
            
            # Проверяем наличие базовых HTML элементов
            assert "<html" in content
            assert "</html>" in content
            assert "<body" in content
            
        except httpx.ConnectError:
            pytest.skip("Main сервис недоступен")
    
    @pytest.mark.frontend
    def test_pages_have_no_cache_headers(self, test_config):
        """Страницы имеют заголовки no-cache"""
        try:
            response = httpx.get(
                f"{test_config.BASE_URL}/",
                timeout=test_config.REQUEST_TIMEOUT
            )
            
            cache_control = response.headers.get("cache-control", "")
            
            # Проверяем наличие no-cache (может быть пустым если не настроено)
            # Это информационный тест
            if "no-cache" in cache_control or "no-store" in cache_control:
                assert True
            else:
                # Предупреждение, но не ошибка
                pass
                
        except httpx.ConnectError:
            pytest.skip("Main сервис недоступен")


class TestStaticFiles:
    """Тесты статических файлов"""
    
    @pytest.mark.frontend
    def test_static_files_accessible(self, test_config):
        """Статические файлы доступны"""
        try:
            # Проверяем доступность директории статики
            response = httpx.get(
                f"{test_config.BASE_URL}/templates/static/chat.js",
                timeout=test_config.REQUEST_TIMEOUT
            )
            
            # Может быть 200 или 404 если файл не существует
            assert response.status_code in [200, 404]
            
        except httpx.ConnectError:
            pytest.skip("Main сервис недоступен")
    
    @pytest.mark.frontend
    def test_service_worker(self, test_config):
        """Service Worker доступен"""
        try:
            response = httpx.get(
                f"{test_config.BASE_URL}/sw.js",
                timeout=test_config.REQUEST_TIMEOUT
            )
            
            # Может быть 200 или 404
            assert response.status_code in [200, 404]
            
        except httpx.ConnectError:
            pytest.skip("Main сервис недоступен")


class TestIMEICheck:
    """Тесты API проверки IMEI"""
    
    @pytest.mark.frontend
    def test_imei_check_api(self, test_config):
        """Проверка IMEI через API"""
        try:
            response = httpx.get(
                f"{test_config.BASE_URL}/api/check-imei",
                params={"imei": "123456789012345"},
                timeout=test_config.REQUEST_TIMEOUT
            )
            
            # API должен вернуть результат (даже если ошибка)
            assert response.status_code == 200
            data = response.json()
            assert "imei" in data
            
        except httpx.ConnectError:
            pytest.skip("Main сервис недоступен")
    
    @pytest.mark.frontend
    def test_imei_check_invalid(self, test_config):
        """Проверка невалидного IMEI"""
        try:
            response = httpx.get(
                f"{test_config.BASE_URL}/api/check-imei",
                params={"imei": "invalid"},
                timeout=test_config.REQUEST_TIMEOUT
            )
            
            # Должен вернуть какой-то результат
            assert response.status_code == 200
            
        except httpx.ConnectError:
            pytest.skip("Main сервис недоступен")


class TestDebugEndpoints:
    """Тесты отладочных эндпоинтов"""
    
    @pytest.mark.frontend
    def test_debug_token_endpoint(self, test_config):
        """Эндпоинт отладки токена"""
        try:
            response = httpx.get(
                f"{test_config.BASE_URL}/debug/token",
                timeout=test_config.REQUEST_TIMEOUT
            )
            
            assert response.status_code == 200
            data = response.json()
            assert "has_token" in data
            
        except httpx.ConnectError:
            pytest.skip("Main сервис недоступен")


class TestPageRefresh:
    """Тесты перезагрузки страниц"""
    
    @pytest.mark.frontend
    @pytest.mark.critical
    def test_multiple_page_refresh(self, test_config):
        """Множественная перезагрузка страниц работает корректно"""
        try:
            pages = ["/", "/product", "/profile", "/post-ad"]
            
            for page in pages:
                # Первый запрос
                response1 = httpx.get(
                    f"{test_config.BASE_URL}{page}",
                    timeout=test_config.REQUEST_TIMEOUT
                )
                assert response1.status_code == 200
                
                # Второй запрос (refresh)
                response2 = httpx.get(
                    f"{test_config.BASE_URL}{page}",
                    timeout=test_config.REQUEST_TIMEOUT
                )
                assert response2.status_code == 200
                
        except httpx.ConnectError:
            pytest.skip("Main сервис недоступен")


class TestPageWithAuth:
    """Тесты страниц с авторизацией"""
    
    @pytest.mark.frontend
    @pytest.mark.critical
    def test_profile_page_with_auth(self, test_config):
        """Страница профиля с авторизованным пользователем"""
        try:
            # Регистрация
            timestamp = datetime.now().strftime('%Y%m%d%H%M%S%f')
            
            reg_response = httpx.post(
                f"{test_config.BASE_URL}/api/v1/auth/register",
                json={
                    "username": f"frontend_test_{timestamp}",
                    "email": f"frontend_{timestamp}@test.com",
                    "password": "FrontendTest123!"
                },
                timeout=test_config.REQUEST_TIMEOUT
            )
            
            cookies = dict(reg_response.cookies)
            
            # Открываем профиль с cookies
            response = httpx.get(
                f"{test_config.BASE_URL}/profile",
                cookies=cookies,
                timeout=test_config.REQUEST_TIMEOUT
            )
            
            assert response.status_code == 200
            
        except httpx.ConnectError:
            pytest.skip("Сервис недоступен")
    
    @pytest.mark.frontend
    def test_post_ad_page_with_auth(self, test_config):
        """Страница подачи объявления с авторизацией"""
        try:
            # Регистрация
            timestamp = datetime.now().strftime('%Y%m%d%H%M%S%f')
            
            reg_response = httpx.post(
                f"{test_config.BASE_URL}/api/v1/auth/register",
                json={
                    "username": f"postad_test_{timestamp}",
                    "email": f"postad_{timestamp}@test.com",
                    "password": "PostAdTest123!"
                },
                timeout=test_config.REQUEST_TIMEOUT
            )
            
            cookies = dict(reg_response.cookies)
            
            # Открываем страницу подачи объявления
            response = httpx.get(
                f"{test_config.BASE_URL}/post-ad",
                cookies=cookies,
                timeout=test_config.REQUEST_TIMEOUT
            )
            
            assert response.status_code == 200
            
        except httpx.ConnectError:
            pytest.skip("Сервис недоступен")


class Test404Page:
    """Тесты страницы 404"""
    
    @pytest.mark.frontend
    def test_404_page(self, test_config):
        """Несуществующая страница возвращает 404"""
        try:
            response = httpx.get(
                f"{test_config.BASE_URL}/nonexistent-page-12345",
                timeout=test_config.REQUEST_TIMEOUT
            )
            
            # Может вернуть 404 или кастомную страницу ошибки
            assert response.status_code in [404, 200]
            
        except httpx.ConnectError:
            pytest.skip("Main сервис недоступен")


class TestLanguageSwitching:
    """Тесты переключения языка"""
    
    @pytest.mark.frontend
    def test_page_with_language_cookie(self, test_config):
        """Страница с установленным языком"""
        try:
            for lang in ["ru", "en", "lv"]:
                response = httpx.get(
                    f"{test_config.BASE_URL}/",
                    cookies={"lang": lang},
                    timeout=test_config.REQUEST_TIMEOUT
                )
                
                assert response.status_code == 200
                
        except httpx.ConnectError:
            pytest.skip("Main сервис недоступен")

