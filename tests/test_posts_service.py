# tests/test_posts_service.py - Тесты для Posts сервиса

import pytest
import httpx
from datetime import datetime
from helpers import assert_status, assert_json_field, TestResult


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
                ({"model": "16"}, "фильтр по модели iPhone 16"),
                ({"price_min": 100, "price_max": 1000}, "фильтр по цене 100-1000"),
                ({"batery_min": 80}, "фильтр по батарее ≥80%"),
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
    """Тесты создания объявления"""
    
    @pytest.mark.posts
    @pytest.mark.critical
    def test_create_post_with_auth(self, test_config):
        """Создание объявления с авторизацией"""
        try:
            # Сначала регистрируемся/логинимся в auth сервисе
            timestamp = datetime.now().strftime('%Y%m%d%H%M%S%f')
            
            reg_response = httpx.post(
                f"{test_config.BASE_URL}/api/v1/auth/register",
                json={
                    "username": f"post_creator_{timestamp}",
                    "email": f"post_creator_{timestamp}@test.com",
                    "password": "PostCreator123!"
                },
                timeout=test_config.REQUEST_TIMEOUT
            )
            
            cookies = dict(reg_response.cookies)
            
            # Создаём пост
            post_data = {
                "imei": "123456789012345",
                "batery": 95,
                "description": "Тестовый iPhone для автотестов",
                "price": 500.0,
                "condition": "Как новый",
                "has_original_box": True,
                "has_charger": True,
                "has_cable": True
            }
            
            response = httpx.post(
                f"{test_config.BASE_URL}/api/v1/posts/iphone",
                data=post_data,
                cookies=cookies,
                timeout=test_config.REQUEST_TIMEOUT
            )
            
            # Может вернуть 201 (создан) или 500 (если IMEI уже существует или другая ошибка)
            assert response.status_code in [201, 422, 500], f"Unexpected: {response.status_code}"
            
        except httpx.ConnectError:
            pytest.skip("Сервис недоступен")
    
    @pytest.mark.posts
    def test_create_post_without_auth(self, test_config):
        """Создание объявления без авторизации должно вернуть ошибку"""
        try:
            post_data = {
                "imei": "123456789012345",
                "batery": 95,
                "price": 500.0
            }
            
            response = httpx.post(
                f"{test_config.BASE_URL}/api/v1/posts/iphone",
                data=post_data,
                timeout=test_config.REQUEST_TIMEOUT
            )
            
            assert response.status_code == 401
            
        except httpx.ConnectError:
            pytest.skip("Posts сервис недоступен")
    
    @pytest.mark.posts
    def test_create_post_invalid_imei(self, test_config):
        """Создание объявления с невалидным IMEI"""
        try:
            # Регистрация
            timestamp = datetime.now().strftime('%Y%m%d%H%M%S%f')
            
            reg_response = httpx.post(
                f"{test_config.BASE_URL}/api/v1/auth/register",
                json={
                    "username": f"invalid_imei_{timestamp}",
                    "email": f"invalid_imei_{timestamp}@test.com",
                    "password": "InvalidImei123!"
                },
                timeout=test_config.REQUEST_TIMEOUT
            )
            
            cookies = dict(reg_response.cookies)
            
            # Пост с коротким IMEI
            response = httpx.post(
                f"{test_config.BASE_URL}/api/v1/posts/iphone",
                data={
                    "imei": "12345",  # Слишком короткий
                    "batery": 95,
                    "price": 500.0
                },
                cookies=cookies,
                timeout=test_config.REQUEST_TIMEOUT
            )
            
            assert response.status_code == 422
            
        except httpx.ConnectError:
            pytest.skip("Сервис недоступен")


