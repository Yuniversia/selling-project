# 🧪 Автоматическое тестирование проекта

## Обзор

Этот проект содержит комплексную систему автоматических тестов для проверки работоспособности всех компонентов перед деплоем в production.

## Структура тестов

```
tests/
├── conftest.py              # Конфигурация и fixtures
├── requirements.txt         # Зависимости для тестов
├── test_auth_service.py     # Тесты Auth сервиса
├── test_posts_service.py    # Тесты Posts сервиса
├── test_chat_service.py     # Тесты Chat сервиса
├── test_frontend_service.py # Тесты Frontend (Main) сервиса
├── test_integration.py      # Интеграционные тесты
├── test_smoke.py            # Быстрые smoke тесты
└── test_notifications.py    # Тесты уведомлений
```

## Установка

```bash
# Установка зависимостей
pip install -r tests/requirements.txt

# Или через make
make test-install
```

## Запуск тестов

### Быстрый запуск (Smoke тесты)
```bash
# Проверка что все сервисы работают
make test-smoke

# Или напрямую
pytest tests/ -m "smoke" -v
```

### Критические тесты (перед деплоем)
```bash
make test-critical

# Или
pytest tests/ -m "critical" -v
```

### Все тесты
```bash
make test

# Или
pytest tests/ -v
```

### Тестирование отдельных сервисов
```bash
# Auth сервис
make test-auth
pytest tests/test_auth_service.py -v

# Posts сервис
make test-posts
pytest tests/test_posts_service.py -v

# Chat сервис
make test-chat
pytest tests/test_chat_service.py -v

# Frontend сервис
make test-frontend
pytest tests/test_frontend_service.py -v
```

### Интеграционные тесты
```bash
make test-integration
pytest tests/test_integration.py -v
```

### Полное тестирование перед деплоем
```bash
make test-pre-deploy

# Или скриптом
./run_tests.sh          # Linux/Mac
.\run_tests.ps1         # Windows PowerShell
```

## Категории тестов (Markers)

| Marker | Описание |
|--------|----------|
| `smoke` | Быстрые тесты для проверки работоспособности |
| `critical` | Критические тесты, обязательные перед деплоем |
| `auth` | Тесты Auth сервиса |
| `posts` | Тесты Posts сервиса |
| `chat` | Тесты Chat сервиса |
| `frontend` | Тесты Frontend сервиса |
| `integration` | Интеграционные тесты |
| `slow` | Медленные тесты |

### Запуск по категориям
```bash
# Несколько категорий
pytest tests/ -m "smoke or critical" -v

# Исключить категорию
pytest tests/ -m "not slow" -v
```

## Конфигурация

### Переменные окружения

| Переменная | По умолчанию | Описание |
|------------|--------------|----------|
| `TEST_AUTH_URL` | `http://localhost:8000` | URL Auth сервиса |
| `TEST_POSTS_URL` | `http://localhost:3000` | URL Posts сервиса |
| `TEST_CHAT_URL` | `http://localhost:4000` | URL Chat сервиса |
| `TEST_MAIN_URL` | `http://localhost:8080` | URL Main сервиса |

### Пример настройки
```bash
export TEST_AUTH_URL=http://192.168.1.100:8000
export TEST_POSTS_URL=http://192.168.1.100:3000
pytest tests/ -v
```

## Что тестируется

### Auth сервис
- ✅ Health check `/health`
- ✅ Регистрация пользователя `/auth/register`
- ✅ Вход в систему `/auth/login`
- ✅ Обновление токена `/auth/refresh`
- ✅ Получение профиля `/auth/me`
- ✅ Обновление профиля `PUT /auth/me`
- ✅ Выход `/auth/logout`
- ✅ Получение пользователя по ID `/auth/user`

