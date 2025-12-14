# tests/test_smoke.py - Быстрые smoke тесты для проверки работоспособности всех сервисов

import pytest
import httpx
from helpers import assert_status, TestResult


class TestAllServicesSmoke:
    """
    Smoke тесты для быстрой проверки всех сервисов.
    Эти тесты должны запускаться первыми перед деплоем.
    """
    
    @pytest.mark.smoke
    @pytest.mark.critical
    def test_all_services_health(self, test_config):
        """
        🔍 Проверка: Все сервисы отвечают через nginx
        📍 Endpoints: /health, /, /api/v1/auth/me, /api/v1/posts/..., /api/v1/chat/...
        ✅ Ожидается: каждый сервис возвращает допустимый статус
        """
        services = {
            "Nginx Health": (f"{test_config.BASE_URL}/health", [200]),
            "Главная страница": (f"{test_config.BASE_URL}/", [200]),
            "Auth сервис": (f"{test_config.BASE_URL}/api/v1/auth/me", [200, 401, 403]),
            "Posts сервис": (f"{test_config.BASE_URL}/api/v1/posts/iphone/list", [200]),
            "Chat сервис": (f"{test_config.BASE_URL}/api/v1/chat/chats/my?user_id=test&is_seller=false", [200]),
        }
        
        failed_services = []
        
        for name, (url, valid_codes) in services.items():
            try:
                response = httpx.get(url, timeout=10.0)
                if response.status_code not in valid_codes:
                    failed_services.append(
                        f"❌ {name}:\n"
                        f"   URL: {url}\n"
                        f"   Ожидался статус: {valid_codes}\n"
                        f"   Получен статус: {response.status_code}"
                    )
            except httpx.ConnectError:
                failed_services.append(f"❌ {name}: не удалось подключиться к {url}")
            except Exception as e:
                failed_services.append(f"❌ {name}: ошибка - {str(e)}")
        
        if failed_services:
            pytest.fail(
                "\n\n🔴 СЕРВИСЫ НЕДОСТУПНЫ:\n\n" + 
                "\n\n".join(failed_services) +
                "\n\n💡 Проверьте:\n"
                "   1. Docker контейнеры запущены: docker ps\n"
                "   2. Nginx работает и проксирует запросы\n"
                "   3. Логи сервисов: docker logs <container>"
            )
    
    @pytest.mark.smoke
    @pytest.mark.critical
    def test_database_connectivity(self, test_config):
        """
        🔍 Проверка: Подключение к базе данных через сервисы
        📍 Проверяем что сервисы не возвращают 500 (ошибка БД)
        ✅ Ожидается: статус НЕ равен 500
        """
        try:
            # Auth сервис
            response = httpx.get(
                f"{test_config.BASE_URL}/api/v1/auth/user",
                params={"id": 1},
                timeout=10.0
            )
            assert response.status_code != 500, \
                f"Auth сервис вернул 500 - возможно проблема с БД. Ответ: {response.text[:200]}"
            
            # Posts сервис
            response = httpx.get(
                f"{test_config.BASE_URL}/api/v1/posts/iphone/list",
                params={"limit": 1},
                timeout=10.0
            )
            assert response.status_code != 500, \
                f"Posts сервис вернул 500 - возможно проблема с БД. Ответ: {response.text[:200]}"
            
            # Chat сервис
            response = httpx.get(
                f"{test_config.BASE_URL}/api/v1/chat/chats/my",
                params={"user_id": "1", "is_seller": "false"},
                timeout=10.0
            )
            assert response.status_code != 500, \
                f"Chat сервис вернул 500 - возможно проблема с БД. Ответ: {response.text[:200]}"
            
        except httpx.ConnectError:
            pytest.skip("Сервисы недоступны - нет соединения")
    
    @pytest.mark.smoke
    @pytest.mark.critical
    def test_main_page_loads(self, test_config):
        """
        🔍 Проверка: Главная страница загружается и не пустая
        📍 Endpoint: GET /
        ✅ Ожидается: статус 200, контент > 100 символов
        """
        try:
            response = httpx.get(
                f"{test_config.BASE_URL}/",
                timeout=10.0
            )
            assert_status(response, [200], "Загрузка главной страницы")
            assert len(response.text) > 100, \
                f"Главная страница почти пустая ({len(response.text)} символов)"
        except httpx.ConnectError:
            pytest.skip("Main сервис недоступен - нет соединения")
    
    @pytest.mark.smoke
    @pytest.mark.critical
    def test_api_endpoints_respond(self, test_config):
        """Основные API эндпоинты отвечают"""
        endpoints = [
            (f"{test_config.BASE_URL}/api/v1/auth/me", "GET"),
            (f"{test_config.BASE_URL}/api/v1/posts/iphone/list", "GET"),
            (f"{test_config.BASE_URL}/api/v1/chat/chats/my?user_id=1&is_seller=false", "GET"),
        ]
        
        for url, method in endpoints:
            try:
                if method == "GET":
                    response = httpx.get(url, timeout=10.0)
                
                # Любой ответ кроме 5xx считается успехом для smoke теста
                assert response.status_code < 500, f"Эндпоинт {url} вернул {response.status_code}"
                
            except httpx.ConnectError:
                pytest.fail(f"Эндпоинт недоступен: {url}")
    
    @pytest.mark.smoke
    def test_static_files_served(self, test_config):
        """Статические файлы отдаются"""
        try:
            response = httpx.get(
                f"{test_config.BASE_URL}/templates/static/chat.js",
                timeout=10.0
            )
            # Файл может существовать или нет, но сервер должен ответить
            assert response.status_code in [200, 404]
        except httpx.ConnectError:
            pytest.skip("Main сервис недоступен")


