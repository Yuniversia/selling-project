# Notification Service - Инструкции по развертыванию

## 📋 Обзор

Создан новый микросервис **notifications** для отправки SMS уведомлений через SendBerry API.

## ✅ Что реализовано

### 1. Структура микросервиса
- ✅ `notifications/main.py` - FastAPI приложение
- ✅ `notifications/models.py` - Модели БД и Pydantic схемы
- ✅ `notifications/database.py` - Подключение к PostgreSQL
- ✅ `notifications/configs.py` - Конфигурация через переменные окружения
- ✅ `notifications/notification_service.py` - Бизнес-логика и SendBerry интеграция
- ✅ `notifications/notification_router.py` - API эндпоинты
- ✅ `notifications/Dockerfile` - Docker образ
- ✅ `notifications/requirements.txt` - Python зависимости
- ✅ `notifications/README.md` - Документация API

### 2. База данных
- ✅ `notifications/migrations/001_create_notification_tables.sql` - SQL миграция
- ✅ Таблица `notificationlog` - История отправленных уведомлений
- ✅ Таблица `notificationtemplate` - Шаблоны сообщений
- ✅ Дефолтные шаблоны для всех типов уведомлений

### 3. API Эндпоинты
- ✅ `POST /api/v1/notifications/order-created` - Уведомление о создании заказа
- ✅ `POST /api/v1/notifications/order-delivered` - Уведомление о доставке + запрос отзыва
- ✅ `GET /api/v1/notifications/history` - История уведомлений с фильтрами
- ✅ `GET /api/v1/notifications/health` - Health check

### 4. Интеграция с системой заказов
- ✅ `posts/order_router.py` - Вызовы notification service:
  - При создании заказа (`/create`) - уведомления продавцу (SMS) и покупателю
  - При оплате (`/pay`) - подтверждение оплаты
  - При отправке (`/ship`) - уведомление об отправке
  - После доставки - запрос на отзыв
- ✅ `posts/configs.py` - Добавлены переменные NOTIFICATION_SERVICE_URL и FRONTEND_URL

### 5. Docker интеграция
- ✅ `docker-compose.yml` - Добавлен notifications-service на порт 6000
- ✅ Настроены зависимости: postgres, auth-service
- ✅ Healthcheck для мониторинга
- ✅ posts-service теперь зависит от notifications-service

### 6. Функционал
- ✅ SendBerry API интеграция (SMS)
- ✅ Retry механизм (до 3 попыток с exponential backoff)
- ✅ Подробное логирование всех операций
- ✅ Шаблоны с переменными `{order_id}`, `{buyer_name}`, и т.д.
- ✅ История всех отправленных уведомлений в БД
- ✅ Асинхронная отправка (не блокирует создание заказа)
- ✅ Поддержка тестового режима SendBerry

### 7. Тесты
- ✅ `tests/test_notification_service.py` - Unit тесты:
  - Health check
  - Отправка уведомлений
  - Фильтрация истории
  - Рендеринг шаблонов
  - Retry механизм
  - Форматирование телефонов

## 🚀 Инструкции по развертыванию

### Шаг 1: Применить SQL миграции

Подключитесь к PostgreSQL и выполните:

```bash
psql -U postgres -d lais_marketplace -f notifications/migrations/001_create_notification_tables.sql
```

Или через Docker:

```bash
docker exec -i lais-postgres psql -U postgres -d lais_marketplace < notifications/migrations/001_create_notification_tables.sql
```

### Шаг 2: Обновить .env файл (уже настроено)

Убедитесь, что в `.env` есть:

```env
# SendBerry API
SENDBERRY_API_KEY=your_api_key
SENDBERRY_API_NAME=your_access_name
SENDBERRY_API_PASSWORD=your_access_password
SENDBERRY_SENDER_ID=SMS Inform  # Default for test mode

# Frontend URL
FRONTEND_URL=https://test.yuniversia.eu/

# Notification Service URL (для posts-service)
NOTIFICATION_SERVICE_URL=http://notifications-service:6000
```

### Шаг 3: Пересобрать и запустить Docker контейнеры

```bash
# Остановить все контейнеры
docker-compose down

# Пересобрать с новым сервисом
docker-compose build

# Запустить все сервисы
docker-compose up -d

# Проверить логи notification service
docker logs -f lais-notifications

# Проверить healthcheck
curl http://localhost:6000/api/v1/notifications/health
```

### Шаг 4: Проверить работоспособность

1. **Проверить, что сервис запущен:**
```bash
docker ps | grep notifications
```

2. **Проверить логи:**
```bash
docker logs lais-notifications
```

