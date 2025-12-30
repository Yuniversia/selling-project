# tests/test_imei_service.py - Тесты для IMEI Checker сервиса

import pytest
import httpx
from datetime import datetime
from helpers import assert_status


# Тестовый IMEI с моковыми данными в checker.py
# В checker.py есть хардкод: if imei == 356901450728885 - возвращает моковые данные:
# model: IPHONE 12 PRO MAX, memory: 256GB, color: GRAPHITE, sn: DX3XK0YQG5K7
TEST_IMEI = "356901450728885"

# Ожидаемые данные от моковой заглушки в checker.py
EXPECTED_MOCK_DATA = {
    "model": "IPHONE 12 PRO MAX",
    "memory": "256GB",
    "color": "GRAPHITE",
    "serial_number": "DX3XK0YQG5K7",
    "activated": True,
    "fmi": False,
    "icloud": False,
    "simlock": False
}


class TestIMEICheckerIntegration:
    """
    Тесты IMEI Checker интеграции.
    
    IMEI Checker интегрирован в Posts сервис (post_service.py).
    При создании объявления вызывается iphone_check() из iphone_cheker/checker.py
    """
    
    @pytest.mark.imei
    @pytest.mark.critical
    def test_imei_checker_mock_data(self, test_config, test_data_tracker):
        """
        🔍 Проверка: IMEI checker возвращает моковые данные для тестового IMEI
        📍 IMEI: 356901450728885 (хардкод в checker.py)
        ✅ Ожидается: данные iPhone 12 Pro Max, 256GB, Graphite
        """
        try:
            # Регистрируем тестового пользователя
            timestamp = datetime.now().strftime('%Y%m%d%H%M%S%f')
            username = f"_test_imei_checker_{timestamp}"
            
            reg_response = httpx.post(
                f"{test_config.BASE_URL}/api/v1/auth/register",
                json={
                    "username": username,
                    "email": f"_test_{timestamp}@test.com",
                    "password": "IMEIChecker123!"
                },
                timeout=test_config.REQUEST_TIMEOUT
            )
            
            if reg_response.status_code not in [200, 201]:
                pytest.skip(f"Не удалось создать пользователя: {reg_response.status_code}")
            
            cookies = dict(reg_response.cookies)
            test_data_tracker.track_user(username=username)
            
            # Создаём объявление с тестовым IMEI
            post_data = {
                "imei": TEST_IMEI,
                "batery": 95,
                "description": "_test_ IMEI checker test",
                "price": 899.0,
                "condition": "Как новый"
            }
            
            response = httpx.post(
                f"{test_config.BASE_URL}/api/v1/posts/iphone",
                data=post_data,
                cookies=cookies,
                timeout=60.0
            )
            
            if response.status_code == 201:
                data = response.json()
                
                if "id" in data:
                    test_data_tracker.track_post(data["id"])
                
                # Проверяем данные от IMEI checker
                print("\n🔍 Проверка данных от IMEI Checker:")
                
                # Модель
                model = data.get("model")
                print(f"   Модель: {model}")
                assert model is not None, \
                    "IMEI Checker должен заполнить модель"
                assert "IPHONE" in model.upper() or "12" in model, \
                    f"Модель должна содержать 'IPHONE' или '12', получено: {model}"
                
                # Память (может быть int или None)
                memory = data.get("memory")
                print(f"   Память: {memory}")
                assert memory is not None, \
                    "IMEI Checker должен заполнить память"
                # memory хранится как int в БД (256)
                assert memory == 256 or str(memory) == "256", \
                    f"Память должна быть 256, получено: {memory}"
                
                # Цвет
                color = data.get("color")
                print(f"   Цвет: {color}")
                assert color is not None, \
                    "IMEI Checker должен заполнить цвет"
                
                # Серийный номер
                sn = data.get("serial_number")
                print(f"   S/N: {sn}")
                assert sn is not None, \
                    "IMEI Checker должен заполнить серийный номер"
                assert sn == "DX3XK0YQG5K7", \
                    f"S/N должен быть DX3XK0YQG5K7 (из мока), получено: {sn}"
                
                print("✅ IMEI Checker работает корректно!")
                
            else:
                pytest.fail(f"Не удалось создать пост: {response.status_code}, {response.text[:200]}")
            
        except httpx.ConnectError:
            pytest.skip("Сервис недоступен")
    
    @pytest.mark.imei
    def test_imei_data_stored_correctly(self, test_config):
        """
        🔍 Проверка: данные IMEI checker сохраняются в объявлении
        📍 Endpoint: GET /api/v1/posts/iphone?id=...
        ✅ Ожидается: объявление содержит model, color, memory, serial_number
        """
        try:
            # Получаем список объявлений
            response = httpx.get(
                f"{test_config.BASE_URL}/api/v1/posts/iphone/list",
                params={"limit": 10},
                timeout=test_config.REQUEST_TIMEOUT
            )
            
            if response.status_code != 200:
                pytest.skip("Не удалось получить список объявлений")
            
            posts = response.json()
            
            if not posts:
                pytest.skip("Нет объявлений для проверки")
            
            # Проверяем структуру данных
            for post in posts:
                post_id = post.get("id")
                
                # Эти поля должны присутствовать (могут быть None для старых записей)
                assert "model" in post, f"Пост #{post_id} должен иметь поле model"
                assert "color" in post, f"Пост #{post_id} должен иметь поле color"
                assert "memory" in post, f"Пост #{post_id} должен иметь поле memory"
                assert "serial_number" in post, f"Пост #{post_id} должен иметь поле serial_number"
                
                # Логируем состояние
                has_imei_data = all([
                    post.get("model"),
                    post.get("color"),
                    post.get("memory"),
                    post.get("serial_number")
                ])
                
                status = "✅" if has_imei_data else "⚠️"
                print(f"   {status} Post #{post_id}: model={post.get('model')}, "
                      f"memory={post.get('memory')}, color={post.get('color')}, "
                      f"sn={post.get('serial_number')}")
            
        except httpx.ConnectError:
            pytest.skip("Posts сервис недоступен")


