# tests/conftest.py - Общая конфигурация и fixtures для тестов

import pytest
import os
import sys
from typing import Generator, List, Dict, Any
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

# Префикс для тестовых данных - легко найти и удалить
TEST_DATA_PREFIX = "_test_"

# ТЕСТОВЫЙ IMEI - это заглушка которая работает в checker.py
# В checker.py есть хардкод: if imei == 356901450728885 - возвращает моковые данные
TEST_IMEI = "356901450728885"


class TestConfig:
    """Конфигурация для тестов"""
    
    # Base URL - всё идёт через nginx прокси на порт 8080
    BASE_URL = os.getenv("TEST_BASE_URL", "http://localhost:8080")
    
    # Префикс для тестовых данных
    TEST_PREFIX = TEST_DATA_PREFIX
    
    # Тестовый IMEI (для которого есть моковые данные в checker.py)
    TEST_IMEI = TEST_IMEI
    
    # API пути через nginx:
    # - Auth:  /api/v1/auth/*  -> auth-service
    # - Posts: /api/v1/posts/* -> posts-service  
    # - Chat:  /api/v1/chat/*  -> chat-service
    # - Main:  /*              -> main-service
    
    # Тестовые данные пользователя (с префиксом для идентификации)
    TEST_USERNAME = f"{TEST_DATA_PREFIX}user_{datetime.now().strftime('%Y%m%d%H%M%S')}"
    TEST_EMAIL = f"{TEST_DATA_PREFIX}{datetime.now().strftime('%Y%m%d%H%M%S')}@test.com"
    TEST_PASSWORD = "TestPass123!"
    
    # Таймаут для HTTP запросов
    REQUEST_TIMEOUT = 30.0
    
    # Флаг для пропуска тестов, требующих запущенных сервисов
    SKIP_INTEGRATION = os.getenv("SKIP_INTEGRATION_TESTS", "false").lower() == "true"
    
    # Флаг очистки тестовых данных после тестов
    CLEANUP_AFTER_TESTS = os.getenv("TEST_CLEANUP", "true").lower() == "true"


# ==================== СИСТЕМА ОЧИСТКИ ТЕСТОВЫХ ДАННЫХ ====================

