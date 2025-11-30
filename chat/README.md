# 💬 Chat Service - WebSocket Чат

Real-time чат система для маркетплейса Lais с поддержкой зарегистрированных и анонимных пользователей.

---

## 🎯 Возможности

### Для покупателей:
- ✅ **Быстрый старт чата** - нажать кнопку "Чат" на странице товара
- ✅ **Анонимный режим** - чат без регистрации (UUID в localStorage)
- ✅ **Real-time общение** - мгновенная доставка сообщений через WebSocket
- ✅ **Индикатор печатания** - видно когда продавец пишет ответ
- ✅ **История сообщений** - все сообщения сохраняются

### Для продавцов:
- ✅ **Централизованный inbox** - все чаты в профиле
- ✅ **Группировка по товарам** - чаты отсортированы по объявлениям
- ✅ **Счетчик непрочитанных** - видно сколько новых сообщений
- ✅ **Последнее сообщение** - превью последнего сообщения в списке
- ✅ **Онлайн статус** - видно кто сейчас в чате

---

## 🏗️ Архитектура

```
chat/
├── main.py                 # FastAPI приложение
├── chat_router.py          # REST API + WebSocket endpoints
├── chat_service.py         # Бизнес-логика чатов
├── websocket_manager.py    # Управление WebSocket соединениями
├── models.py               # SQLModel модели (Chat, Message)
├── database.py             # Подключение к PostgreSQL
├── requirements.txt        # Python зависимости
├── Dockerfile              # Docker образ
└── migrations/
    └── 001_create_chat_tables.sql  # SQL миграция
```

---

## 📊 База данных

### Таблица `chat`
```sql
id              SERIAL PRIMARY KEY
iphone_id       INTEGER (FK -> iphone.id)
seller_id       INTEGER (FK -> user.id)
buyer_id        VARCHAR(255)  -- ID или UUID
buyer_is_registered BOOLEAN
created_at      TIMESTAMP
updated_at      TIMESTAMP
```

### Таблица `message`
```sql
id              SERIAL PRIMARY KEY
chat_id         INTEGER (FK -> chat.id)
sender_id       VARCHAR(255)
sender_is_registered BOOLEAN
message_text    TEXT
is_read         BOOLEAN
created_at      TIMESTAMP
```

---

## 🚀 Запуск

### 1. Применить миграцию БД

```bash
# Подключиться к PostgreSQL
psql -U postgres -d lais_marketplace

# Выполнить миграцию
\i chat/migrations/001_create_chat_tables.sql
```

### 2. Локальный запуск (для разработки)

```bash
cd chat
pip install -r requirements.txt
uvicorn main:app --reload --port 4000
```

### 3. Docker запуск

```bash
# Из корня проекта
docker-compose up -d chat-service

# Проверить статус
docker-compose ps

# Логи
docker-compose logs -f chat-service
```

---

## 📡 API Endpoints

### REST API

#### `POST /api/chat/chats`
Создать новый чат
```json
{
  "iphone_id": 1,
  "seller_id": 2,
  "buyer_id": "user_123",
  "buyer_is_registered": true
}
```

#### `GET /api/chat/chats/my?user_id={id}&is_seller={bool}`
Получить чаты пользователя
- `is_seller=false` - чаты где пользователь покупатель
- `is_seller=true` - чаты где пользователь продавец

#### `GET /api/chat/chats/seller/{seller_id}/grouped`
Получить чаты продавца, сгруппированные по объявлениям
```json
{
  "123": [  // iphone_id
    {
      "id": 1,
      "buyer_id": "uuid-xxx",
      "unread_count": 3,
      "last_message": "Привет!",
      "last_message_time": "2025-11-30T10:00:00"
    }
  ]
}
```

#### `GET /api/chat/chats/{chat_id}/messages?limit=100&offset=0`
Получить сообщения чата с пагинацией

#### `POST /api/chat/chats/{chat_id}/read?user_id={id}`
Пометить сообщения как прочитанные

#### `DELETE /api/chat/chats/{chat_id}`
Удалить чат

---

### WebSocket

#### `WS /api/chat/ws/{chat_id}?user_id={id}`

**Подключение:**
```javascript
const ws = new WebSocket('ws://localhost:4000/api/chat/ws/1?user_id=user_123');
```

**Отправка сообщения:**
```json
{
  "type": "message",
  "message_text": "Привет, товар еще актуален?",
  "sender_is_registered": true
}
```

**Индикатор печатания:**
```json
{
  "type": "typing",
  "is_typing": true
}
```

**Пометка прочитанным:**
```json
{
  "type": "read"
}
```

**Получение сообщений:**
```json
{
  "type": "message",
  "message": {
    "id": 42,
    "sender_id": "seller_1",
    "message_text": "Да, актуален!",
    "created_at": "2025-11-30T10:05:00"
  }
}
```

---

## 🎨 Frontend Integration

### 1. Подключить JavaScript модули

```html
<!-- В product.html и profile.html -->
<script src="{{ url_for('static', path='/chat.js') }}" defer></script>
<script src="{{ url_for('static', path='/seller-chats.js') }}" defer></script>
```

### 2. Открыть чат (product.html)

