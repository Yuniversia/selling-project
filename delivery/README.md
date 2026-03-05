# Delivery Service 🚚

Сервис доставки с интеграцией Omniva и DPD для маркетплейса LAIS.

## Описание

Сервис управляет процессом доставки заказов с момента создания до получения покупателем. Включает:

- ✅ Создание доставок для заказов
- ✅ Отслеживание статуса доставки
- ✅ Генерация трекинг-номеров
- ✅ Генерация 6-значных кодов получения
- ✅ Автоматическая отправка SMS уведомлений
- ✅ Интеграция с Omniva и DPD (имитация)
- ✅ История изменения статусов

## Статусы доставки

1. **created** - Доставка создана
2. **in_transit** - В пути к пункту выдачи
3. **at_pickup_point** - Прибыла в пункт выдачи (генерируется код, отправляется SMS)
4. **picked_up** - Получено покупателем (отправляется SMS с ссылкой на отзыв)
5. **cancelled** - Отменено
6. **returned** - Возвращено отправителю

## Процесс доставки

```
Order Created → Delivery Created → In Transit → At Pickup Point → Picked Up
                                                      ↓
                                            SMS: "Код: 123456"
                                                                       ↓
                                                          SMS: "Получено! Оставьте отзыв"
```

## API Endpoints

### Создание доставки
```bash
POST /api/v1/delivery/create
```

### Отслеживание по трекинг-номеру (публичный)
```bash
GET /api/v1/delivery/tracking/{tracking_number}
```

### Получение доставки по заказу
```bash
GET /api/v1/delivery/order/{order_id}
```

### Обновление статуса
```bash
PATCH /api/v1/delivery/{delivery_id}/status
```

### Имитация доставки (для тестирования)
```bash
# Начать доставку (created → in_transit)
POST /api/v1/delivery/{delivery_id}/simulate

# Доставить в пункт выдачи (генерирует код + отправляет SMS)
POST /api/v1/delivery/{delivery_id}/deliver-to-pickup-point

# Отметить как полученное (проверяет код + отправляет SMS с отзывом)
POST /api/v1/delivery/{delivery_id}/mark-picked-up?pickup_code=123456
```

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
PORT=7000
BACKEND_HOST=0.0.0.0

# External Services
NOTIFICATION_SERVICE_URL=http://notifications-service:6000
POSTS_SERVICE_URL=http://posts-service:3000
FRONTEND_URL=http://localhost:8080

# JWT
SECRET_KEY=My secret key
TOKEN_ALGORITHM=HS256

# Delivery providers (для будущего использования)
OMNIVA_API_KEY=
DPD_API_KEY=
DPD_API_SECRET=

# Simulation
USE_SIMULATION_MODE=true
TRANSIT_TIME_HOURS=24
PICKUP_WAIT_DAYS=7
```

## Запуск

### Docker (рекомендуется)
```bash
docker-compose up -d delivery-service
```

### Локально
```bash
cd delivery
pip install -r requirements.txt
python main.py
```

## Интеграция с другими сервисами

### Posts Service
После создания заказа posts-service должен вызвать:
```python
import httpx

delivery_data = {
    "order_id": order.id,
    "provider": "omniva",  # или "dpd", "pickup"
    "recipient_name": f"{order.buyer_first_name} {order.buyer_last_name}",
    "recipient_phone": order.buyer_phone,
    "recipient_email": order.buyer_email,
    "sender_name": seller.name,
    "sender_phone": seller.phone,
    "delivery_city": order.delivery_city,
    "delivery_address": order.delivery_address,
    "delivery_zip": order.delivery_zip
}

async with httpx.AsyncClient() as client:
    response = await client.post(
        "http://delivery-service:7000/api/v1/delivery/create",
        json=delivery_data
    )
```

### Notification Service
Delivery service автоматически отправляет уведомления через notification service:
- При доставке в пункт выдачи (код получения)
- При получении посылки (ссылка на отзыв)

## Имитация процесса доставки

Для тестирования используйте следующую последовательность:

```bash
# 1. Создайте доставку (обычно автоматически из posts-service)
curl -X POST http://localhost:7000/api/v1/delivery/create \
  -H "Content-Type: application/json" \
  -d '{
    "order_id": 1,
    "provider": "omniva",
    "recipient_name": "Иван Иванов",
    "recipient_phone": "+37120000000",
    "recipient_email": "ivan@example.com",
    "sender_name": "Продавец",
    "sender_phone": "+37120000001",
    "delivery_city": "Рига"
  }'

# 2. Начните доставку (created → in_transit)
curl -X POST http://localhost:7000/api/v1/delivery/1/simulate

# 3. Доставьте в пункт выдачи (in_transit → at_pickup_point)
#    Отправится SMS с кодом
curl -X POST http://localhost:7000/api/v1/delivery/1/deliver-to-pickup-point

# 4. Получите код из SMS или из API
curl http://localhost:7000/api/v1/delivery/order/1

# 5. Отметьте как полученное (at_pickup_point → picked_up)
#    Отправится SMS с ссылкой на отзыв
curl -X POST "http://localhost:7000/api/v1/delivery/1/mark-picked-up?pickup_code=123456"
```

## Будущие улучшения

- [ ] Реальная интеграция с Omniva API
- [ ] Реальная интеграция с DPD API
- [ ] Webhook endpoints для получения обновлений от провайдеров
- [ ] Автоматическое обновление статусов по расписанию
- [ ] Карта с пунктами выдачи
- [ ] Расчет стоимости доставки
- [ ] Печать этикеток для посылок
- [ ] История местоположения посылки

## Техническая информация

- **Язык**: Python 3.11
- **Фреймворк**: FastAPI
- **База данных**: PostgreSQL
- **ORM**: SQLModel
- **Порт**: 7000

## Документация API

После запуска сервиса документация доступна по адресу:
- Swagger UI: http://localhost:7000/delivery/docs
- ReDoc: http://localhost:7000/delivery/redoc