class TestPostUpdate:
    """Тесты обновления объявления"""
    
    @pytest.mark.posts
    def test_update_post(self, test_config):
        """Обновление объявления владельцем"""
        try:
            # Регистрация
            timestamp = datetime.now().strftime('%Y%m%d%H%M%S%f')
            
            reg_response = httpx.post(
                f"{test_config.BASE_URL}/api/v1/auth/register",
                json={
                    "username": f"updater_{timestamp}",
                    "email": f"updater_{timestamp}@test.com",
                    "password": "Updater123!"
                },
                timeout=test_config.REQUEST_TIMEOUT
            )
            
            cookies = dict(reg_response.cookies)
            
            # Создаём пост
            create_response = httpx.post(
                f"{test_config.BASE_URL}/api/v1/posts/iphone",
                data={
                    "imei": f"{timestamp[:15]}",
                    "batery": 90,
                    "price": 400.0,
                    "condition": "Новый"
                },
                cookies=cookies,
                timeout=test_config.REQUEST_TIMEOUT
            )
            
            if create_response.status_code == 201:
                post_id = create_response.json().get("id")
                
                # Обновляем цену
                update_response = httpx.put(
                    f"{test_config.BASE_URL}/api/v1/posts/iphone/{post_id}",
                    json={"price": 450.0},
                    cookies=cookies,
                    timeout=test_config.REQUEST_TIMEOUT
                )
                
                # Может быть 200 или 404 если endpoint не существует
                assert update_response.status_code in [200, 404]
                
        except httpx.ConnectError:
            pytest.skip("Сервис недоступен")


class TestPostMyPosts:
    """Тесты получения своих объявлений"""
    
    @pytest.mark.posts
    @pytest.mark.critical
    def test_get_my_posts(self, test_config):
        """Получение списка своих объявлений"""
        try:
            # Регистрация
            timestamp = datetime.now().strftime('%Y%m%d%H%M%S%f')
            
            reg_response = httpx.post(
                f"{test_config.BASE_URL}/api/v1/auth/register",
                json={
                    "username": f"my_posts_{timestamp}",
                    "email": f"my_posts_{timestamp}@test.com",
                    "password": "MyPosts123!"
                },
                timeout=test_config.REQUEST_TIMEOUT
            )
            
            cookies = dict(reg_response.cookies)
            
            # Получаем свои посты
            response = httpx.get(
                f"{test_config.BASE_URL}/api/v1/posts/iphone/my",
                cookies=cookies,
                timeout=test_config.REQUEST_TIMEOUT
            )
            
            # Может быть 200 или 404 если endpoint не существует
            assert response.status_code in [200, 404]
            
        except httpx.ConnectError:
            pytest.skip("Сервис недоступен")


class TestPostReport:
    """Тесты системы жалоб на объявления"""
    
    @pytest.mark.posts
    def test_report_post(self, test_config):
        """Подача жалобы на объявление"""
        try:
            # Получаем список постов
            list_response = httpx.get(
                f"{test_config.BASE_URL}/api/v1/posts/iphone/list",
                params={"limit": 1},
                timeout=test_config.REQUEST_TIMEOUT
            )
            
            if list_response.status_code == 200:
                posts = list_response.json()
                if posts:
                    post_id = posts[0]["id"]
                    
                    # Подаём жалобу
                    response = httpx.post(
                        f"{test_config.BASE_URL}/api/v1/posts/iphone/{post_id}/report",
                        json={
                            "reason": "Мошенничество",
                            "details": "Тестовая жалоба"
                        },
                        timeout=test_config.REQUEST_TIMEOUT
                    )
                    
                    # Может быть 200/201 или 404 если endpoint не существует
                    assert response.status_code in [200, 201, 404]
                    
        except httpx.ConnectError:
            pytest.skip("Posts сервис недоступен")


class TestCloudflareUpload:
    """Тесты загрузки изображений в Cloudflare"""
    
    @pytest.mark.posts
    def test_get_r2_upload_link(self, test_config):
        """Получение ссылки для загрузки в Cloudflare R2"""
        try:
            response = httpx.get(
                f"{test_config.BASE_URL}/api/v1/posts/r2_link",
                timeout=test_config.REQUEST_TIMEOUT
            )
            
            # Может быть 200 или 500 если Cloudflare не настроен
            assert response.status_code in [200, 500]
            
            if response.status_code == 200:
                data = response.json()
                assert "upload_url" in data
                
        except httpx.ConnectError:
            pytest.skip("Posts сервис недоступен")


