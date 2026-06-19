# Delivery Service

Управляет доставкой заказов через DPD и Omniva, а также самовывозом. Синхронизирует пункты выдачи, создаёт отправления, отслеживает статусы, отправляет webhook в posts-service при изменении статуса.

**Порт:** 7000
**API docs:** http://localhost:7000/delivery/docs

---

## Структура файлов

```
delivery/
├── main.py                 # FastAPI app, фоновая задача синхронизации пунктов выдачи
├── delivery_router.py      # Все эндпоинты /api/v1/delivery/*
├── delivery_service.py     # Интеграция с DPD/Omniva, логика трекинга
├── models.py               # Delivery, DeliveryStatusHistory, PickupPoint
├── database.py             # PostgreSQL, get_session()
├── configs.py              # API ключи DPD/Omniva, стоимости, test mode
├── providers/
│   ├── base.py             # Абстрактный класс DeliveryProvider
│   ├── dpd.py              # DPD API интеграция
│   └── omniva.py           # Omniva API интеграция
├── Dockerfile
└── requirements.txt
```

---

## Модели данных

### Таблица `delivery`

```
id                              SERIAL PRIMARY KEY
order_id                        INTEGER UNIQUE         -- нет FK на order (слабая связь)
provider                        VARCHAR                -- omniva / dpd / pickup
tracking_number                 VARCHAR UNIQUE
provider_tracking_number        VARCHAR
pickup_code                     VARCHAR                -- код для получения в постомате
status                          VARCHAR
  -- created / in_transit / at_pickup_point / picked_up / cancelled / returned
delivery_address                TEXT
pickup_point_id                 VARCHAR
pickup_point_name               VARCHAR
recipient_name                  VARCHAR
recipient_phone                 VARCHAR
recipient_email                 VARCHAR
sender_name                     VARCHAR
sender_phone                    VARCHAR
created_at                      TIMESTAMP
shipped_at                      TIMESTAMP
arrived_at_pickup_point_at      TIMESTAMP
picked_up_at                    TIMESTAMP
estimated_delivery_date         DATE
notification_sent_at_pickup_point TIMESTAMP
```

### Таблица `deliverystatushistory`

```
id            SERIAL PRIMARY KEY
delivery_id   INTEGER FK -> delivery.id
status        VARCHAR
notes         TEXT
created_at    TIMESTAMP
```

### Таблица `pickuppoint`

```
id                SERIAL PRIMARY KEY
system_point_id   VARCHAR UNIQUE     -- ID из DPD/Omniva системы
provider          VARCHAR            -- dpd / omniva
country_code      VARCHAR            -- LV / LT / EE
city              VARCHAR
name              VARCHAR
address           VARCHAR
postal_code       VARCHAR
locker_index      VARCHAR            -- для постоматов
```

---

## API Endpoints

| Метод | URL | Описание | Auth |
|---|---|---|---|
| GET | `/api/v1/delivery/pickup-points` | Список пунктов выдачи (фильтр по provider, city) | Нет |
| POST | `/api/v1/delivery/create` | Создать отправление | Внутренний |
| GET | `/api/v1/delivery/order/{order_id}` | Доставка по order_id | Внутренний |
| GET | `/api/v1/delivery/order-page/{tracking_number}` | Страница трекинга для покупателя | Нет |
| GET | `/api/v1/delivery/track/{tracking_number}` | Статус отправления | Нет |
| PATCH | `/api/v1/delivery/{delivery_id}/status` | Обновить статус вручную | Admin |
| POST | `/api/v1/delivery/{delivery_id}/mark-picked-up` | Отметить как полученное | Admin |
| POST | `/api/v1/delivery/{delivery_id}/simulate` | Симуляция для тестирования | Dev |
| GET | `/health` | Health check | Нет |

---

## Флоу доставки

```
1. posts-service (после оплаты) → POST /api/v1/delivery/create
   Тело: {order_id, provider, recipient_*, sender_*, pickup_point_id}

2. delivery-service → DPD/Omniva API → создаёт отправление
   Ответ: {tracking_number, pickup_code}

3. delivery-service периодически опрашивает API провайдера (или принимает webhook)
   → обновляет delivery.status
   → добавляет запись в deliverystatushistory

4. При статусе at_pickup_point:
   → отправляет SMS покупателю (через notifications-service)
   → отправляет webhook в posts-service → Order(status=ready_for_pickup)

5. При статусе picked_up:
   → webhook в posts-service → Order(status=picked_up)
```

---

## Синхронизация пунктов выдачи

При запуске (и каждые 12 часов) сервис загружает пункты выдачи DPD и Omniva:

```python
# main.py lifespan
async def sync_pickup_points():
    if _sync_in_progress:
        return
    _sync_in_progress = True
    # загружает из DPD API и Omniva API
    # обновляет таблицу pickuppoint (upsert по system_point_id)
    _sync_in_progress = False
```

Флаг `_sync_in_progress` предотвращает параллельные синхронизации.

---

## Webhook в posts-service

После изменения статуса доставки:

```python
async def notify_posts_service(order_id: int, status: str):
    async with httpx.AsyncClient() as client:
        await client.post(
            f"{POSTS_SERVICE_URL}/api/v1/orders/delivery-received",
            json={"order_id": order_id, "delivery_status": status}
        )
```

---

## Конфигурация (`.env`)

```env
# DPD
DPD_API_KEY=...
DPD_API_URL=https://api.dpd.com/
DPD_TEST_MODE=false

# Omniva
OMNIVA_API_KEY=...
OMNIVA_API_URL=https://api.omniva.ee/
OMNIVA_TEST_MODE=false

# PostgreSQL
POSTGRES_USER=postgres
POSTGRES_PASSWORD=pass
POSTGRES_HOST=postgres
POSTGRES_DB=lais_marketplace

# Сервисы
POSTS_SERVICE_URL=http://posts-service:3000
NOTIFICATION_SERVICE_URL=http://notifications-service:6000

# Время
PICKUP_POINT_SYNC_INTERVAL_HOURS=12
ESTIMATED_TRANSIT_DAYS_DPD=2
ESTIMATED_TRANSIT_DAYS_OMNIVA=3
```

---

## Запуск

```bash
# Docker
docker-compose up -d delivery-service
docker-compose logs -f delivery-service

# Локально
cd delivery
pip install -r requirements.txt
uvicorn main:app --port 7000 --reload
```

---

## Связи с другими сервисами

| Сервис | Вызов | Когда |
|---|---|---|
| posts-service | POST /api/v1/orders/delivery-received | При изменении статуса доставки |
| notifications-service | POST /api/v1/notifications/order-delivered | Когда посылка в пункте выдачи |

Входящие вызовы:
- `posts-service` → POST `/api/v1/delivery/create` после оплаты заказа

**Дата последнего обновления:** 2026-06-16