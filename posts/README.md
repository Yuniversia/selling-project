# Posts Service

Центральный сервис платформы. Управляет объявлениями (товары), заказами, спорами, отзывами, просмотрами и жалобами. Оркестрирует весь флоу покупки — от создания заказа до подтверждения получения.

**Порт:** 3000
**API docs:** http://localhost:3000/docs

---

## Структура файлов

```
posts/
├── main.py                # FastAPI app, lifespan, подключение роутеров, запуск фоновых задач
├── post_router_v2.py      # CRUD объявлений, поиск, фильтры, просмотры, жалобы
├── order_router.py        # Заказы, статусы, споры, отзывы, дисконты, webhook доставки
├── bought_router.py       # Legacy: прямые покупки (устарел, оставлен для совместимости)
├── post_service_v2.py     # Бизнес-логика объявлений: IMEI-проверка, загрузка фото в R2
├── models_v2.py           # Основные модели: Product, Order, OrderIssue, OrderReview и др.
├── models.py              # Legacy модели (ссылается на models_v2)
├── database.py            # Подключение к PostgreSQL, схема posts_db
├── configs.py             # Cloudflare R2, URLs сервисов, стоимости доставки, настройки споров
├── cloudflare_r2.py       # Загрузка/удаление изображений в Cloudflare R2
├── taskiq_broker.py       # Redis-брокер для фоновых задач (Taskiq)
├── tasks.py               # Фоновые задачи: IMEI проверка, создание доставки
├── Dockerfile
└── requirements.txt
```

---

## Модели данных (`models_v2.py`)

### `Product` (таблица `iphone` в схеме `posts_db`)

```
id              SERIAL PRIMARY KEY
category_id     INTEGER
seller_id       INTEGER FK -> user.id
price           FLOAT
title           VARCHAR
description     TEXT
status          VARCHAR  -- creating / published / pending_verification / rejected
active          BOOLEAN DEFAULT true
imei            VARCHAR(15) UNIQUE
model           VARCHAR  -- "iPhone 15 Pro Max"
color           VARCHAR
memory          INTEGER  -- GB
images_url      JSON     -- список URL изображений
attributes      JSON     -- дополнительные атрибуты
imei_data_source VARCHAR -- mock / cache / imei.info
view_count      INTEGER DEFAULT 0
created_at      TIMESTAMP
updated_at      TIMESTAMP
```

### `Order` (таблица `order`)

```
id                      SERIAL PRIMARY KEY
post_id                 INTEGER FK -> iphone.id
buyer_id                INTEGER FK -> user.id
seller_id               INTEGER FK -> user.id
status                  VARCHAR
  -- pending_payment / paid / in_transit / ready_for_pickup
  -- picked_up / confirmed / cancelled / refunded
price                   FLOAT
delivery_cost           FLOAT
delivery_method         VARCHAR  -- pickup / dpd / omniva
selected_locker_id      VARCHAR  -- ID пункта выдачи
tracking_number         VARCHAR
order_confirmed_at      TIMESTAMP
discount_offered        FLOAT    -- предложенная скидка продавцом
discount_status         VARCHAR  -- pending / accepted / rejected
created_at              TIMESTAMP
updated_at              TIMESTAMP
```

### `OrderIssue` (споры)

```
id              SERIAL PRIMARY KEY
order_id        INTEGER FK -> order.id
issue_type      VARCHAR  -- not_received / not_as_described / damaged
status          VARCHAR  -- open / seller_responded / escalated / resolved / closed
buyer_message   TEXT
seller_response TEXT
buyer_media_urls JSON
seller_media_urls JSON
admin_verdict   VARCHAR
return_tracking_number VARCHAR
created_at      TIMESTAMP
```

### `OrderReview` (отзывы)

```
id              SERIAL PRIMARY KEY
order_id        INTEGER FK -> order.id UNIQUE
seller_id       INTEGER
product_rating  INTEGER  -- 1-5
seller_rating   INTEGER  -- 1-5
comment         TEXT
created_at      TIMESTAMP
```

### `PostView`, `PostReport` — аналитика и модерация

---

## API Endpoints

### Объявления

| Метод | URL | Описание | Auth |
|---|---|---|---|
| POST | `/api/v1/posts` | Создать объявление (старт: статус creating) | Да |
| POST | `/api/v1/posts/{id}/images` | Загрузить изображения в R2 | Да |
| POST | `/api/v1/posts/{id}/publish` | Опубликовать после заполнения | Да |
| GET | `/api/v1/posts` | Список с фильтрами (модель, память, цена, статус) | Нет |
| GET | `/api/v1/posts/{id}` | Карточка товара | Нет |
| PATCH | `/api/v1/posts/{id}` | Обновить объявление | Да (владелец) |
| DELETE | `/api/v1/posts/{id}` | Снять с публикации | Да (владелец) |
| POST | `/api/v1/posts/{id}/report` | Пожаловаться на объявление | Да |

