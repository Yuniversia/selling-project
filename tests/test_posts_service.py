# tests/test_posts_service.py - Тесты для Posts сервиса

import pytest
import httpx
from datetime import datetime
from helpers import assert_status, assert_json_field, TestResult

# Тестовый IMEI - для этого значения в checker.py есть моковые данные
TEST_IMEI = "356901450728885"


class TestPostsHealthCheck:
    """Тесты проверки здоровья Posts сервиса"""
    
    @pytest.mark.smoke
    @pytest.mark.critical
    @pytest.mark.posts
    def test_health_check(self, test_config):
        """
        🔍 Проверка: Posts сервис доступен через nginx
        📍 Endpoint: GET /api/v1/posts/iphone/list
        ✅ Ожидается: статус 200
        """
        try:
            response = httpx.get(
                f"{test_config.BASE_URL}/api/v1/posts/iphone/list",
                params={"limit": 1},
                timeout=test_config.REQUEST_TIMEOUT
            )
            assert_status(response, [200], "Posts сервис /api/v1/posts/iphone/list")
        except httpx.ConnectError:
            pytest.skip("Posts сервис недоступен - нет соединения")


class TestPostsList:
    """Тесты получения списка товаров (iPhone)"""
    
    @pytest.mark.posts
    @pytest.mark.critical
    def test_get_posts_list(self, test_config):
        """
        🔍 Проверка: Получение списка iPhone объявлений
        📍 Endpoint: GET /api/v1/posts/iphone/list
        ✅ Ожидается: статус 200, массив в ответе
        """
        try:
            response = httpx.get(
                f"{test_config.BASE_URL}/api/v1/posts/iphone/list",
                timeout=test_config.REQUEST_TIMEOUT
            )
            
            assert_status(response, [200], "Получение списка iPhone")
            data = response.json()
            assert isinstance(data, list), \
                f"Ответ должен быть массивом, получен тип: {type(data).__name__}"
            
        except httpx.ConnectError:
            pytest.skip("Posts сервис недоступен - нет соединения")
    
    @pytest.mark.posts
    def test_get_posts_list_with_pagination(self, test_config):
        """
        🔍 Проверка: Пагинация списка товаров
        📍 Endpoint: GET /api/v1/posts/iphone/list?skip=0&limit=10
        ✅ Ожидается: статус 200, массив ≤10 элементов
        """
        try:
            response = httpx.get(
                f"{test_config.BASE_URL}/api/v1/posts/iphone/list",
                params={"skip": 0, "limit": 10},
                timeout=test_config.REQUEST_TIMEOUT
            )
            
            assert_status(response, [200], "Пагинация списка iPhone (limit=10)")
            data = response.json()
            assert isinstance(data, list), \
                f"Ответ должен быть массивом, получен тип: {type(data).__name__}"
            assert len(data) <= 10, \
                f"С limit=10 должно быть ≤10 элементов, получено: {len(data)}"
            
        except httpx.ConnectError:
            pytest.skip("Posts сервис недоступен - нет соединения")
    
    @pytest.mark.posts
    def test_get_posts_list_with_filters(self, test_config):
        """
        🔍 Проверка: Фильтры списка товаров (модель, цена, батарея)
        📍 Endpoint: GET /api/v1/posts/iphone/list с фильтрами
        ✅ Ожидается: статус 200 для всех фильтров
        """
        try:
            filters_to_test = [
                ({"model": "IPHONE 12 PRO MAX"}, "фильтр по модели iPhone 12 PRO MAX"),
                ({"price_min": 100, "price_max": 1000}, "фильтр по цене 100-1000"),
                ({"batery_min": 80}, "фильтр по батарее ≥80%"),
                ({"memory": "128"}, "фильтр по памяти ≥128GB"),
            ]
            
            for params, description in filters_to_test:
                response = httpx.get(
                    f"{test_config.BASE_URL}/api/v1/posts/iphone/list",
                    params=params,
                    timeout=test_config.REQUEST_TIMEOUT
                )
                assert_status(response, [200], f"Список iPhone с {description}")
            
        except httpx.ConnectError:
            pytest.skip("Posts сервис недоступен - нет соединения")
    
    @pytest.mark.posts
    def test_get_posts_list_with_sorting(self, test_config):
        """Получение списка с сортировкой"""
        try:
            # Сортировка по цене (по возрастанию)
            response = httpx.get(
                f"{test_config.BASE_URL}/api/v1/posts/iphone/list",
                params={"sort_price": "asc"},
                timeout=test_config.REQUEST_TIMEOUT
            )
            assert response.status_code == 200
            
            # Сортировка по дате (новые первыми)
            response = httpx.get(
                f"{test_config.BASE_URL}/api/v1/posts/iphone/list",
                params={"sort_date": "desc"},
                timeout=test_config.REQUEST_TIMEOUT
            )
            assert response.status_code == 200
            
        except httpx.ConnectError:
            pytest.skip("Posts сервис недоступен")