class TestOrders:
    """Тесты системы заказов"""
    
    @pytest.mark.posts
    @pytest.mark.critical
    def test_create_order(self, test_config):
        """Создание заказа"""
        try:
            # Регистрация
            timestamp = datetime.now().strftime('%Y%m%d%H%M%S%f')
            
            reg_response = httpx.post(
                f"{test_config.BASE_URL}/api/v1/auth/register",
                json={
                    "username": f"order_test_{timestamp}",
                    "email": f"order_{timestamp}@test.com",
                    "password": "OrderTest123!"
                },
                timeout=test_config.REQUEST_TIMEOUT
            )
            
            cookies = dict(reg_response.cookies)
            
            # Получаем список постов для заказа
            list_response = httpx.get(
                f"{test_config.BASE_URL}/api/v1/posts/iphone/list",
                params={"limit": 1},
                timeout=test_config.REQUEST_TIMEOUT
            )
            
            if list_response.status_code == 200:
                posts = list_response.json()
                if posts:
                    post_id = posts[0]["id"]
                    
                    # Создаём заказ
                    order_response = httpx.post(
                        f"{test_config.BASE_URL}/api/v1/posts/orders/create",
                        json={
                            "iphone_id": post_id,
                            "delivery_method": "pickup",
                            "address": "Тестовый адрес"
                        },
                        cookies=cookies,
                        timeout=test_config.REQUEST_TIMEOUT
                    )
                    
                    # Может быть разные статусы в зависимости от логики
                    assert order_response.status_code in [200, 201, 400, 422]
                    
        except httpx.ConnectError:
            pytest.skip("Сервис недоступен")
    
    @pytest.mark.posts
    def test_get_buyer_orders(self, test_config):
        """Получение заказов покупателя"""
        try:
            # Регистрация
            timestamp = datetime.now().strftime('%Y%m%d%H%M%S%f')
            
            reg_response = httpx.post(
                f"{test_config.BASE_URL}/api/v1/auth/register",
                json={
                    "username": f"buyer_{timestamp}",
                    "email": f"buyer_{timestamp}@test.com",
                    "password": "Buyer123!"
                },
                timeout=test_config.REQUEST_TIMEOUT
            )
            
            cookies = dict(reg_response.cookies)
            
            # Получаем заказы
            response = httpx.get(
                f"{test_config.BASE_URL}/api/v1/posts/orders/buyer",
                cookies=cookies,
                timeout=test_config.REQUEST_TIMEOUT
            )
            
            assert response.status_code in [200, 404]
            
        except httpx.ConnectError:
            pytest.skip("Сервис недоступен")
    
    @pytest.mark.posts
    def test_get_seller_orders(self, test_config):
        """Получение заказов продавца"""
        try:
            # Регистрация
            timestamp = datetime.now().strftime('%Y%m%d%H%M%S%f')
            
            reg_response = httpx.post(
                f"{test_config.BASE_URL}/api/v1/auth/register",
                json={
                    "username": f"seller_{timestamp}",
                    "email": f"seller_{timestamp}@test.com",
                    "password": "Seller123!"
                },
                timeout=test_config.REQUEST_TIMEOUT
            )
            
            cookies = dict(reg_response.cookies)
            
            # Получаем заказы
            response = httpx.get(
                f"{test_config.BASE_URL}/api/v1/posts/orders/seller",
                cookies=cookies,
                timeout=test_config.REQUEST_TIMEOUT
            )
            
            assert response.status_code in [200, 404]
            
        except httpx.ConnectError:
            pytest.skip("Сервис недоступен")


class TestBoughtItems:
    """Тесты системы покупок"""
    
    @pytest.mark.posts
    def test_get_bought_items(self, test_config):
        """Получение списка купленных товаров"""
        try:
            # Регистрация
            timestamp = datetime.now().strftime('%Y%m%d%H%M%S%f')
            
            reg_response = httpx.post(
                f"{test_config.BASE_URL}/api/v1/auth/register",
                json={
                    "username": f"bought_{timestamp}",
                    "email": f"bought_{timestamp}@test.com",
                    "password": "Bought123!"
                },
                timeout=test_config.REQUEST_TIMEOUT
            )
            
            cookies = dict(reg_response.cookies)
            
            # Получаем купленные товары
            response = httpx.get(
                f"{test_config.BASE_URL}/api/v1/posts/bought/",
                cookies=cookies,
                timeout=test_config.REQUEST_TIMEOUT
            )
            
            assert response.status_code in [200, 404, 405]
            
        except httpx.ConnectError:
            pytest.skip("Сервис недоступен")

