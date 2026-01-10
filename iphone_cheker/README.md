# 📱 IMEI Checker Service v2.0

Микросервис для проверки IMEI iPhone с кешированием, test режимом и fallback логикой.

## 🚀 Возможности

- ✅ **Кеширование 7 дней** - результаты проверки кешируются в PostgreSQL
- ✅ **Test режим** - моковые данные для разработки и тестирования
- ✅ **Валидация IMEI** - проверка контрольной суммы по алгоритму Luhn
- ✅ **Детальное логирование** - все проверки записываются в БД
- ✅ **Прозрачность** - показывает источник данных (mock, cache, imei.info, imei.org)
- ✅ **Health check** - мониторинг состояния сервиса

## 📦 Структура

```
iphone_cheker/
├── main.py                    # FastAPI приложение
├── imei_service.py            # Основная логика проверки
├── models.py                  # Pydantic & SQLModel модели
├── database.py                # Подключение к PostgreSQL
├── configs.py                 # Конфигурация
├── utils.py                   # Валидация IMEI
├── requirements.txt           # Зависимости
├── Dockerfile                 # Docker образ
├── sources/
│   ├── base.py                # Базовый класс источников
│   └── mock.py                # Mock источник для test режима
└── README.md                  # Документация
```

## 🔧 API Endpoints

### POST /api/check-warranty

Проверка IMEI для imei-check.html страницы (полные данные с гарантией).

**Request:**
```json
{
  "imei": "123456789012345",
  "check_type": "warranty",
  "test_mode": true
}
```

**Response:**
```json
{
  "imei": "123456789012345",
  "model": "iPhone 15 Pro Max",
  "color": "Natural Titanium",
  "memory": 256,
  "serial_number": "F234567890",
  "purchase_date": "2024-06-15",
  "warranty_status": "Active",
  "warranty_expires": "2025-06-15",
  "icloud_status": "Clean",
  "simlock": "Unlocked",
  "fmi": false,
  "activation_lock": false,
  "source": "mock",
  "checked_at": "2026-01-09T12:00:00",
  "cached": false
}
```

### POST /api/check-basic

Проверка IMEI для создания поста (базовые данные устройства).

**Request:**
```json
{
  "imei": "123456789012345",
  "check_type": "basic",
  "test_mode": true
}
```

**Response:** Аналогично /api/check-warranty

### GET /api/check/{imei}

Legacy endpoint для обратной совместимости.

**Query Parameters:**
- `test_mode` (optional): принудительно включить test режим

### GET /health

Health check для Docker и мониторинга.

**Response:**
```json
{
  "status": "healthy",
  "service": "imei-checker",
  "version": "2.0.0",
  "test_mode": true
}
```

### GET /api/stats

Статистика проверок за последние 24 часа.

**Response:**
```json
{
  "total_checks": 150,
  "success_rate": 98.5,
  "avg_response_time_ms": 234.5,
  "by_source": {
    "mock": 120,
    "cache": 25,
    "imei_info": 3,
    "imei_org": 2
  },
  "test_mode_checks": 120
}
```

## 🔐 Переменные окружения

```bash
# База данных
DATABASE_URL=postgresql://postgres:pass@postgres:5432/lais_marketplace

# API ключи (для production режима)
IMEI_INFO_API_KEY=639d9e49-af3a-475d-98d1-c0b93defabf7  # UUID формат

# Кеширование
IMEI_CACHE_TTL_DAYS=7  # Срок хранения кеша (дни)

# Режим работы
USE_TEST_MODE=false  # false = production (реальный API), true = mock

# Таймауты
API_TIMEOUT_SECONDS=30  # Увеличено для внешних API

# JWT для интеграции
SECRET_KEY=your-secret-key
TOKEN_ALGORITHM=HS256

# Порт сервиса
PORT=5002
BACKEND_HOST=0.0.0.0
```

## 🐳 Docker

### Запуск через docker-compose

```bash
# Поднять все сервисы
docker-compose up -d

# Только IMEI сервис
docker-compose up -d imei-checker-service

# Пересобрать после изменений
docker-compose up -d --build imei-checker-service
```

### Логи

```bash
# Просмотр логов
docker-compose logs -f imei-checker-service

# Последние 100 строк
docker-compose logs --tail=100 imei-checker-service
```

## 🧪 Тестирование

### Проверка в test режиме

```bash
curl -X POST http://localhost:5002/api/check-basic \
  -H "Content-Type: application/json" \
  -d '{"imei": "123456789012345", "test_mode": true}'
```

### Проверка кеширования

```bash
# Первая проверка (live)
curl -X POST http://localhost:5002/api/check-basic \
  -H "Content-Type: application/json" \
  -d '{"imei": "123456789012345", "test_mode": true}'

# Вторая проверка (cached)
curl -X POST http://localhost:5002/api/check-basic \
  -H "Content-Type: application/json" \
  -d '{"imei": "123456789012345", "test_mode": true}'
```

