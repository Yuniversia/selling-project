# Auth Service

Сервис аутентификации и управления пользователями. Выдаёт JWT токены, обрабатывает Google OAuth, хранит профили.

**Порт:** 8080 (внутри Docker: 8000)
**API docs:** http://localhost:8000/auth/docs

---

## Структура файлов

```
auth/
├── main.py           # FastAPI app, CORS, подключение роутера, init БД
├── auth_router.py    # Все эндпоинты (/auth/*)
├── auth_service.py   # Бизнес-логика: JWT, bcrypt, запросы к БД
├── models.py         # User, UserCreate, UserLogin, Token и др.
├── database.py       # Подключение к PostgreSQL, get_session()
├── configs.py        # Читает .env: SECRET_KEY, GOOGLE_CLIENT_ID и др.
├── Dockerfile
└── requirements.txt
```

---

## Модели данных

### Таблица `user`

```sql
id              SERIAL PRIMARY KEY
username        VARCHAR UNIQUE NOT NULL
email           VARCHAR UNIQUE NOT NULL
hashed_password VARCHAR
status          VARCHAR DEFAULT 'active'    -- active / banned
user_type       VARCHAR DEFAULT 'regular'  -- regular / admin / support
avatar_url      VARCHAR
name            VARCHAR
surname         VARCHAR
phone           VARCHAR
posts_count     INTEGER DEFAULT 0
sells_count     INTEGER DEFAULT 0
rating          FLOAT DEFAULT 0.0
created_at      TIMESTAMP DEFAULT NOW()
```

### Pydantic схемы

| Схема | Назначение |
|---|---|
| `UserCreate` | Регистрация (username, email, password) |
| `UserLogin` | Логин (username/email + password) |
| `Token` | Ответ с access_token + refresh_token |
| `PublicUser` | Публичный профиль (без email, phone, password) |
| `PublicUserMinimal` | Минималистичный профиль (id, username, avatar) |

---

## API Endpoints

| Метод | URL | Описание | Auth |
|---|---|---|---|
| POST | `/auth/register` | Регистрация нового пользователя | Нет |
| POST | `/auth/login` | Логин, возвращает JWT в cookies | Нет |
| GET | `/auth/refresh` | Обновить access_token по refresh_token | Cookie |
| POST | `/auth/logout` | Очистить cookies | Cookie |
| GET | `/auth/me` | Профиль текущего пользователя | Cookie |
| PUT | `/auth/me` | Обновить профиль (name, phone, avatar) | Cookie |
| GET | `/auth/user?id={id}` | Публичный профиль пользователя | Нет |
| GET | `/auth/google/login` | Редирект на Google OAuth | Нет |
| GET | `/auth/google/callback` | Колбэк Google OAuth | Нет |
| GET | `/health` | Health check | Нет |

---

## Ключевые функции (`auth_service.py`)

**`create_access_token(data, expires_delta)`**
Создаёт JWT access_token. Payload включает `sub` (user_id), `username`, `user_type`, `exp`.

**`create_refresh_token(data)`**
Создаёт refresh_token с более долгим TTL (обычно 7 дней).

**`verify_password(plain, hashed)`**
Сравнивает через bcrypt. Никогда не логировать `plain`.

**`get_password_hash(password)`**
Хеширует через bcrypt. Всегда использовать перед сохранением.

**`decode_token(token)`**
Декодирует и валидирует JWT. Бросает HTTPException 401 если невалидный.

**`get_user_by_username(db, username)`** / **`get_user_by_email(db, email)`**
Поиск пользователя в БД. Возвращает `None` если не найден.

---

## Аутентификация в других сервисах

Другие сервисы **не делают HTTP-запрос к auth-service** для проверки токена. Они декодируют JWT локально:

```python
import jwt

def get_current_user(request: Request) -> dict:
    token = request.cookies.get("access_token")
    payload = jwt.decode(token, SECRET_KEY, algorithms=[TOKEN_ALGORITHM])
    return payload  # {sub: user_id, username: ..., user_type: ...}
```

Это работает потому что все сервисы используют один `SECRET_KEY` из `.env`.

---

## Конфигурация (`.env`)

```env
SECRET_KEY=your-jwt-secret
TOKEN_ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=30
REFRESH_TOKEN_EXPIRE_DAYS=7

GOOGLE_CLIENT_ID=...
GOOGLE_CLIENT_SECRET=...

POSTGRES_USER=postgres
POSTGRES_PASSWORD=pass
POSTGRES_HOST=postgres
POSTGRES_PORT=5432
POSTGRES_DB=lais_marketplace

COOKIE_SECURE=false   # true в production (HTTPS)
FRONTEND_URL=http://localhost:8080
```

---

## Запуск

```bash
# Docker (рекомендуется)
docker-compose up -d auth-service
docker-compose logs -f auth-service

# Локально
cd auth
pip install -r requirements.txt
uvicorn main:app --port 8000 --reload
```

---

## Связи с другими сервисами

- **posts-service** читает таблицу `user` напрямую через общую БД (получает данные продавца)
- **chat-service** хранит FK на `user.id`
- Все сервисы используют `SECRET_KEY` для декодирования JWT без HTTP-вызовов

**Дата последнего обновления:** 2026-06-16