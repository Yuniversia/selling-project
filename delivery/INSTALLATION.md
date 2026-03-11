# Delivery Service - Инструкция по запуску

## 📋 Требования

### 1. Предварительные условия
- ✅ PostgreSQL база данных `lais_marketplace` (общая для всех сервисов)
- ✅ Сервис notifications запущен (порт 6000)
- ✅ Сервис posts запущен (порт 3000)
- ✅ Docker и Docker Compose установлены

### 2. Зависимости
Все зависимости указаны в `requirements.txt`:
```
fastapi==0.104.1
uvicorn[standard]==0.24.0
sqlmodel==0.0.14
psycopg2-binary==2.9.9
python-jose[cryptography]==3.3.0
httpx==0.25.1
```

---

## 🚀 Запуск через Docker Compose (рекомендуется)

### Шаг 1: Убедитесь, что сервис добавлен в docker-compose.yml

```yaml
delivery-service:
  build: ./delivery
  container_name: delivery-service
  ports:
    - "7000:7000"
  environment:
    - DATABASE_URL=postgresql://lais_user:lais_password@postgres:5432/lais_marketplace
    - NOTIFICATION_SERVICE_URL=http://notifications-service:6000
    - FRONTEND_URL=https://test.yuniversia.eu
  depends_on:
    - postgres
  networks:
    - app-network
  restart: unless-stopped
```

### Шаг 2: Запустите сервис

```bash
# Запуск delivery-service
docker-compose up -d delivery-service

# Проверка логов
docker-compose logs -f delivery-service

# Проверка здоровья
curl http://localhost:7000/api/v1/delivery/health
```

### Шаг 3: Применить миграции БД

**Вариант A: Автоматическое создание таблиц (уже настроено)**
Таблицы создаются автоматически при старте через `create_db_and_tables()` в `main.py`

**Вариант B: Ручное применение миграции (рекомендуется для production)**
```bash
# Подключиться к PostgreSQL контейнеру
docker exec -it postgres psql -U lais_user -d lais_marketplace

# Применить миграцию
\i /path/to/delivery/migrations/001_create_delivery_tables.sql

# Или через psql с хоста:
psql -h localhost -U lais_user -d lais_marketplace -f delivery/migrations/001_create_delivery_tables.sql
```

---

## 🖥️ Локальный запуск (для разработки)

### Шаг 1: Установите зависимости

```bash
cd delivery
pip install -r requirements.txt
```

### Шаг 2: Настройте переменные окружения

Создайте файл `.env` в папке `delivery/`:

```env
DATABASE_URL=postgresql://lais_user:lais_password@localhost:5432/lais_marketplace
NOTIFICATION_SERVICE_URL=http://localhost:6000
FRONTEND_URL=http://localhost:8080
```

### Шаг 3: Примените миграцию

```bash
psql -h localhost -U lais_user -d lais_marketplace -f migrations/001_create_delivery_tables.sql
```

### Шаг 4: Запустите сервис

```bash
python main.py
```

Сервис будет доступен на `http://localhost:7000`

---

## ✅ Проверка работоспособности

### 1. Health Check
```bash
curl http://localhost:7000/api/v1/delivery/health
# Ответ: {"status":"ok","service":"delivery-service","timestamp":"..."}
```

### 2. Документация API
Откройте в браузере: `http://localhost:7000/delivery/docs`

### 3. Создание тестовой доставки
```bash
curl -X POST http://localhost:7000/api/v1/delivery/create \
  -H "Content-Type: application/json" \
  -d '{
    "order_id": 999,
    "provider": "omniva",
    "recipient_name": "Test User",
    "recipient_phone": "+37120000000",
    "recipient_email": "test@example.com",
    "sender_name": "Seller",
    "sender_phone": "+37120000001",
    "delivery_city": "Рига"
  }'
```

### 4. Отслеживание доставки
```bash
# После создания доставки получите tracking_number из ответа
curl http://localhost:7000/api/v1/delivery/tracking/{TRACKING_NUMBER}
```

---

## 🔄 Автоматическая симуляция

Сервис автоматически симулирует процесс доставки:

- **created → in_transit**: через 5 секунд после создания
- **in_transit → at_pickup_point**: через 10 секунд (генерирует код + отправляет SMS)

Это настраивается в `main.py` в функции `auto_simulate_deliveries()`.

---

## 🗄️ Структура базы данных

