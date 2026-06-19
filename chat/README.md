# Chat Service

Real-time чат между покупателями и продавцами. WebSocket для мгновенной доставки сообщений, Web Push для уведомлений, Cloudflare R2 для хранения файлов.

**Порт:** 4000
**API docs:** http://localhost:4000/docs

---

## Структура файлов

```
chat/
├── main.py                 # FastAPI app, lifespan, CORS, init БД
├── chat_router.py          # REST API чатов + WebSocket эндпоинт /ws
├── chat_service.py         # Бизнес-логика: создание чатов, сообщения, непрочитанные
├── websocket_manager.py    # Пул WebSocket-соединений, broadcast по chat_id
├── push_service.py         # Web Push уведомления через VAPID
├── cloudflare_r2.py        # Загрузка файлов в R2
├── models.py               # Chat, Message, PushSubscription + Pydantic схемы
├── push_models.py          # PushSubscriptionCreate, PushSubscriptionResponse
├── database.py             # PostgreSQL, get_session()
├── migrations/
│   └── 001_create_chat_tables.sql
├── Dockerfile
└── requirements.txt
```

---

## Модели данных

### Таблица `chat`

```sql
id                    SERIAL PRIMARY KEY
iphone_id             INTEGER FK -> iphone.id
seller_id             INTEGER FK -> user.id
buyer_id              VARCHAR(255)     -- int (registered) или UUID (anonymous)
buyer_is_registered   BOOLEAN
anonymous_buyer_number INTEGER          -- порядковый номер анонима (#1, #2...)
support_joined        BOOLEAN DEFAULT false
support_user_id       INTEGER
is_hidden_by_buyer    BOOLEAN DEFAULT false
is_hidden_by_seller   BOOLEAN DEFAULT false
created_at            TIMESTAMP
updated_at            TIMESTAMP
```

### Таблица `message`

```sql
id                    SERIAL PRIMARY KEY
chat_id               INTEGER FK -> chat.id
sender_id             VARCHAR(255)
sender_is_registered  BOOLEAN
message_text          TEXT
message_type          VARCHAR  -- text / image / file / system
file_url              VARCHAR
file_name             VARCHAR
file_size             INTEGER
is_read               BOOLEAN DEFAULT false
created_at            TIMESTAMP
```

### Таблица `push_subscriptions`

```sql
id          SERIAL PRIMARY KEY
user_id     VARCHAR(255) UNIQUE
endpoint    VARCHAR UNIQUE
auth_key    VARCHAR
p256dh_key  VARCHAR
is_active   BOOLEAN DEFAULT true
created_at  TIMESTAMP
```

---

## API Endpoints

### Чаты

| Метод | URL | Описание |
|---|---|---|
| POST | `/api/chat/chats` | Создать или найти существующий чат |
| GET | `/api/chat/chats/my` | Мои чаты (покупатель или продавец) |
| GET | `/api/chat/chats/find` | Найти чат по iphone_id + buyer_id |
| GET | `/api/chat/chats/{id}/messages` | История сообщений (пагинация) |
| POST | `/api/chat/chats/{id}/read` | Отметить сообщения прочитанными |
| DELETE | `/api/chat/chats/{id}` | Скрыть чат |
| POST | `/api/chat/chats/hide-for-order` | Скрыть чат после завершения заказа (вызов от posts) |

### Push уведомления

| Метод | URL | Описание |
|---|---|---|
| POST | `/api/chat/push/subscribe` | Подписаться на Web Push |
| DELETE | `/api/chat/push/unsubscribe` | Отписаться |

### WebSocket

| URL | Описание |
|---|---|
| `WS /ws?chat_id={id}&user_id={id}` | Подключение к чату |
| `WS /ws/seller/{seller_id}` | Продавец слушает все свои чаты |

### Файлы

| Метод | URL | Описание |
|---|---|---|
| POST | `/api/chat/upload` | Загрузить файл/изображение в R2 |

---

## WebSocket протокол

### Подключение

```javascript
const ws = new WebSocket('ws://localhost:4000/ws?chat_id=1&user_id=42');
```

### Отправка сообщения

```json
{
  "type": "message",
  "message_text": "Привет, товар ещё доступен?",
  "sender_is_registered": true
}
```

### Отправка файла

```json
{
  "type": "file",
  "file_url": "https://r2.example.com/chat/uuid.jpg",
  "file_name": "photo.jpg",
  "file_size": 204800,
  "message_type": "image"
}
```

### Индикатор печатания

```json
{ "type": "typing", "is_typing": true }
```

### Входящее сообщение (сервер → клиент)

```json
{
  "type": "message",
  "message": {
    "id": 42,
    "sender_id": "1",
    "message_text": "Да, доступен!",
    "message_type": "text",
    "is_read": false,
    "created_at": "2026-06-16T10:00:00"
  }
}
```

---

## Web Push уведомления

Используется стандарт Web Push + VAPID. Ключи задаются через env:

```env
VAPID_PUBLIC_KEY=...
VAPID_PRIVATE_KEY=...
VAPID_CLAIM_EMAIL=admin@example.com
```

Генерация ключей:
```bash
python -c "from py_vapid import Vapid; v = Vapid(); v.generate_keys(); print(v.public_key, v.private_key)"
```

Push отправляется когда:
- Получатель сообщения не подключён к WebSocket
- Сообщение имеет тип `text`, `image` или `file`

---

## Конфигурация (`.env`)

```env
POSTGRES_USER=postgres
POSTGRES_PASSWORD=pass
POSTGRES_HOST=postgres
POSTGRES_DB=lais_marketplace

CF_R2_ACCESS_KEY_ID=...
CF_R2_SECRET_ACCESS_KEY=...
CHAT_CF_R2_BUCKET_NAME=...
CHAT_CF_R2_ENDPOINT=...

VAPID_PUBLIC_KEY=...
VAPID_PRIVATE_KEY=...
VAPID_CLAIM_EMAIL=admin@yuniversia.eu

POSTS_SERVICE_URL=http://posts-service:3000
```

---

## Запуск

```bash
# Docker
docker-compose up -d chat-service
docker-compose logs -f chat-service

# Локально
cd chat
pip install -r requirements.txt
uvicorn main:app --port 4000 --reload
```

---

## Связи с другими сервисами

| Сервис | Вызов | Когда |
|---|---|---|
| posts-service | GET /api/v1/posts/{iphone_id} | Проверка активности объявления перед созданием чата |

Входящие вызовы:
- `posts-service` → POST `/api/chat/chats/hide-for-order` после завершения заказа

---

## Анонимные пользователи

Покупатель без регистрации получает UUID, сохранённый в `localStorage`. Этот UUID используется как `buyer_id`. Для продавца анонимы показываются как "Покупатель #1", "Покупатель #2" — порядковые номера в рамках одного объявления.

**Дата последнего обновления:** 2026-06-16