class TestPostSingle:
    """Тесты получения одного товара"""
    
    @pytest.mark.posts
    @pytest.mark.critical
    def test_get_single_post(self, test_config):
        """Получение одного объявления по ID"""
        try:
            # Сначала получаем список
            list_response = httpx.get(
                f"{test_config.BASE_URL}/api/v1/posts/iphone/list",
                params={"limit": 1},
                timeout=test_config.REQUEST_TIMEOUT
            )
            
            if list_response.status_code == 200:
                posts = list_response.json()
                if posts:
                    post_id = posts[0]["id"]
                    
                    # Получаем конкретный пост
                    response = httpx.get(
                        f"{test_config.BASE_URL}/api/v1/posts/iphone",
                        params={"id": post_id},
                        timeout=test_config.REQUEST_TIMEOUT
                    )
                    
                    assert response.status_code == 200
                    data = response.json()
                    assert data["id"] == post_id
                else:
                    pytest.skip("Нет объявлений в базе данных")
            
        except httpx.ConnectError:
            pytest.skip("Posts сервис недоступен")
    
    @pytest.mark.posts
    def test_get_nonexistent_post(self, test_config):
        """Получение несуществующего объявления"""
        try:
            response = httpx.get(
                f"{test_config.BASE_URL}/api/v1/posts/iphone",
                params={"id": 999999},
                timeout=test_config.REQUEST_TIMEOUT
            )
            
            assert response.status_code == 404
            
        except httpx.ConnectError:
            pytest.skip("Posts сервис недоступен")


