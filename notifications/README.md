# Notifications Service

Отправляет SMS-уведомления через SendBerry API. Ведёт журнал всех уведомлений с retry-логикой. Вызывается внутренне другими сервисами — не доступен напрямую с фронтенда.

**Порт:** 6000
**API docs:** http://localhost:6000/notifications/docs

---

## Структура файлов

```
notifications/
├── main.py                   # FastAPI app, lifespan, CORS, подключение роутера
├── notification_router.py    # Эндпоинты /api/v1/notifications/*
├── notification_service.py   # SendBerry API интеграция, retry логика
├── models.py                 # NotificationLog, NotificationType, NotificationStatus
├── database.py               # PostgreSQL, get_session()
├── configs.py                # SendBerry credentials, FRONTEND_URL
├── Dockerfile
└── requirements.txt
```

---

## Модели данных

### Таблица `notificationlog`

```
id                SERIAL PRIMARY KEY
notification_type VARCHAR     -- order_paid / order_review_request / dispute_event
channel           VARCHAR     -- sms / email / both
recipient_email   VARCHAR
recipient_phone   VARCHAR
recipient_name    VARCHAR
order_id          INTEGER
subject           VARCHAR
message           TEXT
status            VARCHAR     -- pending / sent / failed / retry
error_message     TEXT
retry_count       INTEGER DEFAULT 0
created_at        TIMESTAMP
sent_at           TIMESTAMP
external_id       VARCHAR     -- ID из SendBerry API
```

---

## API Endpoints

| Метод | URL | Описание | Вызывает |
|---|---|---|---|
| POST | `/api/v1/notifications/order-paid` | SMS покупателю и продавцу об оплате | posts-service |
| POST | `/api/v1/notifications/order-delivered` | SMS покупателю о доставке | delivery-service |
| POST | `/api/v1/notifications/send` | Отправить произвольное SMS | Внутренние сервисы |
| GET | `/api/v1/notifications/history` | Журнал уведомлений | Админ |
| GET | `/api/v1/notifications/health` | Health check | Docker |

---

## Шаблоны SMS

### `order_paid` (оплата заказа)

**Покупателю:**
> Оплата прошла! Заказ #{order_id} подтверждён. Продавец подготовит товар к отправке.

**Продавцу:**
> Новый заказ #{order_id}! Покупатель оплатил. Упакуйте и сдайте в пункт приёма DPD/Omniva.

### `order_delivered` (товар доставлен)

**Покупателю:**
> Ваш заказ #{order_id} готов к получению! Код для получения: {pickup_code}

---

## Retry логика

При ошибке отправки SMS:
1. Статус меняется на `retry`
2. `retry_count` увеличивается
3. Повторная попытка через экспоненциальную задержку (1 мин, 5 мин, 30 мин)
4. После 3 неудачных попыток — статус `failed`, логируется ошибка

---

## Конфигурация (`.env`)

```env
SENDBERY_API_KEY=...
SENDBERY_SENDER_NAME=LAIS

POSTGRES_USER=postgres
POSTGRES_PASSWORD=pass
POSTGRES_HOST=postgres
POSTGRES_DB=lais_marketplace

FRONTEND_URL=http://localhost:8080
```

---

## Запуск

```bash
# Docker
docker-compose up -d notifications-service
docker-compose logs -f notifications-service

# Локально
cd notifications
pip install -r requirements.txt
uvicorn main:app --port 6000 --reload
```

---

## Пример вызова из другого сервиса

```python
import httpx

async def notify_order_paid(order_id: int, buyer_phone: str, seller_phone: str):
    async with httpx.AsyncClient(timeout=5.0) as client:
        try:
            await client.post(
                "http://notifications-service:6000/api/v1/notifications/order-paid",
                json={
                    "order_id": order_id,
                    "buyer_phone": buyer_phone,
                    "seller_phone": seller_phone
                }
            )
        except Exception:
            # Уведомления не должны ломать основной флоу
            logger.error("Failed to send notification for order %s", order_id)
```

**Важно:** ошибки notifications-service не должны прерывать основные бизнес-операции. Всегда оборачивай вызовы в try/except.

**Дата последнего обновления:** 2026-06-16