### Проверка валидации

```bash
# Невалидный IMEI (неверная контрольная сумма)
curl -X POST http://localhost:5002/api/check-basic \
  -H "Content-Type: application/json" \
  -d '{"imei": "123456789012340", "test_mode": true}'
# Ожидается: 400 Bad Request
```

## 📊 База данных

### Таблицы

**imei_cache** - кеш проверенных IMEI (TTL: 7 дней)
```sql
CREATE TABLE imei_cache (
    imei VARCHAR(15) PRIMARY KEY,
    model VARCHAR,
    color VARCHAR,
    memory INTEGER,
    serial_number VARCHAR,
    purchase_date VARCHAR,
    warranty_status VARCHAR,
    warranty_expires VARCHAR,
    icloud_status VARCHAR,
    simlock VARCHAR,
    fmi BOOLEAN,
    activation_lock BOOLEAN,
    source VARCHAR,
    checked_at TIMESTAMP,
    expires_at TIMESTAMP
);
```

**imei_check_logs** - логи всех проверок
```sql
CREATE TABLE imei_check_logs (
    id SERIAL PRIMARY KEY,
    imei VARCHAR(15),
    source VARCHAR,
    check_type VARCHAR,
    success BOOLEAN,
    response_time_ms FLOAT,
    error_message TEXT,
    test_mode BOOLEAN,
    created_at TIMESTAMP
);
```

## 🔄 Интеграция

### Статус Production API

✅ **IMEI.info** - АКТИВНО (единственный источник)
- Service ID 12: APPLE Warranty Check ($0.04)
- Endpoint: https://dash.imei.info/api-sync/check/12/
- Статус: Работает и готов к production

❌ **IMEI.org** - ОТКЛЮЧЕНО
- Требуется DHRU FUSION account
- Не доступен через прямой API
- Может быть добавлен в будущем

### В Posts Service

```python
import httpx

async def create_post(imei: str):
    async with httpx.AsyncClient() as client:
        response = await client.post(
            "http://imei-checker-service:5002/api/check-basic",
            json={"imei": imei}  # test_mode больше не нужен в production
        )
        data = response.json()
        
        # Используем данные для создания поста
        post.model = data["model"]
        post.memory = data["memory"]
        post.imei_data_source = data["source"]  # "imei.info" в production
```

### В Frontend

```javascript
async function checkIMEI(imei) {
    const response = await fetch('https://test.yuniversia.eu/api/v1/imei/check-warranty', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({
            imei: imei
        })
    });
    
    const data = await response.json();
    console.log('Source:', data.source);  // "imei.info"
    console.log('Cached:', data.cached);  // true if from cache
}
```

## 📝 Логирование

Сервис использует structured logging:

```
2026-01-09 12:00:00 - IMEIService - INFO - ✅ Cache HIT for IMEI: 123456789012345 (source: mock)
2026-01-09 12:01:00 - IMEIService - INFO - ✅ Mock basic check successful: 123456789012345
2026-01-09 12:02:00 - IMEIService - INFO - 💾 Cached IMEI data: 123456789012345 (TTL: 7 days)
2026-01-09 12:03:00 - IMEIService - ERROR - ❌ Invalid IMEI checksum: 123456789012340
```

## 🚨 Обработка ошибок

- **400 Bad Request** - неверный формат IMEI или невалидная контрольная сумма
- **503 Service Unavailable** - все источники данных недоступны или API вернул ошибку
  - "Not enough balance" - недостаточно средств на балансе IMEI.info
  - "Invalid response" - неверный IMEI или устройство не в базе данных
  - "Rejected" - запрос отклонен API

## 🔮 Статус и Будущие улучшения

### ✅ Реализовано

- ✅ **Production API интеграция** - IMEI.info работает
- ✅ **Кеширование 7 дней** - PostgreSQL
- ✅ **Валидация IMEI** - Luhn algorithm
- ✅ **Детальное логирование** - structured logs
- ✅ **Health check** - Docker healthcheck
- ✅ **Test режим** - моковые данные для разработки

### 🔄 В разработке

- [ ] Реинтеграция IMEI.org (требует DHRU FUSION account)
- [ ] Fallback между несколькими источниками
- [ ] Retry логика с exponential backoff
- [ ] Rate limiting для защиты от абуза

### 💡 Будущие улучшения

- [ ] Prometheus metrics
- [ ] Grafana дашборды
- [ ] Webhook уведомления о низком балансе
- [ ] Автоматическое пополнение баланса

## 📄 Лицензия

Проект для внутреннего использования Lais marketplace.
