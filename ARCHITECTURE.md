# ARCHITECTURE.md — Общие паттерны и стандарты проекта LAIS Marketplace

Этот документ описывает архитектурные принципы, повторяющиеся паттерны кода и стандарты, которым следует весь проект. Перед добавлением нового сервиса или фичи — прочитай этот файл.

---

## 1. Цель проекта

LAIS Marketplace — платформа для безопасной покупки и продажи iPhone. Ключевые характеристики:
- Верификация устройств через IMEI
- Escrow-подобная система оплаты (деньги не уходят продавцу до получения товара)
- Встроенная доставка (DPD, Omniva, самовывоз)
- Система споров между покупателем и продавцом
- Real-time чат с push-уведомлениями

---

## 2. Архитектура системы

### Макро-архитектура

Проект построен как набор **независимых FastAPI микросервисов** за общим Nginx reverse proxy. Каждый сервис — отдельный Docker-контейнер с собственным кодом, зависимостями и Dockerfile.

**Единая точка входа:** Nginx роутит запросы по префиксу URL к нужному сервису.

**Общая база данных:** Все сервисы используют одну PostgreSQL базу `lais_marketplace`, но разделяют её по схемам (`public`, `posts_db`, `payments_db`). Это **shared database**, а не database-per-service.

**Межсервисное общение:** Только через HTTP REST + JSON внутри Docker сети. Сервисы обращаются друг к другу по DNS-имени Compose (`http://posts-service:3000`). Никакой шины сообщений нет — всё синхронно или через Taskiq (для фоновых задач posts-service).

### Когда добавлять новый сервис

Создавай новый сервис только если:
1. Функциональность имеет чёткую границу ответственности (SMS, доставка, IMEI)
2. Сервис может работать независимо и вызываться из нескольких других
3. Функциональность требует отдельного масштабирования

Иначе — добавляй в существующий сервис.

---

## 3. Структура сервиса — стандарт

Каждый сервис имеет одинаковую структуру:

```
{service}/
├── main.py                  # FastAPI app, lifespan, CORS, подключение роутеров
├── {service}_router.py      # Все эндпоинты (или несколько роутеров если их много)
├── {service}_service.py     # Бизнес-логика (функции, не классы)
├── models.py                # SQLModel таблицы + Pydantic схемы запросов/ответов
├── database.py              # engine, get_session(), create_db_and_tables()
├── configs.py               # Pydantic Settings, читает .env
├── Dockerfile
├── requirements.txt
└── README.md
```

**Важно:** бизнес-логика живёт в `{service}_service.py`, а не в роутере. Роутер только разбирает HTTP и вызывает сервис.

---

## 4. Паттерны кода

### 4.1 База данных

```python
# database.py — единый паттерн для всех сервисов
from sqlmodel import create_engine, SQLModel, Session
from typing import Generator

engine = create_engine(DATABASE_URL, echo=False)

def create_db_and_tables():
    SQLModel.metadata.create_all(engine)

def get_session() -> Generator[Session, None, None]:
    with Session(engine) as session:
        yield session
```

```python
# В роутере — Depends для инъекции сессии
from fastapi import Depends
from sqlmodel import Session

@router.get("/items")
def get_items(db: Session = Depends(get_session)):
    ...
```

### 4.2 Модели

Используй SQLModel, который объединяет SQLAlchemy и Pydantic:

```python
# Таблица в БД
class Order(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    status: str = Field(default="pending_payment")
    created_at: datetime = Field(default_factory=datetime.utcnow)

# Схема запроса (без table=True — только Pydantic)
class OrderCreate(SQLModel):
    post_id: int
    delivery_method: str

# Схема ответа
class OrderResponse(SQLModel):
    id: int
    status: str
    created_at: datetime
```

**Правило:** никогда не возвращай из эндпоинта объект таблицы напрямую — используй Response-схему. Это предотвращает утечку полей (паролей, внутренних данных).

### 4.3 Аутентификация

JWT хранится в HttpOnly cookie. Все бекенд-сервисы декодируют JWT **локально** через общий `SECRET_KEY` — без HTTP-запроса к auth-service.

```python
# Паттерн извлечения пользователя из cookie
def get_current_user(request: Request) -> dict:
    token = request.cookies.get("access_token")
    if not token:
        raise HTTPException(401, "Not authenticated")
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        return payload
    except JWTError:
        raise HTTPException(401, "Invalid token")

# В роутере
@router.get("/me")
def get_me(user: dict = Depends(get_current_user)):
    return user
```

Для опциональной авторизации (публичный эндпоинт, но поведение меняется если залогинен):

```python
def get_optional_user(request: Request) -> Optional[dict]:
    try:
        return get_current_user(request)
    except HTTPException:
        return None
```

### 4.4 Конфигурация

```python
# configs.py — Pydantic BaseSettings
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    postgres_user: str = "postgres"
    postgres_password: str = "pass"
    postgres_host: str = "postgres"
    postgres_port: int = 5432
    postgres_db: str = "lais_marketplace"
    
    secret_key: str = "dev-secret"
    
    class Config:
        env_file = "../../.env"  # путь к корневому .env
        extra = "ignore"

settings = Settings()
```

### 4.5 Межсервисные HTTP-запросы

Всегда используй `httpx.AsyncClient` для async, `httpx.Client` для sync:

```python
async def call_notifications(order_id: int, phone: str):
    async with httpx.AsyncClient(timeout=10.0) as client:
        resp = await client.post(
            f"{NOTIFICATION_SERVICE_URL}/api/v1/notifications/order-paid",
            json={"order_id": order_id, "phone": phone}
        )
        resp.raise_for_status()
```