class TestPostCreate:
    """Тесты создания объявления с полными данными IMEI"""
    
    @pytest.mark.posts
    @pytest.mark.critical
    @pytest.mark.imei
    def test_create_post_with_valid_imei(self, test_config, test_data_tracker):
        """
        🔍 Создание объявления с валидным тестовым IMEI
        📍 IMEI 356901450728885 имеет моковые данные в checker.py
        ✅ Ожидается: пост создан с данными от IMEI checker (модель, цвет, память)
        """
        try:
            # Регистрируем тестового пользователя
            timestamp = datetime.now().strftime('%Y%m%d%H%M%S%f')
            username = f"_test_post_creator_{timestamp}"
            
            reg_response = httpx.post(
                f"{test_config.BASE_URL}/api/v1/auth/register",
                json={
                    "username": username,
                    "email": f"_test_{timestamp}@test.com",
                    "password": "PostCreator123!"
                },
                timeout=test_config.REQUEST_TIMEOUT
            )
            
            if reg_response.status_code not in [200, 201]:
                pytest.skip(f"Не удалось зарегистрировать пользователя: {reg_response.status_code}")
            
            cookies = dict(reg_response.cookies)
            test_data_tracker.track_user(username=username)
            
            # Создаём пост с валидным тестовым IMEI
            post_data = {
                "imei": TEST_IMEI,  # Тестовый IMEI с моковыми данными
                "batery": 95,
                "description": "_test_ Тестовый iPhone для автотестов",
                "price": 799.0,
                "condition": "Как новый",
                "has_original_box": True,
                "has_charger": True,
                "has_cable": True,
                "has_receipt": False,
                "has_warranty": False
            }
            
            response = httpx.post(
                f"{test_config.BASE_URL}/api/v1/posts/iphone",
                data=post_data,
                cookies=cookies,
                timeout=60.0  # Больший таймаут - IMEI checker может быть медленным
            )
            
            # Проверяем успешное создание
            if response.status_code == 201:
                data = response.json()
                
                # Трекаем для очистки
                if "id" in data:
                    test_data_tracker.track_post(data["id"])
                
                # Проверяем что IMEI checker заполнил данные
                assert data.get("imei") == TEST_IMEI, \
                    f"IMEI должен быть {TEST_IMEI}, получено: {data.get('imei')}"
                
                # Проверяем данные от IMEI checker (из моковых данных в checker.py)
                assert data.get("model") is not None, \
                    f"Модель должна быть заполнена IMEI checker. Получено: {data}"
                
                assert data.get("memory") is not None, \
                    f"Память должна быть заполнена IMEI checker. Получено: {data}"
                
                assert data.get("color") is not None, \
                    f"Цвет должен быть заполнен IMEI checker. Получено: {data}"
                
                assert data.get("serial_number") is not None, \
                    f"Серийный номер должен быть заполнен IMEI checker. Получено: {data}"
                
                print(f"✅ Пост создан с данными IMEI checker:")
                print(f"   Модель: {data.get('model')}")
                print(f"   Память: {data.get('memory')} GB")
                print(f"   Цвет: {data.get('color')}")
                print(f"   S/N: {data.get('serial_number')}")
                
            elif response.status_code == 422:
                pytest.fail(f"Ошибка валидации: {response.json()}")
            else:
                pytest.fail(f"Неожиданный статус: {response.status_code}, {response.text[:200]}")
            
        except httpx.ConnectError:
            pytest.skip("Сервис недоступен")
    
    @pytest.mark.posts
    def test_create_post_without_auth(self, test_config):
        """Создание объявления без авторизации должно вернуть 401"""
        try:
            post_data = {
                "imei": TEST_IMEI,
                "batery": 95,
                "price": 500.0
            }
            
            response = httpx.post(
                f"{test_config.BASE_URL}/api/v1/posts/iphone",
                data=post_data,
                timeout=test_config.REQUEST_TIMEOUT
            )
            
            assert response.status_code == 401, \
                f"Без авторизации должен быть 401, получено: {response.status_code}"
            
        except httpx.ConnectError:
            pytest.skip("Posts сервис недоступен")
    
    @pytest.mark.posts
    def test_create_post_invalid_imei(self, test_config, test_data_tracker):
        """Создание объявления с невалидным IMEI"""
        try:
            # Регистрация
            timestamp = datetime.now().strftime('%Y%m%d%H%M%S%f')
            username = f"_test_invalid_imei_{timestamp}"
            
            reg_response = httpx.post(
                f"{test_config.BASE_URL}/api/v1/auth/register",
                json={
                    "username": username,
                    "email": f"_test_{timestamp}@test.com",
                    "password": "InvalidImei123!"
                },
                timeout=test_config.REQUEST_TIMEOUT
            )
            
            cookies = dict(reg_response.cookies)
            test_data_tracker.track_user(username=username)
            
            # Пост с коротким IMEI
            response = httpx.post(
                f"{test_config.BASE_URL}/api/v1/posts/iphone",
                data={
                    "imei": "12345",  # Слишком короткий - должен быть 15 цифр
                    "batery": 95,
                    "price": 500.0
                },
                cookies=cookies,
                timeout=test_config.REQUEST_TIMEOUT
            )
            
            assert response.status_code == 422, \
                f"Короткий IMEI должен вернуть 422, получено: {response.status_code}"
            
        except httpx.ConnectError:
            pytest.skip("Сервис недоступен")
    
    @pytest.mark.posts
    def test_create_post_invalid_battery(self, test_config, test_data_tracker):
        """Создание объявления с невалидным значением батареи"""
        try:
            # Регистрация
            timestamp = datetime.now().strftime('%Y%m%d%H%M%S%f')
            username = f"_test_invalid_battery_{timestamp}"
            
            reg_response = httpx.post(
                f"{test_config.BASE_URL}/api/v1/auth/register",
                json={
                    "username": username,
                    "email": f"_test_{timestamp}@test.com",
                    "password": "InvalidBattery123!"
                },
                timeout=test_config.REQUEST_TIMEOUT
            )
            
            cookies = dict(reg_response.cookies)
            test_data_tracker.track_user(username=username)
            
            # Пост с батареей > 100
            response = httpx.post(
                f"{test_config.BASE_URL}/api/v1/posts/iphone",
                data={
                    "imei": TEST_IMEI,
                    "batery": 150,  # Невалидное значение
                    "price": 500.0
                },
                cookies=cookies,
                timeout=test_config.REQUEST_TIMEOUT
            )
            
            assert response.status_code == 422, \
                f"Батарея >100 должна вернуть 422, получено: {response.status_code}"
            
        except httpx.ConnectError:
            pytest.skip("Сервис недоступен")


