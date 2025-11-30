# 🚀 LAIS Marketplace - Документация по запуску

## 📋 Содержание
1. [Архитектура проекта](#архитектура-проекта)
2. [Требования](#требования)
3. [Быстрый старт](#быстрый-старт)
4. [Разработка](#разработка)
5. [Production развертывание](#production-развертывание)
6. [Полезные команды](#полезные-команды)
7. [Troubleshooting](#troubleshooting)

---

## 🏗 Архитектура проекта

Проект состоит из 4 Docker контейнеров:

```
┌─────────────────────────────────────────────────────┐
│                  LAIS Marketplace                   │
└─────────────────────────────────────────────────────┘
                         │
        ┌────────────────┼────────────────┐
        │                │                │
   ┌────▼────┐     ┌────▼────┐     ┌────▼────┐
   │  Main   │     │  Auth   │     │  Posts  │
   │ Service │────▶│ Service │◀────│ Service │
   │ :8080   │     │ :8000   │     │ :3000   │
   └─────────┘     └────┬────┘     └────┬────┘
                        │                │
                        └────────┬───────┘
                                 │
                          ┌──────▼──────┐
                          │ PostgreSQL  │
                          │   :5432     │
                          └─────────────┘
```

### Сервисы:

1. **PostgreSQL** (`:5432`) - База данных
   - Все таблицы: `user`, `iphone`, `bought`
   - Persistent хранилище через Docker volume

2. **Auth Service** (`:8000`) - Аутентификация
   - Регистрация, авторизация
   - JWT токены
   - Управление пользователями
   - API Docs: http://localhost:8000/auth/docs

3. **Posts Service** (`:3000`) - Объявления
   - CRUD объявлений о продаже iPhone
   - Система покупок
   - Статистика просмотров
   - API Docs: http://localhost:3000/docs

4. **Main Service** (`:8080`) - Frontend
   - HTML страницы (Jinja2 шаблоны)
   - Статические файлы (CSS, JS)
   - Web: http://localhost:8080

---

## 💻 Требования

### Минимальные требования:
- **Docker Desktop** 20.10+
- **Docker Compose** 1.29+
- **Windows 10/11** с WSL2 (для Windows)
- **4GB RAM** (минимум 2GB для Docker)
- **10GB свободного места**

### Установка Docker:

**Windows:**
1. Скачайте Docker Desktop: https://www.docker.com/products/docker-desktop
2. Установите и запустите
3. Включите WSL2 backend

**Linux:**
```bash
# Ubuntu/Debian
sudo apt-get update
sudo apt-get install docker.io docker-compose

# Запуск Docker
sudo systemctl start docker
sudo systemctl enable docker
```

**macOS:**
```bash
# Через Homebrew
brew install --cask docker
```

---

## 🚀 Быстрый старт

### 1. Клонирование репозитория
```bash
git clone <repository-url>
cd ss.lv
```

### 2. Настройка переменных окружения

Файл `.env` уже создан с настройками по умолчанию:
```env
USE_POSTGRES=true
POSTGRES_USER=postgres
POSTGRES_PASSWORD=pass
POSTGRES_HOST=localhost
POSTGRES_PORT=5432
POSTGRES_DB=lais_marketplace
```

### 3. Запуск всего проекта одной командой

```bash
docker-compose up -d
```

Эта команда:
- ✅ Создаст PostgreSQL базу данных
- ✅ Запустит Auth Service
- ✅ Запустит Posts Service
- ✅ Запустит Main Service (Frontend)
- ✅ Настроит сеть между контейнерами
- ✅ Применит миграции (создаст таблицы)

### 4. Проверка статуса

```bash
docker-compose ps
```

Должны быть запущены 4 контейнера:
```
NAME                STATUS              PORTS
lais-postgres       Up (healthy)        0.0.0.0:5432->5432/tcp
lais-auth           Up                  0.0.0.0:8000->8000/tcp
lais-posts          Up                  0.0.0.0:3000->3000/tcp
lais-main           Up                  0.0.0.0:8080->8080/tcp
```

### 5. Открытие приложения

Откройте в браузере:
- **Frontend**: http://localhost:8080
- **Auth API Docs**: http://localhost:8000/auth/docs
- **Posts API Docs**: http://localhost:3000/docs

### 6. Остановка проекта

```bash
docker-compose down
```

Для удаления с данными:
```bash
docker-compose down -v  # Удалит и PostgreSQL данные
```

---

## 🛠 Разработка

### Запуск в режиме разработки (с hot reload)

Docker volumes уже настроены для синхронизации локального кода с контейнерами. Изменения применяются автоматически.

### Просмотр логов

```bash
# Все сервисы
docker-compose logs -f

# Конкретный сервис
docker-compose logs -f auth-service
docker-compose logs -f posts-service
docker-compose logs -f main-service
docker-compose logs -f postgres
```

### Перезапуск конкретного сервиса

```bash
docker-compose restart auth-service
docker-compose restart posts-service
docker-compose restart main-service
```

### Пересборка после изменения зависимостей

```bash
# Пересборка всех сервисов
docker-compose build

# Пересборка конкретного сервиса
docker-compose build auth-service

# Пересборка и перезапуск
docker-compose up -d --build
```

### Запуск команд внутри контейнера

```bash
# Открыть bash в контейнере
docker-compose exec auth-service bash
docker-compose exec posts-service bash

# Запустить Python скрипт
docker-compose exec posts-service python migrate_to_postgres.py

# Подключиться к PostgreSQL
docker-compose exec postgres psql -U postgres -d lais_marketplace
```

### Установка новых зависимостей

1. Добавьте пакет в `requirements.txt` или `requirments.txt`
2. Пересоберите контейнер:
   ```bash
   docker-compose build auth-service  # или posts-service
   docker-compose up -d auth-service
   ```

---

## 🚀 Production развертывание

### 1. Обновите `.env` для production

```env
USE_POSTGRES=true
POSTGRES_USER=postgres
POSTGRES_PASSWORD=<STRONG_PASSWORD>  # Измените!
POSTGRES_HOST=postgres
POSTGRES_PORT=5432
POSTGRES_DB=lais_marketplace
```

### 2. Используйте production docker-compose

Создайте `docker-compose.prod.yml`:
```yaml
version: '3.8'

services:
  postgres:
    image: postgres:15-alpine
    restart: always
    # ... (без volumes для локальных файлов)

  auth-service:
    build:
      context: ./auth
    restart: always
    # Убираем volumes с локальными файлами

  posts-service:
    build:
      context: ./posts
    restart: always
    # Убираем volumes с локальными файлами

  main-service:
    build:
      context: ./main
    restart: always
    # Убираем volumes с локальными файлами
```

### 3. Запуск в production

```bash
docker-compose -f docker-compose.prod.yml up -d
```

### 4. Настройка Nginx (опционально)

Для использования доменного имени и SSL:

```nginx
server {
    listen 80;
    server_name your-domain.com;

    location / {
        proxy_pass http://localhost:8080;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }

    location /auth/ {
        proxy_pass http://localhost:8000/auth/;
    }

    location /api/v1/ {
        proxy_pass http://localhost:3000/api/v1/;
    }
}
```

---

## 📝 Полезные команды

### Docker Compose

```bash
# Запуск в фоне
docker-compose up -d

# Запуск с просмотром логов
docker-compose up

# Остановка
docker-compose down

# Остановка с удалением volumes
docker-compose down -v

# Просмотр статуса
docker-compose ps

# Просмотр логов
docker-compose logs -f [service-name]

# Перезапуск сервиса
docker-compose restart [service-name]

# Пересборка
docker-compose build

# Пересборка и запуск
docker-compose up -d --build
```

### PostgreSQL

```bash
# Подключение к БД
docker-compose exec postgres psql -U postgres -d lais_marketplace

# Список таблиц
docker-compose exec postgres psql -U postgres -d lais_marketplace -c "\dt"

# Бэкап базы данных
docker-compose exec postgres pg_dump -U postgres lais_marketplace > backup.sql

# Восстановление
docker-compose exec -T postgres psql -U postgres -d lais_marketplace < backup.sql

# Просмотр содержимого таблицы
docker-compose exec postgres psql -U postgres -d lais_marketplace -c "SELECT * FROM \"user\" LIMIT 5;"
```

### Очистка Docker

```bash
# Удалить неиспользуемые контейнеры
docker container prune

# Удалить неиспользуемые образы
docker image prune

# Удалить всё неиспользуемое (осторожно!)
docker system prune -a

# Удалить volumes
docker volume prune
```

---

## 🔧 Troubleshooting

### Проблема: Порт уже занят

**Ошибка:**
```
Error: Bind for 0.0.0.0:8000 failed: port is already allocated
```

**Решение:**
```bash
# Windows
netstat -ano | findstr :8000
taskkill /PID <PID> /F

# Linux/Mac
lsof -i :8000
kill -9 <PID>

# Или измените порт в docker-compose.yml:
ports:
  - "8001:8000"  # Внешний:Внутренний
```

### Проблема: PostgreSQL не запускается

**Решение:**
```bash
# Проверка логов
docker-compose logs postgres

# Удаление volume и пересоздание
docker-compose down -v
docker-compose up -d postgres
```

### Проблема: Сервис не видит базу данных

**Ошибка:**
```
Connection refused (0x0000274D/10061)
```

**Решение:**
1. Проверьте, что PostgreSQL запущен:
   ```bash
   docker-compose ps postgres
   ```

2. Проверьте healthcheck:
   ```bash
   docker-compose exec postgres pg_isready -U postgres
   ```

3. Проверьте переменные окружения в `.env`:
   ```env
   POSTGRES_HOST=postgres  # Должен быть "postgres", не "localhost"!
   ```

### Проблема: Изменения в коде не применяются

**Решение:**
```bash
# Пересоберите контейнер
docker-compose up -d --build [service-name]

# Или полная пересборка
docker-compose down
docker-compose build --no-cache
docker-compose up -d
```

### Проблема: Ошибка при импорте модулей

**Ошибка:**
```
ModuleNotFoundError: No module named 'fastapi'
```

**Решение:**
```bash
# Пересоберите контейнер (зависимости устанавливаются при сборке)
docker-compose build [service-name]
docker-compose up -d [service-name]
```

### Проблема: Не хватает памяти

**Ошибка:**
```
docker: Error response from daemon: OCI runtime create failed
```

**Решение:**
1. Откройте Docker Desktop
2. Settings → Resources
3. Увеличьте Memory до 4GB+
4. Apply & Restart

### Проблема: Таблицы не созданы

**Решение:**
```bash
# Запустите миграцию вручную
docker-compose exec posts-service python migrate_to_postgres.py

# Или проверьте логи при запуске
docker-compose logs posts-service | grep -i "table"
```

---

## 📊 Мониторинг

### Проверка здоровья сервисов

```bash
# Health checks
curl http://localhost:8000/health  # Auth
curl http://localhost:3000/health  # Posts
curl http://localhost:8080/health  # Main
```

### Использование ресурсов

```bash
# Статистика контейнеров
docker stats

# Использование места
docker system df
```

---

## 🎯 Следующие шаги

1. ✅ Проект запущен в Docker
2. ⏭ Настройте CI/CD (GitHub Actions)
3. ⏭ Добавьте мониторинг (Prometheus + Grafana)
4. ⏭ Настройте резервное копирование БД
5. ⏭ Добавьте тесты (pytest)
6. ⏭ Настройте SSL сертификаты (Let's Encrypt)

---

## 📞 Поддержка

Если возникли проблемы:
1. Проверьте логи: `docker-compose logs -f`
2. Проверьте статус: `docker-compose ps`
3. Перезапустите: `docker-compose restart`
4. Пересоберите: `docker-compose up -d --build`

---

**Версия:** 1.0.0  
**Дата обновления:** 2025-11-29
