# Main Service (Frontend)

Отдаёт HTML страницы через Jinja2 шаблоны, статические файлы (CSS, JS) и генерирует sitemap. Является "склейкой" между пользователем и API-сервисами — рендерит страницы с данными, полученными от других сервисов.

**Порт:** 8080
**URL:** http://localhost:8080

---

## Структура файлов

```
main/
├── main.py                    # FastAPI app, монтирование статики, подключение роутеров
├── frontend_router.py         # HTML страницы и несколько прокси-эндпоинтов
├── sitemap_generator.py       # Генерация sitemap.xml из объявлений
├── translations.py            # i18n поддержка (переводы строк)
├── configs.py                 # URL сервисов, настройки
├── templates/
│   ├── base.html              # Базовый шаблон с хедером и футером
│   ├── index.html             # Главная страница (список объявлений)
│   ├── product.html           # Карточка товара
│   ├── profile.html           # Профиль пользователя
│   ├── create-post.html       # Форма создания объявления
│   ├── my-sales.html          # Страница продавца (мои продажи)
│   ├── order-tracking.html    # Трекинг заказа покупателем
│   ├── admin.html             # Административная панель
│   └── static/
│       ├── *.css              # Стили
│       ├── *.js               # JavaScript модули
│       └── icons/             # SVG иконки
├── Dockerfile
└── requirements.txt
```

---

## Страницы

| URL | Шаблон | Описание |
|---|---|---|
| `/` | `index.html` | Главная: список объявлений с фильтрами |
| `/product/{id}` | `product.html` | Карточка товара: фото, описание, IMEI, кнопки купить/чат |
| `/profile/{id}` | `profile.html` | Профиль пользователя: объявления, рейтинг |
| `/my-sales` | `my-sales.html` | Кабинет продавца: заказы, чаты, статистика |
| `/order/{id}` | `order-tracking.html` | Трекинг заказа для покупателя |
| `/create` | `create-post.html` | Создание объявления: IMEI → форма → фото |
| `/admin` | `admin.html` | Админ-панель: пользователи, жалобы, споры |
| `/sitemap.xml` | — | Динамический sitemap |

---

## API Endpoints (прокси и утилиты)

| Метод | URL | Описание |
|---|---|---|
| GET | `/api/v1/delivery-costs` | Стоимости доставки (из configs) |
| GET | `/api/check-imei` | Прокси к imei-checker-service |
| GET | `/health` | Health check |
| GET | `/sitemap.xml` | Генерируемый sitemap |

---

## Как работает рендеринг

Страницы рендерятся **на сервере** через Jinja2. Данные могут быть:

1. **Server-side**: `frontend_router.py` делает HTTP-запросы к API сервисам при генерации страницы и передаёт данные в шаблон через `TemplateResponse`.

2. **Client-side**: JavaScript делает fetch/XHR к API после загрузки страницы. Это основной паттерн — большинство динамики через JS.

```python
# Пример server-side рендеринга
@router.get("/product/{post_id}")
async def product_page(post_id: int, request: Request):
    # Данные подгружаются JS после загрузки страницы
    return templates.TemplateResponse("product.html", {
        "request": request,
        "post_id": post_id,
        "api_url": settings.api_url
    })
```

---

## JavaScript модули

Основные JS файлы в `templates/static/`:

| Файл | Назначение |
|---|---|
| `auth.js` | Регистрация/логин, хранение состояния авторизации |
| `chat.js` | WebSocket чат для покупателя |
| `seller-chats.js` | Inbox продавца, группировка чатов по объявлениям |
| `product.js` | Карточка товара: галерея, покупка, форма заказа |
| `create-post.js` | Шаги создания объявления: IMEI → детали → фото |
| `admin-api.js` | Функции для административной панели |
| `order-tracking.js` | Трекинг и статусы заказа |

---

## Конфигурация (`.env`)

```env
# URL для JavaScript (доступны из браузера)
FRONTEND_URL=http://localhost:8080
AUTH_SERVICE_URL=http://localhost:8000
POSTS_SERVICE_URL=http://localhost:3000
CHAT_SERVICE_URL=http://localhost:4000

# URL для server-side запросов (внутри Docker)
POSTS_SERVICE_INTERNAL_URL=http://posts-service:3000
IMEI_SERVICE_INTERNAL_URL=http://imei-checker-service:5002

# Стоимости доставки (дублируются для фронтенда)
DELIVERY_COST_PICKUP=0
DELIVERY_COST_DPD=2.99
DELIVERY_COST_OMNIVA=1.99
```

---

## Sitemap

`sitemap_generator.py` запрашивает список всех активных объявлений из `posts-service` и генерирует XML sitemap для SEO. Обновляется при каждом запросе `/sitemap.xml`.

---

## Запуск

```bash
# Docker
docker-compose up -d main-service
docker-compose logs -f main-service

# Локально
cd main
pip install -r requirements.txt
uvicorn main:app --port 8080 --reload
```

---

## Статика

Статические файлы монтируются из `templates/static/`:

```python
# main.py
app.mount("/static", StaticFiles(directory="templates/static"), name="static")
```

В шаблонах: `{{ url_for('static', path='/style.css') }}`

**Дата последнего обновления:** 2026-06-16