**Правило:** межсервисные вызовы оборачивай в try/except. Если notifications-service недоступен — это не должно ломать основной флоу (логируй ошибку, но продолжай выполнение).

### 4.6 Обработка ошибок

```python
from fastapi import HTTPException

# Стандартный способ возврата ошибки
raise HTTPException(status_code=404, detail="Order not found")
raise HTTPException(status_code=403, detail="Access denied")
raise HTTPException(status_code=422, detail="Invalid IMEI format")

# Для валидации входных данных — Pydantic делает это автоматически
```

### 4.7 Health Check

Каждый сервис обязан иметь `GET /health`:

```python
@router.get("/health")
def health_check():
    return {"status": "healthy", "service": "posts"}
```

Docker Compose использует эти эндпоинты для healthcheck проб.

---

## 5. Конвенции именования

| Что | Стиль | Пример |
|---|---|---|
| Файлы | snake_case | `order_router.py`, `delivery_service.py` |
| Функции | snake_case | `create_order()`, `get_user_by_id()` |
| Классы/модели | PascalCase | `Order`, `DeliveryStatus`, `OrderCreate` |
| Переменные | snake_case | `order_id`, `buyer_phone` |
| Константы | UPPER_SNAKE | `MAX_IMAGES`, `DEFAULT_CURRENCY` |
| API endpoints | kebab-case | `/api/v1/pickup-points`, `/api/v1/order-paid` |
| Таблицы БД | snake_case lowercase | `order`, `delivery_status_history`, `push_subscriptions` |
| Env variables | UPPER_SNAKE | `STRIPE_SECRET_KEY`, `DELIVERY_COST_DPD` |

---

## 6. API Design

### Версионирование

Все публичные API используют prefix `/api/v1/`:
- `GET /api/v1/posts`
- `POST /api/v1/orders`
- `GET /api/v1/delivery/pickup-points`

Исключение: auth-service использует `/auth/` (исторически).

### HTTP методы

| Действие | Метод |
|---|---|
| Получить список | GET |
| Получить один объект | GET /{id} |
| Создать | POST |
| Обновить частично | PATCH |
| Удалить | DELETE |

### Коды ответов

- `200` — успех, данные в теле
- `201` — создан
- `202` — принято (для async операций вроде payments)
- `400` — неверный запрос / валидация
- `401` — не авторизован
- `403` — запрещено (авторизован, но нет прав)
- `404` — не найдено
- `422` — ошибка валидации Pydantic (автоматически)

---

## 7. База данных — правила

1. **Одна БД, разные схемы.** Не создавай отдельные БД для сервисов — используй схемы PostgreSQL (`posts_db`, `payments_db`).

2. **Не удаляй записи.** Используй статусы: `cancelled`, `deleted`, `rejected`. Физическое удаление — только для технических таблиц (cache, logs).

3. **Timestamp на каждой таблице.** Всегда добавляй `created_at` (и `updated_at` где нужно). Используй `datetime.utcnow`.

4. **Не используй Enum в БД.** Храни статусы как `VARCHAR` со строковыми значениями. Enum в Python (для валидации) — ок.

5. **Внешние ключи.** Delivery service намеренно не имеет FK на order — это допустимо для слабо связанных сервисов. Но если сервисы живут в одной схеме — FK обязательны.

6. **Миграции.** SQLModel создаёт таблицы через `create_db_and_tables()` при старте. Изменения схемы делаются через SQL-файлы в `migrations/`.

---

## 8. Файлы и изображения

- **Cloudflare R2** — единственное хранилище для файлов (не локальная ФС).
- Posts-service: изображения товаров через Cloudflare Images Direct Upload.
- Chat-service: файлы сообщений через R2.
- Никогда не храни файлы в контейнере — при перезапуске всё потеряется.

---

## 9. Безопасность

- Пароли хешируются через **bcrypt** (cost factor 12+).
- JWT токены хранятся в **HttpOnly cookies**, не в localStorage.
- Stripe webhook подписи верифицируются через `STRIPE_WEBHOOK_SECRET`.
- IMEI API ключи никогда не логируются.
- Все эндпоинты, изменяющие данные — требуют авторизации.
- Публичные эндпоинты (список товаров, карточка) — не требуют авторизации, но обогащаются данными если пользователь залогинен.

---

## 10. Тестирование и режим разработки

- `USE_TEST_MODE=true` в `.env` включает моковый режим для IMEI (не тратит API credits).
- `PAYMENTS_TEST_MODE=true` использует Stripe test ключи.
- `USE_POSTGRES=false` переключает на SQLite (для быстрой локальной разработки без Docker).
- Тестовые эндпоинты (`/api/v1/test/...`) присутствуют только в dev-режиме.

---

## 11. Добавление нового сервиса — чеклист

- [ ] Создать папку `{service}/` со стандартной структурой файлов
- [ ] Добавить `Dockerfile` (шаблон из любого существующего сервиса)
- [ ] Добавить сервис в `docker-compose.yml` с healthcheck
- [ ] Добавить роутинг в `nginx/nginx.conf`
- [ ] Добавить URL сервиса в `.env` и `.env.example`
- [ ] Написать `README.md` для сервиса
- [ ] Добавить в таблицу в этом файле и в `README.md`
- [ ] Добавить в `Markdown/info.md` (межсервисные вызовы, таблицы БД)

---

**Дата последнего обновления:** 2026-06-16