### Заказы

| Метод | URL | Описание | Auth |
|---|---|---|---|
| POST | `/api/v1/orders` | Создать заказ, запустить оплату | Да |
| GET | `/api/v1/orders` | Мои заказы (покупатель или продавец) | Да |
| GET | `/api/v1/orders/{id}` | Детали заказа | Да |
| POST | `/api/v1/orders/{id}/confirm` | Подтвердить получение (покупатель) | Да |
| POST | `/api/v1/orders/{id}/cancel` | Отменить заказ | Да |
| POST | `/api/v1/orders/{id}/discount` | Продавец предлагает скидку | Да |
| POST | `/api/v1/orders/{id}/discount/accept` | Покупатель принимает скидку | Да |
| POST | `/api/v1/orders/delivery-received` | Webhook от delivery-service | Внутренний |

### Споры

| Метод | URL | Описание | Auth |
|---|---|---|---|
| POST | `/api/v1/orders/{id}/issue` | Открыть спор | Да (покупатель) |
| POST | `/api/v1/orders/{id}/issue/respond` | Ответить на спор | Да (продавец) |
| POST | `/api/v1/orders/{id}/issue/escalate` | Эскалировать до админа | Да |
| POST | `/api/v1/orders/{id}/issue/resolve` | Закрыть спор (админ) | Да (admin) |

### Отзывы

| Метод | URL | Описание | Auth |
|---|---|---|---|
| POST | `/api/v1/orders/{id}/review` | Оставить отзыв после завершения | Да (покупатель) |

---

## Флоу покупки

```
1. Покупатель нажимает "Купить"
   → POST /api/v1/orders  →  Order(status=pending_payment)
   → posts-service вызывает payments-service → создаёт Stripe Checkout Session
   → возвращает checkout_url покупателю

2. Покупатель оплачивает в Stripe

3. Stripe webhook → payments-service → обновляет Payment(status=succeeded)
   → payments-service вызывает posts-service webhook → Order(status=paid)
   → posts-service вызывает delivery-service → создаёт доставку
   → posts-service вызывает notifications-service → SMS продавцу и покупателю

4. Продавец отправляет товар
   → delivery-service обновляет статус доставки
   → delivery-service отправляет webhook → posts-service → Order(status=in_transit / ready_for_pickup)

5. Покупатель забирает товар
   → POST /api/v1/orders/{id}/confirm → Order(status=confirmed)
   → Покупатель оставляет отзыв: POST /api/v1/orders/{id}/review
```

---

## Конфигурация (`.env`)

```env
# Cloudflare R2 (изображения)
CF_ACCOUNT_ID=...
CF_R2_ACCESS_KEY_ID=...
CF_R2_SECRET_ACCESS_KEY=...
POST_CF_R2_BUCKET_NAME=...
POST_CF_R2_HASH=...

# URLs сервисов
IMEI_SERVICE_URL=http://imei-checker-service:5002
DELIVERY_SERVICE_URL=http://delivery-service:7000
NOTIFICATION_SERVICE_URL=http://notifications-service:6000
PAYMENTS_SERVICE_URL=http://payments-service:9000
CHAT_SERVICE_URL=http://chat-service:4000

# Стоимость доставки
DELIVERY_COST_PICKUP=0
DELIVERY_COST_DPD=2.99
DELIVERY_COST_OMNIVA=1.99

# Споры
DISPUTE_AUTO_ACCEPT_DAYS=7   # дней до авто-подтверждения без ответа покупателя

# Redis (для Taskiq)
REDIS_URL=redis://redis:6379/0

# Режим
USE_TEST_MODE=false
```

---

## Фоновые задачи (Taskiq)

Posts-service использует Redis + Taskiq для асинхронных задач:
- Проверка IMEI при создании объявления (не блокирует ответ)
- Авто-подтверждение заказов через N дней (фоновый cron)

---

## Запуск

```bash
# Docker
docker-compose up -d posts-service
docker-compose logs -f posts-service

# Локально
cd posts
pip install -r requirements.txt
uvicorn main:app --port 3000 --reload
```

---

## Связи с другими сервисами

| Сервис | Вызов | Когда |
|---|---|---|
| imei-checker-service | POST /api/check-basic | При создании объявления |
| payments-service | POST /api/v1/payments/checkout-sessions | При создании заказа |
| delivery-service | POST /api/v1/delivery/create | После оплаты |
| notifications-service | POST /api/v1/notifications/order-paid | После оплаты |
| chat-service | POST /api/chat/chats/hide-for-order | После завершения заказа |

**Дата последнего обновления:** 2026-06-16