3. **Проверить healthcheck:**
```bash
curl http://localhost:6000/api/v1/notifications/health
```

Ожидаемый ответ:
```json
{
  "status": "healthy",
  "service": "notification-service",
  "version": "1.0.0"
}
```

4. **Проверить документацию API:**
Откройте в браузере: http://localhost:6000/notifications/docs

5. **Создать тестовый заказ** и проверить, что:
   - В логах posts-service появились записи об отправке уведомлений
   - В логах notifications-service видны попытки отправки
   - В таблице `notificationlog` появились записи

### Шаг 5: Проверить таблицы в БД

```sql
-- Проверить таблицы
\dt notificationlog
\dt notificationtemplate

-- Посмотреть шаблоны
SELECT notification_type, description FROM notificationtemplate;

-- Посмотреть историю уведомлений
SELECT id, notification_type, channel, status, created_at 
FROM notificationlog 
ORDER BY created_at DESC 
LIMIT 10;
```

## 📧 Типы уведомлений

### 1. order_created_seller
**Кому:** Продавцу  
**Каналы:** SMS + Email  
**Когда:** При создании заказа и оплате  
**Содержит:** Информация о покупателе, товаре, сумме

### 2. order_created_buyer
**Кому:** Покупателю  
**Каналы:** Email  
**Когда:** При создании заказа и оплате  
**Содержит:** Подтверждение заказа, ссылка для отслеживания

### 3. order_review_request
**Кому:** Покупателю  
**Каналы:** Email  
**Когда:** После отправки товара продавцом  
**Содержит:** Ссылка для оценки продавца и оставления отзыва

## 🔧 Настройка Nginx (если требуется внешний доступ)

Если нужен доступ к notification service извне, добавьте в `nginx/nginx.conf`:

```nginx
# Notification Service
location /notifications/ {
    proxy_pass http://notifications-service:6000/;
    proxy_http_version 1.1;
    proxy_set_header Host $host;
    proxy_set_header X-Real-IP $remote_addr;
    proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    proxy_set_header X-Forwarded-Proto $scheme;
}
```

## 🧪 Запуск тестов

```bash
# Из корневой директории проекта
pytest tests/test_notification_service.py -v

# Или запустить все тесты
pytest tests/ -v
```

## 📊 Мониторинг

### Проверка статуса сервисов:
```bash
docker-compose ps
```

### Логи в реальном времени:
```bash
# Notification service
docker logs -f lais-notifications

# Posts service (для проверки вызовов)
docker logs -f lais-posts
```

### Проверка отправленных уведомлений через API:
```bash
# История по заказу
curl "http://localhost:6000/api/v1/notifications/history?order_id=123"

# История по email
curl "http://localhost:6000/api/v1/notifications/history?email=buyer@example.com"

# Все уведомления (последние 50)
curl "http://localhost:6000/api/v1/notifications/history"
```

## 🔍 Диагностика: Почему не пришли уведомления?

### Шаг 1: Проверить, что notification service запущен

```bash
# Linux/macOS:
docker ps | grep notifications

# Windows PowerShell:
docker ps | findstr notifications

# Ожидаемый вывод: контейнер lais-notifications должен быть в статусе "Up"
```

Если контейнер не запущен:
```bash
docker-compose up -d notifications-service
docker logs lais-notifications
```

### Шаг 2: Проверить логи posts-service (вызовы уведомлений)

```bash
# Linux/macOS - последние 100 строк логов posts-service
docker logs --tail 100 lais-posts | grep -E "notification|CREATE ORDER"

# Windows PowerShell:
docker logs --tail 100 lais-posts | findstr "notification CREATE"

# Поиск попыток отправки уведомлений (Linux/macOS)
docker logs --tail 200 lais-posts | grep -E "Notification|order-created"

# Windows PowerShell:
docker logs --tail 200 lais-posts | findstr "Notification order-created"
```

**Что искать:**
- `✅ Notification sent: order-created` - успешная отправка
- `⚠️ Notification failed` - ошибка отправки
- `❌ Error sending notification` - исключение
- `⚠️ Failed to send notifications` - общая ошибка

### Шаг 3: Проверить логи notifications-service

```bash
# Все логи notification service
docker logs lais-notifications

# Последние 50 строк
docker logs --tail 50 lais-notifications

# Поиск ошибок (Linux/macOS)
docker logs lais-notifications | grep -E "ERROR|Failed|Exception"

# Windows PowerShell:
docker logs lais-notifications | findstr "ERROR Failed Exception"
```