### Таблица `delivery`
- **id** - PRIMARY KEY
- **order_id** - ID заказа (уникальный, индексированный)
- **tracking_number** - Трекинг-номер (уникальный)
- **pickup_code** - 6-значный код получения
- **provider** - omniva, dpd, pickup
- **status** - created, in_transit, at_pickup_point, picked_up, cancelled, returned
- **recipient_name, recipient_phone, recipient_email** - Данные получателя
- **sender_name, sender_phone** - Данные отправителя
- **created_at, shipped_at, arrived_at_pickup_point_at, picked_up_at** - Временные метки
- **notification_sent_at_pickup_point, notification_sent_picked_up** - Флаги отправки SMS

### Таблица `deliverystatushistory`
- **id** - PRIMARY KEY
- **delivery_id** - Связь с delivery
- **status** - Статус
- **notes** - Заметки
- **created_at** - Время изменения

### Views (представления)
- `delivery_stats_by_provider` - Статистика по провайдерам
- `active_deliveries` - Активные доставки
- `deliveries_at_pickup_points` - Доставки в пакоматах

---

## 🔧 Конфигурация Nginx

Для доступа через домен добавьте в `nginx/nginx.conf`:

```nginx
upstream delivery_backend {
    server delivery-service:7000;
}

location /api/v1/delivery/ {
    proxy_pass http://delivery_backend;
    proxy_http_version 1.1;
    proxy_set_header Upgrade $http_upgrade;
    proxy_set_header Connection 'upgrade';
    proxy_set_header Host $host;
    proxy_cache_bypass $http_upgrade;
    proxy_set_header X-Real-IP $remote_addr;
    proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    proxy_set_header X-Forwarded-Proto $scheme;
}
```

После изменений перезапустите Nginx:
```bash
docker-compose restart nginx
```

---

## 📝 Интеграция с другими сервисами

### Posts Service → Delivery Service
Когда пользователь оплачивает заказ, posts-service автоматически создает доставку:

```python
# posts/order_router.py
async with httpx.AsyncClient() as client:
    response = await client.post(
        f"{DELIVERY_SERVICE_URL}/api/v1/delivery/create",
        json={
            "order_id": order.id,
            "provider": order.delivery_method,
            "recipient_name": f"{order.buyer_first_name} {order.buyer_last_name}",
            # ...
        }
    )
```

### Delivery Service → Notifications Service
При достижении статуса `at_pickup_point` отправляется SMS:

```python
# delivery/delivery_service.py
async with httpx.AsyncClient() as client:
    await client.post(
        f"{NOTIFICATION_SERVICE_URL}/api/v1/notifications/send",
        json={
            "notification_type": "delivery_pickup_code",
            "channel": "sms",
            "recipient_phone": delivery.recipient_phone,
            "pickup_code": delivery.pickup_code,
            "tracking_number": delivery.tracking_number
        }
    )
```

---

## 🐛 Отладка

### Проблема: Таблицы не создаются
**Решение**: Примените миграцию вручную
```bash
docker exec -it postgres psql -U lais_user -d lais_marketplace \
  -c "\i /docker-entrypoint-initdb.d/001_create_delivery_tables.sql"
```

### Проблема: SMS не отправляются
**Проверьте**:
1. Сервис notifications запущен и доступен
2. В notifications-service настроен SendPulse API
3. Проверьте логи: `docker-compose logs -f notifications-service`

### Проблема: Автосимуляция не работает
**Проверьте логи**:
```bash
docker-compose logs -f delivery-service | grep "Auto-simulating"
```

### Проблема: Ошибка подключения к БД
**Проверьте**:
```bash
# Проверить, что PostgreSQL запущен
docker-compose ps postgres

# Проверить переменные окружения
docker exec delivery-service env | grep DATABASE_URL
```

---

## 📚 Дополнительная документация

- [README.md](README.md) - Общая информация о сервисе
- [USAGE_GUIDE.md](USAGE_GUIDE.md) - Подробное руководство по использованию
- [INTEGRATION_GUIDE.md](INTEGRATION_GUIDE.md) - Интеграция с другими сервисами
- [QUICKSTART.md](QUICKSTART.md) - Быстрый старт

---

## 🎯 Checklist запуска

- [ ] PostgreSQL база данных создана
- [ ] Миграция применена (таблицы delivery и deliverystatushistory созданы)
- [ ] Сервис notifications запущен (порт 6000)
- [ ] Delivery-service добавлен в docker-compose.yml
- [ ] Delivery-service запущен (`docker-compose up -d delivery-service`)
- [ ] Health check успешен (`curl http://localhost:7000/api/v1/delivery/health`)
- [ ] Nginx настроен для проксирования запросов
- [ ] Posts-service интегрирован с delivery-service

---

**Готово!** ✅ Теперь delivery-service готов к работе.
