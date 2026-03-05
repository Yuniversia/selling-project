# Notification Service

Микросервис для отправки SMS и Email уведомлений через SendPulse API.

## Основные возможности

- ✉️ Отправка Email уведомлений через SendPulse SMTP
- 📱 Отправка SMS уведомлений через SendPulse SMS API
- 🔄 Автоматический retry при ошибках (до 3 попыток)
- 📊 История всех отправленных уведомлений
- 🎨 Поддержка шаблонов уведомлений
- 🔗 Интеграция с системой заказов

## API Endpoints

### POST /api/v1/notifications/order-created
Отправка уведомлений при создании заказа:
- Продавцу: SMS + Email о новом заказе
- Покупателю: Email с подтверждением и ссылкой для отслеживания

### POST /api/v1/notifications/order-delivered
Отправка уведомления после доставки заказа:
- Покупателю: Email со ссылкой для оценки продавца

### GET /api/v1/notifications/history
Получение истории отправленных уведомлений с фильтрами:
- `order_id` - по номеру заказа
- `email` - по email получателя
- `phone` - по телефону получателя
- `limit` - максимальное количество записей

### GET /api/v1/notifications/health
Проверка работоспособности сервиса

## Переменные окружения

```env
# Database
USE_POSTGRES=true
POSTGRES_USER=postgres
POSTGRES_PASSWORD=pass
POSTGRES_HOST=postgres
POSTGRES_PORT=5432
POSTGRES_DB=lais_marketplace

# Server
PORT=6000
BACKEND_HOST=0.0.0.0
FRONTEND_URL=https://test.yuniversia.eu

# SendPulse API
SENDPULSE_API_ID=your_api_id
SENDPULSE_API_SECRET=your_api_secret

# JWT (optional, для защиты API)
SECRET_KEY=My secret key
TOKEN_ALGORITHM=HS256
```

## Типы уведомлений

### order_created_seller
Уведомление продавцу о новом заказе
- SMS: Краткая информация о заказе
- Email: Детальная информация с ссылкой на заказ

### order_created_buyer
Подтверждение заказа покупателю
- Email: Детали заказа и ссылка для отслеживания

### order_review_request
Запрос на отзыв после получения заказа
- Email: Ссылка для оценки продавца

## Шаблоны уведомлений

Шаблоны хранятся в таблице `notification_template` и поддерживают переменные:

**Доступные переменные:**
- `{seller_name}` - Имя продавца
- `{buyer_name}` - Имя покупателя
- `{product_name}` - Название товара
- `{product_model}` - Модель товара
- `{order_price}` - Цена заказа
- `{order_id}` - Номер заказа
- `{tracking_url}` - Ссылка для отслеживания
- `{review_url}` - Ссылка для отзыва
- `{frontend_url}` - URL фронтенда

## Структура БД

### notification_log
История отправленных уведомлений:
- `notification_type` - Тип уведомления
- `channel` - Канал (email/sms/both)
- `recipient_email` / `recipient_phone` - Получатель
- `status` - Статус доставки (pending/sent/failed/retry)
- `retry_count` - Количество попыток
- `error_message` - Сообщение об ошибке
- `external_id` - ID из SendPulse API

### notification_template
Шаблоны уведомлений:
- `notification_type` - Тип уведомления (уникальный)
- `email_subject` / `email_body` - Шаблоны для email
- `sms_text` - Шаблон для SMS
- `is_active` - Активен ли шаблон

## Пример использования

```python
import requests

# Отправка уведомления о новом заказе
response = requests.post(
    "http://localhost:6000/api/v1/notifications/order-created",
    json={
        "order_id": 123,
        "seller_name": "Иван Иванов",
        "seller_email": "seller@example.com",
        "seller_phone": "+37120000000",
        "buyer_name": "Петр Петров",
        "buyer_email": "buyer@example.com",
        "product_name": "iPhone 14 Pro",
        "product_model": "128GB Space Black",
        "order_price": 899.99,
        "delivery_method": "DPD",
        "tracking_url": "https://test.yuniversia.eu/orders/123"
    }
)
```

## Запуск в development режиме

```bash
cd notifications
pip install -r requirements.txt
python main.py
```

Документация API: http://localhost:6000/notifications/docs

## Интеграция с другими сервисами

Notification service вызывается из `posts/order_router.py`:
- При создании заказа (`/create`)
- При оплате заказа (`/pay`)
- При доставке (`mark_as_delivered`)
- При получении заказа (`confirm_receipt`)

## Обработка ошибок

- Автоматический retry до 3 раз с exponential backoff
- Все попытки логируются в БД
- При неудаче все равно возвращается успех, если хотя бы одно уведомление отправлено
- Детальные логи ошибок для отладки
