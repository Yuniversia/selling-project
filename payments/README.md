# Payments Service

Обрабатывает платежи через Stripe. Создаёт PaymentIntent и Checkout Session, принимает Stripe webhooks, управляет возвратами. Все операции идемпотентны через `X-Request-ID`.

**Порт:** 9000
**API docs:** http://localhost:9000/docs

---

## Структура файлов

```
payments/
├── main.py             # FastAPI app, Redis healthcheck, exception handlers
├── payment_router.py   # Все эндпоинты /api/v1/payments/*
├── payment_service.py  # Stripe интеграция: intent, checkout, webhook, refund
├── seller_service.py   # Stripe Connect: онбординг продавцов
├── models.py           # Payment, PaymentWebhookEvent + Pydantic схемы
├── database.py         # PostgreSQL, схема payments_db
├── configs.py          # Pydantic BaseSettings: Stripe ключи, Redis URLs
├── api_response.py     # Стандартный формат ответа
├── middlewares.py      # RequestContext middleware
├── Dockerfile
└── requirements.txt
```

---

## Модели данных

### Таблица `payment` (схема `payments_db`)

```
id                              SERIAL PRIMARY KEY
order_id                        INTEGER
post_id                         INTEGER
buyer_id                        INTEGER
seller_id                       INTEGER
amount_cents                    INTEGER        -- сумма в центах (например, 9999 = 99.99 EUR)
currency                        VARCHAR(3)     -- "eur"
description                     TEXT
status                          VARCHAR
  -- requires_payment_method / requires_action / processing
  -- succeeded / canceled / failed / partially_refunded / refunded
provider                        VARCHAR        -- "stripe"
provider_payment_intent_id      VARCHAR UNIQUE
provider_checkout_session_id    VARCHAR UNIQUE
client_secret                   VARCHAR        -- для Stripe Elements
idempotency_key                 VARCHAR UNIQUE
metadata                        JSON
last_error                      TEXT
created_at                      TIMESTAMP
updated_at                      TIMESTAMP
paid_at                         TIMESTAMP
refunded_at                     TIMESTAMP
```

### Таблица `paymentwebhookevent`

```
id                  SERIAL PRIMARY KEY
provider_event_id   VARCHAR UNIQUE     -- Stripe event ID (предотвращает дублирование)
event_type          VARCHAR            -- payment_intent.succeeded и др.
payload             JSON
processed_at        TIMESTAMP
```

---

## API Endpoints

| Метод | URL | Описание | Auth |
|---|---|---|---|
| POST | `/api/v1/payments/intents` | Создать Stripe PaymentIntent | Да |
| POST | `/api/v1/payments/checkout-sessions` | Создать Stripe Checkout Session | Да |
| GET | `/api/v1/payments/checkout-sessions/{session_id}` | Статус сессии | Да |
| GET | `/api/v1/payments/{payment_id}` | Получить платёж | Да |
| POST | `/api/v1/payments/{payment_id}/refund` | Возврат средств | Да (admin) |
| POST | `/api/v1/payments/webhooks/stripe` | Stripe webhook (без auth, с подписью) | Подпись |
| GET | `/health` | Health check (проверяет Redis) | Нет |

---

## Идемпотентность

Все мутирующие операции принимают заголовок `X-Request-ID`. Если запрос с тем же `X-Request-ID` уже был обработан — возвращается закешированный результат без повторного создания.

```
POST /api/v1/payments/checkout-sessions
X-Request-ID: order-123-attempt-1
```

---

## Stripe Webhook

Stripe отправляет события на `POST /api/v1/payments/webhooks/stripe`. Сервис верифицирует подпись через `STRIPE_WEBHOOK_SECRET`.

Обрабатываемые события:
- `payment_intent.succeeded` → Payment(status=succeeded), уведомляет posts-service
- `payment_intent.payment_failed` → Payment(status=failed)
- `checkout.session.completed` → Payment(status=succeeded)
- `charge.refunded` → Payment(status=refunded)

---

## Флоу оплаты через Checkout Session

```
1. posts-service → POST /api/v1/payments/checkout-sessions
   Тело: {order_id, post_id, buyer_id, seller_id, amount_cents, currency, success_url, cancel_url}

2. payments-service → Stripe API → создаёт Checkout Session
   Ответ: {checkout_url: "https://checkout.stripe.com/..."}

3. Frontend редиректит покупателя на checkout_url

4. Покупатель платит → Stripe отправляет webhook

5. payments-service обрабатывает webhook → уведомляет posts-service
```

---

## Конфигурация (`.env`)

```env
# Stripe
STRIPE_SECRET_KEY=sk_test_...
STRIPE_PUBLISHABLE_KEY=pk_test_...
STRIPE_WEBHOOK_SECRET=whsec_...

# Режим: если true — использует тестовые Stripe ключи и пропускает реальные списания
PAYMENTS_TEST_MODE=true

# PostgreSQL
POSTGRES_USER=postgres
POSTGRES_PASSWORD=pass
POSTGRES_HOST=postgres
POSTGRES_DB=lais_marketplace
POSTGRES_SCHEMA=payments_db

# Redis (для кеша идемпотентности и event channels)
REDIS_URL=redis://redis:6379/0
REDIS_RESULT_URL=redis://redis:6379/1

# Posts service (для webhook после успешной оплаты)
POSTS_SERVICE_URL=http://posts-service:3000
```

---

## Запуск

```bash
# Docker
docker-compose up -d payments-service
docker-compose logs -f payments-service

# Тестирование webhook локально (нужен Stripe CLI)
stripe listen --forward-to localhost:9000/api/v1/payments/webhooks/stripe

# Локально
cd payments
pip install -r requirements.txt
uvicorn main:app --port 9000 --reload
```

---

## Связи с другими сервисами

Входящие вызовы:
- `posts-service` создаёт checkout session при создании заказа

Исходящие вызовы после webhook:
- `posts-service` — POST `/api/v1/orders/payment-success` при успешной оплате

**Дата последнего обновления:** 2026-06-16