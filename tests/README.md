# 🧪 Тесты для SS.LV Marketplace

## Описание

Автоматические тесты для проверки работоспособности всех компонентов проекта перед деплоем в production.

## Структура тестов

```
tests/
├── conftest.py              # Конфигурация pytest и fixtures
├── helpers.py               # Вспомогательные функции для тестов
├── test_auth_service.py     # Тесты Auth сервиса (регистрация, логин, профиль)
├── test_posts_service.py    # Тесты Posts сервиса (CRUD объявлений)
├── test_chat_service.py     # Тесты Chat сервиса (WebSocket)
├── test_frontend_service.py # Тесты Frontend (HTML страницы)
├── test_imei_service.py     # Тесты IMEI Checker интеграции
├── test_integration.py      # Интеграционные тесты
├── test_security.py         # Тесты безопасности
├── test_smoke.py            # Smoke тесты (быстрая проверка)
└── test_notifications.py    # Тесты уведомлений
```

## Важно: IMEI Checker

Для тестов используется **тестовый IMEI**: `356901450728885`

В файле `iphone_cheker/checker.py` для этого IMEI есть **моковые данные**:
- Модель: IPHONE 12 PRO MAX
- Память: 256GB
- Цвет: GRAPHITE
- S/N: DX3XK0YQG5K7

Тесты проверяют что IMEI Checker корректно заполняет эти поля при создании объявления.

## Запуск тестов

### Предварительные требования

```bash
# Убедитесь что контейнеры запущены
docker ps

# Должны быть запущены:
# - lais-nginx (nginx прокси)
# - lais-auth (auth-service)
# - lais-posts (posts-service)  
# - lais-chat (chat-service)
# - lais-main (main-service)
# - lais-postgres (PostgreSQL)
```

### Установка зависимостей

```bash
cd tests
pip install -r requirements.txt
```

### Быстрая проверка (smoke тесты)

```bash
pytest -m smoke -v
```

### Все тесты

```bash
pytest -v
```

### Только критические тесты (перед деплоем)

```bash
pytest -m critical -v
```

### Тесты конкретного сервиса

```bash
# Auth сервис
pytest test_auth_service.py -v

# Posts сервис
pytest test_posts_service.py -v

# IMEI тесты
pytest -m imei -v
```

## Очистка тестовых данных

### Автоматическая очистка

По умолчанию тестовые данные **автоматически удаляются** после тестов.

```bash
# Запуск тестов с очисткой (по умолчанию)
pytest -v

# Запуск БЕЗ очистки (для отладки)
pytest -v --no-cleanup

# Только очистка (без тестов)
pytest -v --cleanup-only
```

### Ручная очистка

```bash
# Linux/Mac
./cleanup_test_data.sh

# Или через curl
curl -X DELETE http://localhost:8080/api/v1/posts/test/iphone/cleanup
curl -X DELETE http://localhost:8080/api/v1/auth/test/users/cleanup
```

### Идентификация тестовых данных

Все тестовые данные создаются с префиксом `_test_`:
- **Пользователи**: username и email начинаются с `_test_`
- **Объявления**: description содержит `_test_`
- **Дополнительно**: IMEI начинающийся с `00000`

## API Endpoints для очистки

### Удаление тестовых пользователей

```bash
DELETE /api/v1/auth/test/users/cleanup

# Response:
{
    "status": "cleanup_complete",
    "deleted_count": 5,
    "deleted_usernames": ["_test_user_123", "_test_user_456", ...]
}
```

### Удаление тестовых объявлений

```bash
DELETE /api/v1/posts/test/iphone/cleanup

# Response:
{
    "status": "cleanup_complete", 
    "deleted_count": 3,
    "deleted_ids": [42, 43, 44]
}
```

## Маркеры тестов

| Маркер | Описание |
|--------|----------|
| `@pytest.mark.smoke` | Smoke тесты - быстрая проверка |
| `@pytest.mark.critical` | Критические - обязательны перед деплоем |
| `@pytest.mark.auth` | Тесты Auth сервиса |
| `@pytest.mark.posts` | Тесты Posts сервиса |
| `@pytest.mark.chat` | Тесты Chat сервиса |
| `@pytest.mark.frontend` | Тесты Frontend |
| `@pytest.mark.imei` | Тесты IMEI Checker |
| `@pytest.mark.integration` | Интеграционные тесты |

## Переменные окружения

| Переменная | По умолчанию | Описание |
|------------|--------------|----------|
| `TEST_BASE_URL` | `http://localhost:8080` | URL nginx прокси |
| `TEST_CLEANUP` | `true` | Очищать тестовые данные после тестов |
| `SKIP_INTEGRATION_TESTS` | `false` | Пропустить интеграционные тесты |

## Отчёты

```bash
# HTML отчёт
pytest --html=report.html --self-contained-html

# JUnit XML (для CI/CD)
pytest --junitxml=report.xml

# Покрытие кода
pytest --cov=./ --cov-report=html
```

## Пример вывода

```
============================================
🔍 ПРОВЕРКА ДОСТУПНОСТИ СЕРВИСОВ (через nginx)
   Base URL: http://localhost:8080
============================================
  ✅ Nginx/Main: OK (status: 200)
  ✅ Auth API: OK (status: 401)
  ✅ Posts API: OK (status: 200)
  ✅ Chat API: OK (status: 200)
============================================

✅ Все сервисы доступны через nginx. Тесты готовы к запуску.

test_smoke.py::TestAllServicesAvailable::test_nginx_responds PASSED
test_smoke.py::TestAllServicesAvailable::test_auth_service_available PASSED
...

============================================
🧹 ОЧИСТКА ТЕСТОВЫХ ДАННЫХ
============================================

  📌 Очистка объявлений...
     ✅ Удалено объявлений: 3

  👤 Очистка тестовых пользователей...
     ✅ Удалено пользователей: 5

============================================
```

## Troubleshooting

### "Сервис недоступен"

```bash
# Проверьте контейнеры
docker ps

# Проверьте логи nginx
docker logs lais-nginx

# Перезапустите
docker-compose down && docker-compose up -d
```

### "IMEI Checker не заполняет данные"

Проверьте что используется тестовый IMEI `356901450728885` - для него есть моковые данные в `iphone_cheker/checker.py`.

### "Cleanup не работает"

1. Убедитесь что endpoints доступны:
   ```bash
   curl -X DELETE http://localhost:8080/api/v1/posts/test/iphone/cleanup
   curl -X DELETE http://localhost:8080/api/v1/auth/test/users/cleanup
   ```

2. Перезапустите контейнеры после изменения кода:
   ```bash
   docker-compose build auth-service posts-service
   docker-compose up -d
   ```
