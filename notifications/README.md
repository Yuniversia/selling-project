# Notification Service

Микросервис для отправки SMS уведомлений через SendBerry API.

## Основные возможности

- 📱 Отправка SMS уведомлений через SendBerry SMS API
- 🔄 Автоматический retry при ошибках (до 3 попыток)
- 📊 История всех отправленных уведомлений
- 🎨 Поддержка шаблонов уведомлений
- 🔗 Интеграция с системой заказов

## API Endpoints

### POST /api/v1/notifications/order-created
Отправка уведомлений при создании заказа:
- Продавцу: SMS о новом заказе
- Покупателю: Email с подтверждением (или SMS, если настроено)

### POST /api/v1/notifications/order-delivered
Отправка уведомления после доставки заказа:
- Покупателю: Уведомление о доставке

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

# SendBerry API
SENDBERRY_API_KEY=your_api_key
SENDBERRY_API_NAME=your_access_name
SENDBERRY_API_PASSWORD=your_access_password
SENDBERRY_SENDER_ID=SMS Inform  # Default for test mode, or your verified sender ID

# JWT (optional, для защиты API)
SECRET_KEY=My secret key
TOKEN_ALGORITHM=HS256
```

## Режим работы SendBerry

### Test/Limited Mode
В тестовом режиме или при использовании free credits:
- Необходимо верифицировать sender ID "from" или использовать дефолтный "SMS Inform"
- SMS можно отправлять только на ваш собственный верифицированный номер
- Необходимо верифицировать номера получателей в настройках SendBerry Portal

### Production Mode
После активации полного доступа:
- Можно использовать собственный Sender ID (alphanumeric или номер телефона)
- Отправка SMS на любые номера без ограничений
- Webhook для отслеживания статуса доставки (опционально)

### Важно
- Номера телефонов должны быть в международном формате E.164: `+37120000000`
- Текст сообщений поддерживает UTF-8 (включая кириллицу)
- Email уведомления в текущей версии не поддерживаются (только SMS)

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
- `external_id` - ID из SendBerry API (campaign ID)

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