### Posts сервис
- ✅ Health check `/health`
- ✅ Список товаров `/api/v1/iphone/list`
- ✅ Фильтрация и сортировка
- ✅ Пагинация
- ✅ Получение товара по ID `/api/v1/iphone`
- ✅ Создание товара `POST /api/v1/iphone`
- ✅ Загрузка изображений `/api/v1/r2_link`
- ✅ Система заказов `/api/v1/orders/*`
- ✅ Система покупок `/api/v1/bought/*`

### Chat сервис
- ✅ Health check `/health`
- ✅ Создание чата `/api/chat/chats`
- ✅ Поиск чата `/api/chat/chats/find`
- ✅ Получение чатов пользователя `/api/chat/chats/my`
- ✅ Отправка сообщений `/api/chat/chats/{id}/messages`
- ✅ Получение сообщений с пагинацией
- ✅ Отметка прочитанными `/api/chat/chats/{id}/read`
- ✅ WebSocket соединение

### Frontend сервис
- ✅ Health check `/health`
- ✅ Главная страница `/`
- ✅ Страница товара `/product`
- ✅ Профиль `/profile`
- ✅ Подача объявления `/post-ad`
- ✅ Страница продавца `/seller`
- ✅ Правила `/terms`
- ✅ Политика `/policy`
- ✅ Проверка IMEI `/imei-check`
- ✅ Мои заказы `/my-orders`
- ✅ Мои продажи `/my-sales`
- ✅ Статические файлы
- ✅ Переключение языков

### Интеграционные тесты
- ✅ Полный цикл регистрации → логин → профиль → выход
- ✅ Создание объявления → просмотр → появление в списке
- ✅ Чат: создание → сообщения → прочтение
- ✅ Обновление токена
- ✅ Обновление профиля
- ✅ Процесс покупки
- ✅ Полный пользовательский путь
- ✅ Межсервисное взаимодействие

## HTML отчёт

Для создания HTML отчёта:
```bash
make test-report

# Или
pytest tests/ -v --html=test_report.html --self-contained-html
```

Отчёт будет сохранён в `test_report.html`.

## CI/CD интеграция

### GitHub Actions
```yaml
name: Tests

on: [push, pull_request]

jobs:
  test:
    runs-on: ubuntu-latest
    
    services:
      postgres:
        image: postgres:15
        env:
          POSTGRES_PASSWORD: pass
        ports:
          - 5432:5432
    
    steps:
      - uses: actions/checkout@v3
      
      - name: Start services
        run: docker-compose up -d
        
      - name: Wait for services
        run: sleep 30
        
      - name: Install test dependencies
        run: pip install -r tests/requirements.txt
        
      - name: Run smoke tests
        run: pytest tests/ -m "smoke" -v
        
      - name: Run critical tests
        run: pytest tests/ -m "critical" -v
        
      - name: Run all tests
        run: pytest tests/ -v --html=test_report.html
        
      - name: Upload test report
        uses: actions/upload-artifact@v3
        with:
          name: test-report
          path: test_report.html
```

## Рекомендации перед деплоем

1. **Запустите все сервисы:**
   ```bash
   docker-compose up -d
   ```

2. **Дождитесь готовности:**
   ```bash
   make health
   ```

3. **Запустите тесты:**
   ```bash
   make test-pre-deploy
   ```

4. **Проверьте результат:**
   - Все smoke тесты должны пройти
   - Все critical тесты должны пройти
   - Если есть падения - исправьте перед деплоем

## Troubleshooting

### Сервисы недоступны
```
pytest.skip("Auth сервис недоступен")
```
**Решение:** Запустите сервисы: `docker-compose up -d`

### Таймаут соединения
**Решение:** Увеличьте `REQUEST_TIMEOUT` в `conftest.py`

### Тесты падают из-за дубликатов
**Решение:** Тесты используют уникальные timestamp в именах, но если база заполнена - очистите тестовые данные

### WebSocket тесты пропускаются
**Решение:** Установите `websockets`: `pip install websockets`

## Автор

Тесты созданы для проекта LAIS Marketplace.