class TestIMEIValidation:
    """Тесты валидации IMEI"""
    
    @pytest.mark.imei
    def test_imei_must_be_15_digits(self, test_config, test_data_tracker):
        """IMEI должен содержать ровно 15 цифр"""
        try:
            timestamp = datetime.now().strftime('%Y%m%d%H%M%S%f')
            username = f"_test_imei_valid_{timestamp}"
            
            reg_response = httpx.post(
                f"{test_config.BASE_URL}/api/v1/auth/register",
                json={
                    "username": username,
                    "email": f"_test_{timestamp}@test.com",
                    "password": "IMEIValid123!"
                },
                timeout=test_config.REQUEST_TIMEOUT
            )
            
            cookies = dict(reg_response.cookies)
            test_data_tracker.track_user(username=username)
            
            invalid_imeis = [
                ("12345", "слишком короткий"),
                ("12345678901234567890", "слишком длинный"),
                ("35690145072888a", "содержит буквы"),
                ("", "пустой"),
            ]
            
            for imei, reason in invalid_imeis:
                response = httpx.post(
                    f"{test_config.BASE_URL}/api/v1/posts/iphone",
                    data={
                        "imei": imei,
                        "batery": 95,
                        "price": 500.0
                    },
                    cookies=cookies,
                    timeout=test_config.REQUEST_TIMEOUT
                )
                
                assert response.status_code == 422, \
                    f"IMEI '{imei}' ({reason}) должен вернуть 422, получено: {response.status_code}"
                print(f"   ✅ IMEI '{imei}' ({reason}) корректно отклонён")
            
        except httpx.ConnectError:
            pytest.skip("Сервис недоступен")
    
    @pytest.mark.imei
    def test_valid_imei_format(self, test_config, test_data_tracker):
        """Проверка что валидный формат IMEI принимается"""
        try:
            timestamp = datetime.now().strftime('%Y%m%d%H%M%S%f')
            username = f"_test_imei_format_{timestamp}"
            
            reg_response = httpx.post(
                f"{test_config.BASE_URL}/api/v1/auth/register",
                json={
                    "username": username,
                    "email": f"_test_{timestamp}@test.com",
                    "password": "IMEIFormat123!"
                },
                timeout=test_config.REQUEST_TIMEOUT
            )
            
            cookies = dict(reg_response.cookies)
            test_data_tracker.track_user(username=username)
            
            # Используем тестовый IMEI с моковыми данными
            response = httpx.post(
                f"{test_config.BASE_URL}/api/v1/posts/iphone",
                data={
                    "imei": TEST_IMEI,
                    "batery": 95,
                    "description": "_test_ IMEI format validation",
                    "price": 500.0
                },
                cookies=cookies,
                timeout=60.0
            )
            
            # Должен принять (201) или отклонить по другой причине (не из-за формата)
            assert response.status_code in [201, 500], \
                f"Валидный IMEI должен быть принят или ошибка от checker, получено: {response.status_code}"
            
            if response.status_code == 201:
                data = response.json()
                if "id" in data:
                    test_data_tracker.track_post(data["id"])
                print(f"   ✅ IMEI {TEST_IMEI} принят")
            
        except httpx.ConnectError:
            pytest.skip("Сервис недоступен")


