# Payments Service

Микросервис обработки платежей на Stripe в стиле остальных сервисов проекта.

## Возможности
- Создание Stripe PaymentIntent: `POST /api/v1/payments/intents` (`202 Accepted`)
- Создание Stripe Checkout Session (redirect): `POST /api/v1/payments/checkout-sessions` (`202 Accepted`)
- Проверка Stripe Checkout Session: `GET /api/v1/payments/checkout-sessions/{session_id}`
- Получение платежа: `GET /api/v1/payments/{payment_id}`
- Рефанд: `POST /api/v1/payments/{payment_id}/refund` (`202 Accepted`)
- Stripe webhook: `POST /api/v1/payments/webhooks/stripe`
- Health-check: `GET /health`

## Environment Variables
- `STRIPE_SECRET_KEY`
- `STRIPE_WEBHOOK_SECRET`
- `STRIPE_PUBLISHABLE_KEY`
- `REDIS_URL`
- `USE_POSTGRES`, `POSTGRES_*`, `POSTGRES_SCHEMA`

## Локальный запуск
```bash
uvicorn main:app --host 0.0.0.0 --port 9000 --reload
```

## Запуск в Docker Compose
```bash
docker compose up -d postgres redis auth-service payments-service posts-service main-service
```

## Тестовая оплата (через posts-service)
1. Создай заказ на странице товара.
2. Нажми кнопку оплаты на шаге 3.
3. `posts-service` вызовет `payments-service` и в тестовом режиме отправит `pm_card_visa`.
4. При успешном Stripe test payment заказ перейдет в `paid`.

Переменные для тестового режима:
- `PAYMENTS_TEST_MODE=true`
- `STRIPE_SECRET_KEY=sk_test_...`
- `STRIPE_WEBHOOK_SECRET=whsec_...`