```javascript
// Для покупателя
document.getElementById('openChatBtn').addEventListener('click', () => {
    window.chatManager.openChat(sellerId, iphoneId);
});
```

### 3. Отобразить чаты продавца (profile.html)

```javascript
// Автоматически загружается при наличии id="profilePage"
window.sellerChatsManager = new SellerChatsManager();
```

---

## 🔧 Конфигурация

### Переменные окружения

```env
# В docker-compose.yml или .env
POSTGRES_USER=postgres
POSTGRES_PASSWORD=pass
POSTGRES_HOST=postgres
POSTGRES_PORT=5432
POSTGRES_DB=lais_marketplace
DOCKER_ENV=true
PORT=4000
```

### CORS настройки

В `chat/main.py`:
```python
allow_origins=[
    "http://localhost:8080",  # Main frontend
    "http://localhost:8000",  # Auth service
    "http://localhost:3000",  # Posts service
    "http://localhost:4000",  # Chat service
    "http://127.0.0.1:8080",
    # ... добавьте production домены
]
```

---

## 🧪 Тестирование

### 1. Health Check
```bash
curl http://localhost:4000/health
# {"status":"healthy","service":"chat"}
```

### 2. Создать тестовый чат
```bash
curl -X POST http://localhost:4000/api/chat/chats \
  -H "Content-Type: application/json" \
  -d '{
    "iphone_id": 1,
    "seller_id": 1,
    "buyer_id": "test-buyer-uuid",
    "buyer_is_registered": false
  }'
```

### 3. WebSocket тест (в браузере)
```javascript
const ws = new WebSocket('ws://localhost:4000/api/chat/ws/1?user_id=test');
ws.onopen = () => console.log('Connected!');
ws.onmessage = (e) => console.log('Message:', JSON.parse(e.data));
ws.send(JSON.stringify({
    type: 'message',
    message_text: 'Test message',
    sender_is_registered: false
}));
```

---

## 📦 Зависимости

```txt
fastapi==0.121.3
uvicorn[standard]==0.34.0
sqlmodel==0.0.24
psycopg2-binary==2.9.10
python-multipart==0.0.20
websockets==14.1
```

---

## 🐛 Troubleshooting

### WebSocket не подключается
```bash
# Проверить порт
docker-compose ps
netstat -an | findstr :4000

# Проверить логи
docker-compose logs -f chat-service

# Проверить CORS
# Убедитесь что frontend origin добавлен в allow_origins
```

### Сообщения не сохраняются
```bash
# Проверить подключение к БД
docker exec -it lais-chat psql -U postgres -d lais_marketplace -c "SELECT * FROM chat LIMIT 5;"

# Проверить миграции
docker exec -it lais-postgres psql -U postgres -d lais_marketplace -c "\dt"
```

### Чаты не загружаются в профиле
```bash
# Проверить JavaScript в консоли браузера (F12)
# Проверить что seller-chats.js подключен
# Проверить что есть id="profilePage" в body
```

---

## 🔐 Безопасность

### Реализовано:
- ✅ Валидация chat_id перед подключением к WebSocket
- ✅ Проверка существования чата
- ✅ Санитизация HTML в сообщениях
- ✅ Ограничение длины сообщений (2000 символов)

### TODO:
- ⏳ Rate limiting для отправки сообщений
- ⏳ Блокировка спама
- ⏳ Модерация сообщений
- ⏳ Авторизация через JWT токены

---

## 📈 Мониторинг

### Метрики
```python
# Количество активных соединений
len(manager.active_connections)

# Количество пользователей онлайн в чате
len(manager.get_active_users(chat_id))
```

### Логи
```bash
docker-compose logs -f chat-service | grep -E "connected|disconnected|error"
```

---

## 🚀 Production Deployment

### 1. Обновить CORS
```python
# В chat/main.py
allow_origins=[
    "https://yourdomain.com",
    "https://www.yourdomain.com",
]
```

### 2. Добавить SSL для WebSocket (wss://)
```nginx
# В nginx.conf
location /api/chat/ws/ {
    proxy_pass http://chat-service:4000;
    proxy_http_version 1.1;
    proxy_set_header Upgrade $http_upgrade;
    proxy_set_header Connection "upgrade";
    proxy_set_header Host $host;
}
```

### 3. Увеличить workers
```dockerfile
# В Dockerfile
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "4000", "--workers", "4"]
```

---

## 📝 Changelog

### v1.0.0 (2025-11-30)
- ✅ Базовая функциональность чата
- ✅ WebSocket real-time обмен сообщениями
- ✅ Поддержка анонимных пользователей
- ✅ UI для покупателей и продавцов
- ✅ Группировка чатов по объявлениям
- ✅ Счетчик непрочитанных сообщений
- ✅ Индикатор печатания
- ✅ Docker интеграция

---

## 🤝 Contributing

При добавлении новых фич:
1. Обновить модели в `models.py`
2. Добавить методы в `chat_service.py`
3. Создать endpoints в `chat_router.py`
4. Обновить frontend JS
5. Добавить тесты
6. Обновить этот README

---

**Версия:** 1.0.0  
**Автор:** Lais Team  
**Дата:** 30.11.2025