**Что искать:**
- `🔑 Requesting new SendPulse access token...` - запрос OAuth токена
- `✅ SendPulse access token received` - токен получен
- `📧 Sending email to ...` - попытка отправки email
- `📱 Sending SMS to ...` - попытка отправки SMS
- `✅ Email sent successfully` / `✅ SMS sent successfully` - успешная отправка
- `❌ Failed to get SendPulse token` - ошибка получения токена (проверьте API ключи)
- `❌ Email send failed` / `❌ SMS send failed` - ошибка отправки

### Шаг 4: Проверить базу данных

```bash
# Подключиться к PostgreSQL
docker exec -it lais-postgres psql -U postgres -d lais_marketplace
```

В psql выполните:

```sql
-- Проверить, есть ли записи в notificationlog
SELECT 
    id, 
    notification_type, 
    channel, 
    recipient_email,
    recipient_phone,
    status, 
    error_message,
    created_at 
FROM notificationlog 
ORDER BY created_at DESC 
LIMIT 10;

-- Проверить последние неудачные попытки
SELECT 
    id,
    notification_type,
    channel,
    status,
    error_message,
    retry_count,
    created_at
FROM notificationlog 
WHERE status IN ('failed', 'retry')
ORDER BY created_at DESC;

-- Проверить конкретный заказ (замените 123 на ваш order_id)
SELECT * FROM notificationlog WHERE order_id = 123;

-- Выйти из psql
\q
```

**Интерпретация результатов:**
- **Пусто (0 rows)** → notification service НЕ вызывался или НЕ работает БД
- **status = 'pending'** → уведомление в очереди
- **status = 'sent'** → успешно отправлено
- **status = 'failed'** → все попытки исчерпаны, смотрите `error_message`
- **status = 'retry'** → идут повторные попытки

### Шаг 5: Проверить healthcheck

```bash
# Linux/macOS/Windows:
curl http://localhost:6000/api/v1/notifications/health

# Или через PowerShell (Windows):
Invoke-WebRequest -Uri "http://localhost:6000/api/v1/notifications/health" | Select-Object -ExpandProperty Content
```

Ожидаемый ответ:
```json
{"status":"healthy","service":"notification-service","version":"1.0.0"}
```

Если не отвечает - сервис не запущен или упал.

### Шаг 6: Проверить переменные окружения

```bash
# Linux/macOS - проверить, что posts-service знает URL notification service
docker exec lais-posts env | grep NOTIFICATION_SERVICE_URL

# Windows PowerShell:
docker exec lais-posts env | findstr NOTIFICATION_SERVICE_URL

# Должно быть: NOTIFICATION_SERVICE_URL=http://notifications-service:6000

# Проверить SendPulse credentials (Linux/macOS)
docker exec lais-notifications env | grep SENDPULSE

# Windows PowerShell:
docker exec lais-notifications env | findstr SENDPULSE

# Должно быть:
# SENDPULSE_API_ID=f9c9ceb91e80d79748cd2fbbcf05798a
# SENDPULSE_API_SECRET=0a3d1307576dd7e17f8538ddc0ab5760
```

### Шаг 7: Проверить сетевое взаимодействие

```bash
# Проверить, что posts-service может достучаться до notifications-service
docker exec lais-posts curl -s http://notifications-service:6000/api/v1/notifications/health
```

Если получаете ошибку "Could not resolve host" - проблема с Docker сетью.

### Шаг 8: Тестовая отправка вручную

Отправьте тестовое уведомление напрямую в notification service:

```powershell
# Через curl (замените данные на свои)
curl -X POST http://localhost:6000/api/v1/notifications/order-created `
  -H "Content-Type: application/json" `
  -d '{
    "order_id": 999,
    "seller_name": "Test Seller",
    "seller_email": "test-seller@example.com",
    "seller_phone": "+37120000000",
    "buyer_name": "Test Buyer",
    "buyer_email": "test-buyer@example.com",
    "buyer_phone": "+37121111111",
    "product_name": "iPhone 14 Pro",
    "product_model": "128GB Space Black",
    "order_price": 899.99,
    "delivery_method": "DPD",
    "tracking_url": "https://test.yuniversia.eu/orders/999"
  }'
```

Или через PowerShell:
```powershell
$body = @{
    order_id = 999
    seller_name = "Test Seller"
    seller_email = "test-seller@example.com"
    seller_phone = "+37120000000"
    buyer_name = "Test Buyer"
    buyer_email = "test-buyer@example.com"
    product_name = "iPhone 14 Pro"
    product_model = "128GB"
    order_price = 899.99
    delivery_method = "DPD"
    tracking_url = "https://test.yuniversia.eu/orders/999"
} | ConvertTo-Json

Invoke-WebRequest -Uri "http://localhost:6000/api/v1/notifications/order-created" `
  -Method POST `
  -ContentType "application/json" `
  -Body $body