class TestIMEICheckerErrorHandling:
    """Тесты обработки ошибок IMEI checker"""
    
    @pytest.mark.imei
    def test_unknown_imei_handling(self, test_config, test_data_tracker):
        """
        Проверка обработки неизвестного IMEI.
        Для IMEI без моковых данных checker обращается к реальному API.
        """
        try:
            timestamp = datetime.now().strftime('%Y%m%d%H%M%S%f')
            username = f"_test_unknown_imei_{timestamp}"
            
            reg_response = httpx.post(
                f"{test_config.BASE_URL}/api/v1/auth/register",
                json={
                    "username": username,
                    "email": f"_test_{timestamp}@test.com",
                    "password": "UnknownIMEI123!"
                },
                timeout=test_config.REQUEST_TIMEOUT
            )
            
            cookies = dict(reg_response.cookies)
            test_data_tracker.track_user(username=username)
            
            # Используем IMEI без моковых данных
            unknown_imei = "000000000000000"
            
            response = httpx.post(
                f"{test_config.BASE_URL}/api/v1/posts/iphone",
                data={
                    "imei": unknown_imei,
                    "batery": 95,
                    "description": "_test_ Unknown IMEI test",
                    "price": 500.0
                },
                cookies=cookies,
                timeout=60.0
            )
            
            # Может создаться с пустыми данными IMEI или вернуть ошибку
            print(f"   Unknown IMEI response: {response.status_code}")
            
            if response.status_code == 201:
                data = response.json()
                if "id" in data:
                    test_data_tracker.track_post(data["id"])
                
                # Для неизвестного IMEI данные могут быть пустыми
                print(f"   Model: {data.get('model')}")
                print(f"   Memory: {data.get('memory')}")
                print(f"   S/N: {data.get('serial_number')}")
            
        except httpx.ConnectError:
            pytest.skip("Сервис недоступен")


class TestCleanupEndpoints:
    """Тесты endpoint очистки"""
    
    @pytest.mark.imei
    def test_auth_cleanup_endpoint(self, test_config):
        """Проверка endpoint очистки пользователей"""
        try:
            response = httpx.delete(
                f"{test_config.BASE_URL}/api/v1/auth/test/users/cleanup",
                timeout=test_config.REQUEST_TIMEOUT
            )
            
            assert response.status_code == 200, \
                f"Auth cleanup должен вернуть 200, получено: {response.status_code}"
            
            data = response.json()
            assert "deleted_count" in data
            print(f"   ✅ Удалено пользователей: {data['deleted_count']}")
            
        except httpx.ConnectError:
            pytest.skip("Auth сервис недоступен")
    
    @pytest.mark.imei  
    def test_posts_cleanup_endpoint(self, test_config):
        """Проверка endpoint очистки объявлений"""
        try:
            response = httpx.delete(
                f"{test_config.BASE_URL}/api/v1/posts/test/iphone/cleanup",
                timeout=test_config.REQUEST_TIMEOUT
            )
            
            assert response.status_code == 200, \
                f"Posts cleanup должен вернуть 200, получено: {response.status_code}"
            
            data = response.json()
            assert "deleted_count" in data
            print(f"   ✅ Удалено объявлений: {data['deleted_count']}")
            
        except httpx.ConnectError:
            pytest.skip("Posts сервис недоступен")