class TestPostValidation:
    """Тесты валидации данных объявления"""
    
    @pytest.mark.posts
    @pytest.mark.imei
    def test_post_has_required_fields(self, test_config):
        """Проверка что существующие посты имеют обязательные поля"""
        try:
            response = httpx.get(
                f"{test_config.BASE_URL}/api/v1/posts/iphone/list",
                params={"limit": 5},
                timeout=test_config.REQUEST_TIMEOUT
            )
            
            if response.status_code == 200:
                posts = response.json()
                if posts:
                    for post in posts:
                        # Обязательные поля
                        assert "id" in post, f"Пост должен иметь id"
                        assert "imei" in post, f"Пост должен иметь imei"
                        assert "batery" in post, f"Пост должен иметь batery"
                        assert "author_id" in post, f"Пост должен иметь author_id"
                        
                        # Поля от IMEI checker (должны быть заполнены для валидных IMEI)
                        # model, color, memory, serial_number
                        print(f"   Post #{post['id']}: model={post.get('model')}, "
                              f"memory={post.get('memory')}, color={post.get('color')}")
                else:
                    pytest.skip("Нет объявлений для проверки")
            
        except httpx.ConnectError:
            pytest.skip("Posts сервис недоступен")


class TestPostReport:
    """Тесты жалоб на объявления"""
    
    @pytest.mark.posts
    def test_report_nonexistent_post(self, test_config):
        """Жалоба на несуществующее объявление"""
        try:
            response = httpx.post(
                f"{test_config.BASE_URL}/api/v1/posts/report",
                json={
                    "post_id": 999999,
                    "reason": "spam"
                },
                timeout=test_config.REQUEST_TIMEOUT
            )
            
            assert response.status_code == 404, \
                f"Жалоба на несуществующий пост должна вернуть 404"
            
        except httpx.ConnectError:
            pytest.skip("Posts сервис недоступен")


class TestCleanupEndpoints:
    """Тесты для endpoint очистки тестовых данных"""
    
    @pytest.mark.posts
    def test_cleanup_endpoint_exists(self, test_config):
        """Проверка что endpoint очистки существует"""
        try:
            response = httpx.delete(
                f"{test_config.BASE_URL}/api/v1/posts/test/iphone/cleanup",
                timeout=test_config.REQUEST_TIMEOUT
            )
            
            # Должен вернуть 200 (даже если нечего удалять)
            assert response.status_code == 200, \
                f"Cleanup endpoint должен вернуть 200, получено: {response.status_code}"
            
            data = response.json()
            assert "deleted_count" in data, "Ответ должен содержать deleted_count"
            
        except httpx.ConnectError:
            pytest.skip("Posts сервис недоступен")