class TestDataTracker:
    """
    Отслеживает созданные тестовые данные для последующей очистки.
    Все тестовые данные создаются с префиксом _test_ для легкой идентификации.
    """
    
    def __init__(self):
        self.created_users: List[Dict[str, Any]] = []      # {id, username}
        self.created_posts: List[int] = []                  # [post_id, ...]
        self.created_chats: List[int] = []                  # [chat_id, ...]
        self.created_orders: List[int] = []                 # [order_id, ...]
        self.base_url = TestConfig.BASE_URL
        self._cleanup_enabled = TestConfig.CLEANUP_AFTER_TESTS
    
    def track_user(self, user_id: int = None, username: str = None):
        """Добавляет пользователя в список для очистки"""
        if user_id or username:
            self.created_users.append({"id": user_id, "username": username})
            print(f"   📝 Tracked user: {username or user_id}")
    
    def track_post(self, post_id: int):
        """Добавляет объявление в список для очистки"""
        if post_id and post_id not in self.created_posts:
            self.created_posts.append(post_id)
            print(f"   📝 Tracked post: {post_id}")
    
    def track_chat(self, chat_id: int):
        """Добавляет чат в список для очистки"""
        if chat_id and chat_id not in self.created_chats:
            self.created_chats.append(chat_id)
            print(f"   📝 Tracked chat: {chat_id}")
    
    def track_order(self, order_id: int):
        """Добавляет заказ в список для очистки"""
        if order_id and order_id not in self.created_orders:
            self.created_orders.append(order_id)
            print(f"   📝 Tracked order: {order_id}")
    
    def cleanup_all(self):
        """
        Удаляет все отслеживаемые тестовые данные через API endpoints.
        """
        if not self._cleanup_enabled:
            print("\n⚠️  Очистка отключена (TEST_CLEANUP=false или --no-cleanup)")
            return
        
        print("\n" + "=" * 60)
        print("🧹 ОЧИСТКА ТЕСТОВЫХ ДАННЫХ")
        print("=" * 60)
        
        errors = []
        
        # Вызываем cleanup endpoints для массового удаления
        try:
            # 1. Очистка постов через API
            print("\n  📌 Очистка объявлений...")
            response = httpx.delete(
                f"{self.base_url}/api/v1/posts/test/iphone/cleanup",
                timeout=30.0
            )
            if response.status_code == 200:
                data = response.json()
                print(f"     ✅ Удалено объявлений: {data.get('deleted_count', 0)}")
            else:
                errors.append(f"Posts cleanup: status {response.status_code}")
                print(f"     ❌ Ошибка: {response.status_code}")
        except Exception as e:
            errors.append(f"Posts cleanup: {str(e)[:50]}")
            print(f"     ❌ Ошибка: {str(e)[:50]}")
        
        try:
            # 2. Очистка пользователей через API
            print("\n  👤 Очистка тестовых пользователей...")
            response = httpx.delete(
                f"{self.base_url}/api/v1/auth/test/users/cleanup",
                timeout=30.0
            )
            if response.status_code == 200:
                data = response.json()
                print(f"     ✅ Удалено пользователей: {data.get('deleted_count', 0)}")
            else:
                errors.append(f"Users cleanup: status {response.status_code}")
                print(f"     ❌ Ошибка: {response.status_code}")
        except Exception as e:
            errors.append(f"Users cleanup: {str(e)[:50]}")
            print(f"     ❌ Ошибка: {str(e)[:50]}")
        
        # Результаты
        print("\n" + "-" * 60)
        if errors:
            print(f"  ⚠️  Ошибки при очистке ({len(errors)}):")
            for err in errors:
                print(f"     - {err}")
        else:
            print("  ✅ Очистка завершена успешно!")
        print("=" * 60 + "\n")
        
        # Очищаем списки
        self.created_chats.clear()
        self.created_posts.clear()
        self.created_orders.clear()
        self.created_users.clear()
    
    def get_summary(self) -> str:
        """Возвращает сводку отслеживаемых данных"""
        return (
            f"Отслеживается: {len(self.created_users)} пользователей, "
            f"{len(self.created_posts)} объявлений, "
            f"{len(self.created_chats)} чатов, "
            f"{len(self.created_orders)} заказов"
        )


# Глобальный трекер тестовых данных
_test_data_tracker = TestDataTracker()


@pytest.fixture(scope="session")
def test_data_tracker():
    """Возвращает трекер для отслеживания созданных тестовых данных"""
    return _test_data_tracker


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
    config.addinivalue_line(
        "markers", "imei: тесты для IMEI checker"
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


# ==================== АВТОМАТИЧЕСКАЯ ОЧИСТКА ====================

def pytest_sessionfinish(session, exitstatus):
    """
    Hook pytest - вызывается после завершения всех тестов.
    Выполняет очистку тестовых данных.
    """
    global _test_data_tracker
    if _test_data_tracker:
        summary = _test_data_tracker.get_summary()
        print(f"\n📊 {summary}")
        _test_data_tracker.cleanup_all()


def pytest_addoption(parser):
    """Добавляет опции командной строки для тестов"""
    parser.addoption(
        "--no-cleanup",
        action="store_true",
        default=False,
        help="Не удалять тестовые данные после тестов"
    )
    parser.addoption(
        "--cleanup-only",
        action="store_true",
        default=False,
        help="Только очистить тестовые данные (без запуска тестов)"
    )


@pytest.fixture(scope="session", autouse=True)
def configure_cleanup(request):
    """Настраивает очистку на основе опций командной строки"""
    global _test_data_tracker
    
    if request.config.getoption("--no-cleanup"):
        _test_data_tracker._cleanup_enabled = False
        print("\n⚠️  Очистка тестовых данных ОТКЛЮЧЕНА (--no-cleanup)")
    
    # Если только очистка - выполняем её и пропускаем тесты
    if request.config.getoption("--cleanup-only"):
        print("\n🧹 Режим --cleanup-only: только очистка данных")
        _test_data_tracker._cleanup_enabled = True
        _test_data_tracker.cleanup_all()
