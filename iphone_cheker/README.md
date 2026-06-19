# IMEI Checker Service

Проверяет iPhone по IMEI номеру: модель, память, цвет, статус iCloud, гарантия. Кеширует результаты на 7 дней чтобы не тратить API-кредиты повторно. Поддерживает test mode с моковыми данными.

**Порт:** 5002 (внутри Docker), 5001 (проброс наружу в некоторых конфигах)
**API docs:** http://localhost:5002/docs

---

## Структура файлов

```
iphone_cheker/
├── main.py                 # FastAPI app, JWT auth для admin эндпоинтов
├── imei_service.py         # Основная логика: кеш, fallback по источникам, логирование
├── models.py               # IMEICheckRequest, IMEICheckResponse, IMEICacheEntry
├── database.py             # PostgreSQL, get_session()
├── configs.py              # API ключи, cache TTL, test mode
├── utils.py                # Валидация IMEI по алгоритму Luhn
├── sources/
│   ├── base.py             # Абстрактный класс IMEISource
│   ├── imei_info.py        # imei.info API ($0.04 за проверку)
│   ├── imei_org.py         # imei.org API (требует DHRU FUSION, отключён)
│   ├── imeicheck_net.py    # imeicheck.net API
│   └── mock.py             # Моковые данные для разработки
├── Dockerfile
└── requirements.txt
```

---

## Модели данных

### Таблица `imei_cache`

```
imei             VARCHAR(15) PRIMARY KEY
model            VARCHAR
color            VARCHAR
memory           INTEGER
serial_number    VARCHAR
purchase_date    VARCHAR
warranty_status  VARCHAR    -- Active / Expired / Out of Warranty
warranty_expires VARCHAR
icloud_status    VARCHAR    -- Clean / Lost / Stolen
simlock          VARCHAR    -- Unlocked / Locked
fmi              BOOLEAN    -- Find My iPhone включён
activation_lock  BOOLEAN
source           VARCHAR    -- imei.info / mock / imeicheck.net
checked_at       TIMESTAMP
expires_at       TIMESTAMP  -- checked_at + IMEI_CACHE_TTL_DAYS
```

### Таблица `imei_check_logs`

```
id               SERIAL PRIMARY KEY
imei             VARCHAR(15)
source           VARCHAR
check_type       VARCHAR    -- basic / warranty
success          BOOLEAN
response_time_ms FLOAT
error_message    TEXT
test_mode        BOOLEAN
created_at       TIMESTAMP
```

---

## API Endpoints

| Метод | URL | Описание | Auth |
|---|---|---|---|
| POST | `/api/check-basic` | Базовая проверка (модель, память, цвет) | JWT |
| POST | `/api/check-warranty` | Полная проверка (+ гарантия, iCloud, simlock) | JWT |
| GET | `/api/check/{imei}` | Legacy GET эндпоинт | JWT |
| GET | `/api/stats` | Статистика за 24 часа | JWT |
| GET | `/balance` | Баланс API аккаунта | JWT Admin |
| GET | `/health` | Health check | Нет |

---

## Логика проверки

```
1. Валидация IMEI (алгоритм Luhn) — если неверный, сразу 400

2. Проверка кеша в БД (imei_cache)
   → если есть и expires_at > now() — возвращаем из кеша (source: cache)

3. Если USE_TEST_MODE=true — возвращаем mock данные

4. Запрос к imei.info API
   → при ошибке — пробуем imeicheck.net (fallback)
   → если все источники недоступны — 503

5. Сохраняем результат в кеш на TTL дней

6. Логируем в imei_check_logs
```

---

## Источники данных

| Источник | Статус | Цена | Примечание |
|---|---|---|---|
| `imei.info` | Активен | $0.04/запрос | Service ID 12: Apple Warranty Check |
| `imeicheck.net` | Fallback | Зависит от плана | Используется если imei.info недоступен |
| `imei.org` | Отключён | — | Требует DHRU FUSION account |
| `mock` | Dev only | Бесплатно | Включается через USE_TEST_MODE=true |

---

## Валидация IMEI (алгоритм Luhn)

```python
# utils.py
def validate_imei(imei: str) -> bool:
    if len(imei) != 15 or not imei.isdigit():
        return False
    # Алгоритм Luhn
    digits = [int(d) for d in imei]
    for i in range(1, 15, 2):
        digits[i] *= 2
        if digits[i] > 9:
            digits[i] -= 9
    return sum(digits) % 10 == 0
```

---

## Конфигурация (`.env`)

```env
# API ключи
IMEI_INFO_API_KEY=your-uuid-api-key
IMEICHECK_NET_API_KEY=...

# Кеш
IMEI_CACHE_TTL_DAYS=7

# Режим: false = production (реальные API), true = mock данные
USE_TEST_MODE=false

# Таймаут запросов к внешним API
API_TIMEOUT_SECONDS=30

# JWT (такой же как у остальных сервисов)
SECRET_KEY=...
TOKEN_ALGORITHM=HS256

# PostgreSQL
POSTGRES_USER=postgres
POSTGRES_PASSWORD=pass
POSTGRES_HOST=postgres
POSTGRES_DB=lais_marketplace
```

---

## Использование из posts-service

```python
import httpx

async def check_imei_for_post(imei: str) -> dict:
    async with httpx.AsyncClient(timeout=30.0) as client:
        response = await client.post(
            "http://imei-checker-service:5002/api/check-basic",
            json={"imei": imei, "check_type": "basic"},
            headers={"Authorization": f"Bearer {INTERNAL_JWT}"}
        )
        if response.status_code == 400:
            raise ValueError("Invalid IMEI")
        return response.json()
        # {"model": "iPhone 15 Pro Max", "memory": 256, "color": "...", "source": "imei.info"}
```

---

## Запуск

```bash
# Docker
docker-compose up -d imei-checker-service
docker-compose logs -f imei-checker-service

# Тест в test mode
curl -X POST http://localhost:5002/api/check-basic \
  -H "Content-Type: application/json" \
  -d '{"imei": "353879234567890", "check_type": "basic"}'

# Локально
cd iphone_cheker
pip install -r requirements.txt
uvicorn main:app --port 5002 --reload
```

---

## Ошибки

| Код | Причина |
|---|---|
| 400 | Невалидный IMEI (неверная контрольная сумма или формат) |
| 401 | Нет или невалидный JWT |
| 503 | Все источники недоступны (проверь баланс на imei.info) |

**Дата последнего обновления:** 2026-06-16