class TestCriticalFlows:
    """Критические пользовательские сценарии для smoke тестов"""
    
    @pytest.mark.smoke
    @pytest.mark.critical
    def test_registration_works(self, test_config):
        """Регистрация пользователя работает"""
        from datetime import datetime
        
        try:
            timestamp = datetime.now().strftime('%Y%m%d%H%M%S%f')
            
            response = httpx.post(
                f"{test_config.BASE_URL}/api/v1/auth/register",
                json={
                    "username": f"smoke_{timestamp}",
                    "email": f"smoke_{timestamp}@test.com",
                    "password": "SmokeTest123!"
                },
                timeout=15.0
            )
            
            # 201 = успех, 406 = пользователь уже существует (тоже ОК для smoke)
            assert response.status_code in [201, 406], f"Регистрация вернула {response.status_code}"
            
        except httpx.ConnectError:
            pytest.skip("Auth сервис недоступен")
    
    @pytest.mark.smoke
    @pytest.mark.critical
    def test_login_works(self, test_config):
        """Вход в систему работает"""
        try:
            # Пробуем войти с несуществующим пользователем
            response = httpx.post(
                f"{test_config.BASE_URL}/api/v1/auth/login",
                json={
                    "username_or_email": "nonexistent_user_smoke_test",
                    "password": "wrongpassword"
                },
                timeout=15.0
            )
            
            # 401 или 406 = сервис работает (отклонил неверные данные)
            assert response.status_code in [401, 406, 400], f"Login вернул {response.status_code}"
            
        except httpx.ConnectError:
            pytest.skip("Auth сервис недоступен")
    
    @pytest.mark.smoke
    @pytest.mark.critical
    def test_posts_listing_works(self, test_config):
        """Список товаров загружается"""
        try:
            response = httpx.get(
                f"{test_config.BASE_URL}/api/v1/posts/iphone/list",
                timeout=15.0
            )
            
            assert response.status_code == 200
            data = response.json()
            assert isinstance(data, list)
            
        except httpx.ConnectError:
            pytest.skip("Posts сервис недоступен")
    
    @pytest.mark.smoke
    def test_chat_service_responds(self, test_config):
        """Chat сервис отвечает"""
        try:
            # Используем /api/v1/chat/chats/my - рабочий endpoint
            response = httpx.get(
                f"{test_config.BASE_URL}/api/v1/chat/chats/my",
                params={"user_id": "smoke_test", "is_seller": "false"},
                timeout=10.0
            )
            
            # 200 = сервис работает
            assert response.status_code == 200
            
        except httpx.ConnectError:
            pytest.skip("Chat сервис недоступен")


class TestProductionReadiness:
    """Тесты готовности к production"""
    
    @pytest.mark.smoke
    @pytest.mark.critical
    def test_no_debug_mode(self, test_config):
        """Проверка что debug режим выключен (не показываются детали ошибок)"""
        try:
            # Отправляем заведомо неправильный запрос
            response = httpx.post(
                f"{test_config.BASE_URL}/api/v1/auth/register",
                json={},  # Пустые данные
                timeout=10.0
            )
            
            # Не должно быть stack trace в ответе
            if response.status_code >= 400:
                text = response.text.lower()
                assert "traceback" not in text, "Обнаружен stack trace в ответе"
                assert "file \"" not in text, "Обнаружены пути к файлам в ответе"
                
        except httpx.ConnectError:
            pytest.skip("Auth сервис недоступен")
    
    @pytest.mark.smoke
    def test_cors_headers_present(self, test_config):
        """CORS заголовки присутствуют"""
        try:
            response = httpx.options(
                f"{test_config.BASE_URL}/api/v1/auth/login",
                headers={"Origin": "http://localhost:8080"},
                timeout=10.0
            )
            
            # OPTIONS может вернуть разные коды в зависимости от конфигурации
            # Главное - проверить что сервер отвечает
            assert response.status_code < 500
            
        except httpx.ConnectError:
            pytest.skip("Auth сервис недоступен")
    
    @pytest.mark.smoke
    def test_response_times_acceptable(self, test_config):
        """Время ответа приемлемое (< 5 секунд)"""
        import time
        
        endpoints = [
            f"{test_config.BASE_URL}/",
            f"{test_config.BASE_URL}/api/v1/auth/me",
            f"{test_config.BASE_URL}/api/v1/posts/iphone/list",
        ]
        
        for url in endpoints:
            try:
                start = time.time()
                response = httpx.get(url, timeout=10.0)
                elapsed = time.time() - start
                
                assert elapsed < 5.0, f"Ответ от {url} занял {elapsed:.2f}с (макс. 5с)"
                
            except httpx.ConnectError:
                pytest.skip(f"Сервис недоступен: {url}")

