# tests/conftest.py - Общая конфигурация и fixtures для тестов

import pytest
import os
import sys
from typing import Generator
import httpx
from datetime import datetime

# Добавляем пути к модулям проекта
sys.path.insert(0, os.path.dirname(__file__))  # Путь к tests/ для импорта helpers
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'auth'))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'posts'))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'chat'))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'main'))


# ==================== КОНФИГУРАЦИЯ ТЕСТОВ ====================

class TestConfig:
    """Конфигурация для тестов"""
    
    # Base URL - всё идёт через nginx прокси на порт 8080
    # В production все сервисы доступны через nginx:
    #   - Auth:  /api/v1/auth/*  -> auth-service:8000
    #   - Posts: /api/v1/*       -> posts-service:3000  
    #   - Chat:  /api/chat/*     -> chat-service:4000
    #   - Main:  /*              -> main-service:8080
    
    # Все запросы идут через nginx на порту 8080
    BASE_URL = os.getenv("TEST_BASE_URL", "http://localhost:8080")
    
    # API пути через nginx:
    # - Auth:  /api/v1/auth/*  -> auth-service
    # - Posts: /api/v1/posts/* -> posts-service  
    # - Chat:  /api/v1/chat/*  -> chat-service
    # - Main:  /*              -> main-service
    
    # Тестовые данные пользователя
    TEST_USERNAME = f"test_user_{datetime.now().strftime('%Y%m%d%H%M%S')}"
    TEST_EMAIL = f"test_{datetime.now().strftime('%Y%m%d%H%M%S')}@test.com"
    TEST_PASSWORD = "TestPass123!"
    
    # Таймаут для HTTP запросов
    REQUEST_TIMEOUT = 30.0
    
    # Флаг для пропуска тестов, требующих запущенных сервисов
    SKIP_INTEGRATION = os.getenv("SKIP_INTEGRATION_TESTS", "false").lower() == "true"


@pytest.fixture(scope="session")
def test_config():
    """Возвращает конфигурацию тестов"""
    return TestConfig()


@pytest.fixture(scope="session")
def http_client() -> Generator[httpx.Client, None, None]:
    """Синхронный HTTP клиент для тестов"""
    client = httpx.Client(timeout=TestConfig.REQUEST_TIMEOUT)
    yield client
    client.close()


@pytest.fixture(scope="session")
async def async_http_client() -> Generator[httpx.AsyncClient, None, None]:
    """Асинхронный HTTP клиент для тестов"""
    async with httpx.AsyncClient(timeout=TestConfig.REQUEST_TIMEOUT) as client:
        yield client


@pytest.fixture(scope="session")
def auth_client(http_client: httpx.Client, test_config: TestConfig) -> httpx.Client:
    """HTTP клиент с настроенным base_url для Auth сервиса (через nginx)"""
    http_client.base_url = test_config.BASE_URL
    return http_client


@pytest.fixture(scope="session")
def posts_client(test_config: TestConfig) -> Generator[httpx.Client, None, None]:
    """HTTP клиент с настроенным base_url для Posts сервиса (через nginx)"""
    client = httpx.Client(
        base_url=test_config.BASE_URL,
        timeout=TestConfig.REQUEST_TIMEOUT
    )
    yield client
    client.close()


@pytest.fixture(scope="session")
def chat_client(test_config: TestConfig) -> Generator[httpx.Client, None, None]:
    """HTTP клиент с настроенным base_url для Chat сервиса (через nginx)"""
    client = httpx.Client(
        base_url=test_config.BASE_URL,
        timeout=TestConfig.REQUEST_TIMEOUT
    )
    yield client
    client.close()


@pytest.fixture(scope="session")
def main_client(test_config: TestConfig) -> Generator[httpx.Client, None, None]:
    """HTTP клиент с настроенным base_url для Main (Frontend) сервиса (через nginx)"""
    client = httpx.Client(
        base_url=test_config.BASE_URL,
        timeout=TestConfig.REQUEST_TIMEOUT
    )
    yield client
    client.close()


# ==================== HELPER FUNCTIONS ====================

def check_service_available(url: str) -> bool:
    """Проверяет доступность сервиса по /health эндпоинту"""
    try:
        response = httpx.get(f"{url}/health", timeout=5.0)
        return response.status_code == 200
    except Exception:
        return False


@pytest.fixture(scope="session", autouse=True)
def check_services_availability(test_config: TestConfig):
    """
    Проверяет доступность всех сервисов перед запуском тестов.
    Все сервисы работают через nginx прокси на одном порту.
    """
    # Эндпоинты для проверки через nginx
    health_endpoints = {
        "Nginx/Main": f"{test_config.BASE_URL}/health",
        "Auth API": f"{test_config.BASE_URL}/api/v1/auth/me",  # Вернёт 401, но значит работает
        "Posts API": f"{test_config.BASE_URL}/api/v1/posts/iphone/list",
        "Chat API": f"{test_config.BASE_URL}/api/v1/chat/chats/my?user_id=1&is_seller=false",
    }
    
    available_services = {}
    unavailable_services = []
    
    print("\n" + "=" * 60)
    print("🔍 ПРОВЕРКА ДОСТУПНОСТИ СЕРВИСОВ (через nginx)")
    print(f"   Base URL: {test_config.BASE_URL}")
    print("=" * 60)
    
    for name, url in health_endpoints.items():
        try:
            response = httpx.get(url, timeout=10.0)
            # Считаем сервис доступным если он отвечает (даже с 401/404)
            is_available = response.status_code < 500
            available_services[name] = is_available
            
            if is_available:
                print(f"  ✅ {name}: OK (status: {response.status_code})")
            else:
                print(f"  ❌ {name}: ERROR (status: {response.status_code})")
                unavailable_services.append(name)
        except Exception as e:
            print(f"  ❌ {name}: НЕДОСТУПЕН ({str(e)[:50]})")
            available_services[name] = False
            unavailable_services.append(name)
    
    print("=" * 60)
    
    if unavailable_services:
        print(f"\n⚠️  ВНИМАНИЕ: {len(unavailable_services)} сервис(ов) недоступны!")
        print("   Проверьте что контейнеры запущены: docker ps\n")
    else:
        print("\n✅ Все сервисы доступны через nginx. Тесты готовы к запуску.\n")
    
    return available_services


# ==================== MARKERS ====================

def pytest_configure(config):
    """Регистрация кастомных маркеров pytest"""
    config.addinivalue_line(
        "markers", "auth: тесты для Auth сервиса"
    )
    config.addinivalue_line(
        "markers", "posts: тесты для Posts сервиса"
    )
    config.addinivalue_line(
        "markers", "chat: тесты для Chat сервиса"
    )
    config.addinivalue_line(
        "markers", "frontend: тесты для Frontend/Main сервиса"
    )
    config.addinivalue_line(
        "markers", "integration: интеграционные тесты"
    )
    config.addinivalue_line(
        "markers", "smoke: smoke тесты для быстрой проверки"
    )
    config.addinivalue_line(
        "markers", "critical: критические тесты, обязательные перед деплоем"
    )


# ==================== TEST SESSION STATE ====================

class TestSessionState:
    """Хранит состояние тестовой сессии (токены, созданные объекты и т.д.)"""
    access_token: str = None
    refresh_token: str = None
    test_user_id: int = None
    test_post_id: int = None
    test_chat_id: int = None
    cookies: dict = {}


@pytest.fixture(scope="session")
def session_state():
    """Возвращает объект для хранения состояния между тестами"""
    return TestSessionState()