```

Проверьте ответ и логи после тестовой отправки.

## 🐛 Частые проблемы и решения

### ❌ "Connection refused" при вызове notification service

**Причина:** Сервис не запущен или порт закрыт

**Решение:**
```powershell
docker-compose up -d notifications-service
docker logs lais-notifications
```

### ❌ "Failed to get SendPulse token: 401 Unauthorized"

**Причина:** Неверные API credentials SendPulse

**Решение:**
1. Проверьте ключи в `.env`
2. Зайдите в [SendPulse Dashboard](https://sendpulse.com/settings#api)
3. Проверьте, что API доступ активирован
4. Перезапустите сервис: `docker-compose restart notifications-service`

### ❌ Записи в notificationlog есть, но status = 'failed'

**Причина:** SendPulse API вернул ошибку

**Решение:**
```sql
-- Посмотрите error_message
SELECT error_message FROM notificationlog WHERE status = 'failed' ORDER BY created_at DESC LIMIT 1;
```

Частые ошибки:
- `HTTP 401` - неверные credentials
- `HTTP 429` - превышен лимит запросов
- `Invalid phone number` - неверный формат телефона
- `Invalid email` - неверный email

### ❌ Записей в notificationlog вообще нет

**Причина:** posts-service не вызывает notification service

**Решение:**
1. Проверьте, что posts-service пересобран:
```powershell
docker-compose build posts-service
docker-compose up -d posts-service
```

2. Проверьте логи при создании заказа:
```powershell
docker logs -f lais-posts
# Создайте тестовый заказ и смотрите логи
```

3. Проверьте, что в [posts/order_router.py](../posts/order_router.py) есть вызовы `send_notification_async`

### ❌ "Module 'httpx' not found" в posts-service

**Причина:** Не установлена библиотека httpx

**Решение:**
```powershell
docker exec lais-posts pip install httpx
# Или пересоберите контейнер
docker-compose build posts-service
docker-compose up -d posts-service
```

## 📋 Чек-лист диагностики

Пройдитесь по этому списку последовательно:

- [ ] 1. Контейнер lais-notifications запущен (`docker ps`)
- [ ] 2. Healthcheck отвечает (`curl http://localhost:6000/api/v1/notifications/health`)
- [ ] 3. В логах posts-service видны попытки отправки (`docker logs lais-posts | findstr notification`)
- [ ] 4. В логах notifications-service нет критических ошибок (`docker logs lais-notifications`)
- [ ] 5. В таблице notificationlog есть записи (`SELECT * FROM notificationlog`)
- [ ] 6. Переменные окружения настроены правильно (см. Шаг 6)
- [ ] 7. Тестовая отправка работает (см. Шаг 8)

Если все пункты выполнены, но уведомления не приходят:
- Проверьте spam/junk папку в email
- Проверьте, что email/телефон указаны правильно в заказе
- Проверьте лимиты SendPulse аккаунта

## ⚠️ Возможные проблемы

### 1. SendPulse API credentials не работают
**Решение:** Проверьте API ключи в SendPulse dashboard, возможно нужно активировать API доступ

### 2. Notification service не может подключиться к БД
**Решение:** 
```bash
# Проверьте, что postgres запущен
docker ps | grep postgres

# Проверьте логи
docker logs lais-postgres
```

### 3. Posts service не может вызвать notification service
**Решение:**
```bash
# Проверьте, что сервисы в одной сети
docker network inspect ss_lv_lais-network

# Проверьте переменную окружения
docker exec lais-posts env | grep NOTIFICATION_SERVICE_URL
```

### 4. Уведомления не отправляются
**Решение:**
1. Проверьте логи: `docker logs lais-notifications`
2. Проверьте таблицу notificationlog на наличие ошибок:
```sql
SELECT * FROM notificationlog WHERE status = 'failed' ORDER BY created_at DESC LIMIT 10;
```
3. Проверьте, что SendPulse API credentials корректные

## 📝 Дополнительная информация

- **Порты:**
  - 6000 - Notification Service API
  - Docs: http://localhost:6000/notifications/docs

- **База данных:**
  - Таблицы: `notificationlog`, `notificationtemplate`
  - Схема: `public`

- **Переменные окружения:**
  - См. `notifications/configs.py` для полного списка

- **Документация SendPulse API:**
  - https://sendpulse.com/integrations/api

## ✨ Готово!

Notification service полностью интегрирован и готов к использованию. При каждой продаже будут автоматически отправляться уведомления продавцу и покупателю.
