# Delivery Service - Краткая справка

## 🚀 Быстрый старт

```bash
# Запуск через Docker
docker-compose up -d delivery-service

# Проверка
curl http://localhost:7000/api/v1/delivery/health

# Документация
open http://localhost:7000/delivery/docs
```

## 📦 Основные команды

### Создать доставку
```bash
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
```

### Отследить доставку
```bash
curl http://localhost:7000/api/v1/delivery/tracking/OM3K9L2M4N5P6Q
```

### Имитация процесса

```bash
# 1. Отправка (created → in_transit)
curl -X POST http://localhost:7000/api/v1/delivery/1/simulate

# 2. Доставка в пункт выдачи (генерирует код + SMS)
curl -X POST http://localhost:7000/api/v1/delivery/1/deliver-to-pickup-point

# 3. Получение товара (проверяет код + SMS с отзывом)
curl -X POST "http://localhost:7000/api/v1/delivery/1/mark-picked-up?pickup_code=123456"
```

## 🔄 Статусы

- `created` → Доставка создана
- `in_transit` → В пути (автоматически через 5 сек)
- `at_pickup_point` → В пункте выдачи (автоматически через 10 сек, генерируется код)
- `picked_up` → Получено

### 🤖 Автоматическая симуляция

Сервис автоматически переводит доставки по статусам:
- **created → in_transit**: через 5 секунд после создания
- **in_transit → at_pickup_point**: через 10 секунд после отправки (генерирует код + SMS)

Для мгновенного изменения используйте ручные команды выше.

## 📱 SMS уведомления

### При доставке в пункт выдачи:
```
Ваш заказ прибыл в пункт выдачи! 
Код получения: 123456. 
Трекинг: OM3K9L2M4N5P6Q.
```

### При получении:
```
Посылка получена! 
Спасибо за покупку. 
Оставьте отзыв: [ссылка]
```

## 🔗 Endpoints

- `POST /api/v1/delivery/create` - Создать доставку
- `GET /api/v1/delivery/tracking/{tracking}` - Отследить (публичный)
- `GET /api/v1/delivery/order/{order_id}` - Получить по заказу
- `PATCH /api/v1/delivery/{id}/status` - Обновить статус
- `POST /api/v1/delivery/{id}/simulate` - Начать доставку
- `POST /api/v1/delivery/{id}/deliver-to-pickup-point` - Доставить
- `POST /api/v1/delivery/{id}/mark-picked-up` - Получить

## 📚 Документация

- [README.md](README.md) - Общая информация
- [USAGE_GUIDE.md](USAGE_GUIDE.md) - Детальное руководство
- [INTEGRATION_GUIDE.md](INTEGRATION_GUIDE.md) - Интеграция с другими сервисами

## 🐛 Логи

```bash
docker logs lais-delivery -f
```

## ⚙️ Порты

- **Delivery Service**: 7000
- **Notifications**: 6000
- **Posts**: 3000
