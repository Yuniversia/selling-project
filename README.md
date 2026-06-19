# LAIS Marketplace

Платформа для покупки и продажи iPhone. Микросервисная архитектура на FastAPI + PostgreSQL + Docker.

**Production:** https://test.yuniversia.eu/

---

## Быстрый старт

```bash
# Скопировать .env.example в .env и заполнить ключи
cp .env.example .env

# Поднять все сервисы
docker-compose up -d --build

# Проверить статус
docker-compose ps
```

**Доступные адреса после запуска:**

| Сервис | URL |
|---|---|
| Frontend | http://localhost:8080 |
| Auth API docs | http://localhost:8000/auth/docs |
| Posts API docs | http://localhost:3000/docs |
| Chat API docs | http://localhost:4000/docs |
| Payments API docs | http://localhost:9000/docs |
| Notifications API docs | http://localhost:6000/notifications/docs |
| Delivery API docs | http://localhost:7000/delivery/docs |
| IMEI Checker API docs | http://localhost:5002/docs |

---

## Состав системы

```
marketplace/
├── auth/              # Аутентификация, пользователи, JWT, Google OAuth    :8000
├── posts/             # Объявления, заказы, споры, отзывы                  :3000
├── chat/              # WebSocket чат, push-уведомления, файлы             :4000
├── payments/          # Stripe платежи, webhooks, возвраты                 :9000
├── notifications/     # SMS через SendBerry                                :6000
├── delivery/          # DPD / Omniva доставка, трекинг                    :7000
├── iphone_cheker/     # Проверка IMEI с кешированием                      :5002
├── main/              # HTML/Jinja2 frontend, статика, sitemap             :8080
├── nginx/             # Reverse proxy, единая точка входа                 :80->8080
├── Markdown/          # Архитектурная документация
├── ARCHITECTURE.md    # Общие паттерны и стандарты кода
├── docker-compose.yml
└── .env
```

Подробный README по каждому сервису — в соответствующей папке.

---

## Архитектура

```
Browser
  │
  ▼
NGINX :8080
  │
  ├─── /api/v1/auth/*          → auth-service:8000
  ├─── /api/v1/posts/*         → posts-service:3000
  ├─── /api/v1/chat/*          → chat-service:4000
  ├─── /api/v1/imei/*          → imei-checker-service:5002
  ├─── /api/v1/notifications/* → notifications-service:6000
  ├─── /api/v1/delivery/*      → delivery-service:7000
  ├─── /ws*                    → chat-service:4000 (WebSocket)
  └─── /                       → main-service:8080

Все сервисы → PostgreSQL :5432 (lais_marketplace)
posts + chat → Cloudflare R2 (файлы и изображения)
payments     → Stripe API
notifications → SendBerry SMS API
iphone_cheker → imei.info API
auth         → Google OAuth API
posts        → Redis (Taskiq очередь задач)
```

Межсервисные HTTP-вызовы (внутри Docker сети):

| Откуда | Куда | Зачем |
|---|---|---|
| posts-service | imei-checker-service | Проверка IMEI при создании объявления |
| posts-service | delivery-service | Создание доставки после оплаты |
| posts-service | payments-service | Создание payment intent |
| posts-service | notifications-service | SMS покупателю и продавцу |
| posts-service | chat-service | Скрытие чата после завершения заказа |
| chat-service | posts-service | Проверка активности объявления |
| delivery-service | posts-service | Webhook об изменении статуса доставки |
| delivery-service | notifications-service | SMS при доставке |

---

## База данных

Единая PostgreSQL база `lais_marketplace`. Логические схемы по сервисам:

- `public` — auth, chat, notifications, delivery
- `posts_db` — posts service
- `payments_db` — payments service

Полная схема: [Markdown/DB_FULL_VIEW.md](Markdown/DB_FULL_VIEW.md)

---

## Команды разработки

```bash
# Запуск всего
docker-compose up -d --build

# Остановка
docker-compose down

# Пересобрать один сервис
docker-compose up -d --build posts-service

# Логи сервиса
docker-compose logs -f posts-service

# Войти в контейнер
docker-compose exec posts-service sh

# Подключиться к БД
docker-compose exec postgres psql -U postgres -d lais_marketplace

# Полный сброс данных
docker-compose down -v && docker-compose up -d --build
```

Все имена сервисов: `postgres`, `redis`, `auth-service`, `posts-service`, `chat-service`, `imei-checker-service`, `notifications-service`, `delivery-service`, `main-service`, `nginx`.

Полные команды и шпаргалка: [Markdown/info.md](Markdown/info.md)

---

## Технологии

- **Backend:** Python 3.11, FastAPI, SQLModel, Uvicorn
- **БД:** PostgreSQL 15, Redis 7
- **Хранилище файлов:** Cloudflare R2 (S3-compatible)
- **Платежи:** Stripe
- **SMS:** SendBerry
- **Доставка:** DPD API, Omniva API
- **IMEI:** imei.info API
- **Auth:** JWT (HttpOnly cookies), Google OAuth 2.0, bcrypt
- **Очередь задач:** Taskiq + Redis
- **Инфраструктура:** Docker, Docker Compose, Nginx

---

## Переменные окружения

Все переменные — в файле `.env` в корне проекта. Шаблон: `.env.example`.

Ключевые группы:

```env
# PostgreSQL
POSTGRES_USER=postgres
POSTGRES_PASSWORD=...
POSTGRES_HOST=postgres
POSTGRES_DB=lais_marketplace

# JWT
SECRET_KEY=...
TOKEN_ALGORITHM=HS256

# Cloudflare R2
CF_R2_ACCESS_KEY_ID=...
CF_R2_SECRET_ACCESS_KEY=...

# Stripe
STRIPE_SECRET_KEY=sk_test_...
STRIPE_WEBHOOK_SECRET=whsec_...

# Delivery
DELIVERY_COST_DPD=2.99
DELIVERY_COST_OMNIVA=1.99

# Redis
REDIS_URL=redis://redis:6379/0

# Режим разработки
USE_TEST_MODE=false
PAYMENTS_TEST_MODE=true
```

---

## Документация

- [ARCHITECTURE.md](ARCHITECTURE.md) — общие паттерны, стандарты написания кода
- [Markdown/info.md](Markdown/info.md) — карта сервисов, команды, диаграммы
- [Markdown/DB_FULL_VIEW.md](Markdown/DB_FULL_VIEW.md) — полная схема БД
- `{service}/README.md` — документация каждого сервиса

---

**Дата последнего обновления:** 2026-06-16