# 🏪 LAIS Marketplace

Платформа для покупки и продажи iPhone с системой аутентификации, объявлениями и покупками.

## � Документация развертывания

### 🖥️ Локальная разработка
- **[Быстрый старт](#-быстрый-старт-3-шага)** - запуск на локальной машине
- **[Docker Guide](DOCKER_GUIDE.md)** - полная документация Docker

### 🌐 Production развертывание
- **[Arch Linux + Nginx](ARCH-LINUX-DEPLOYMENT.md)** - полная инструкция для production
- **[Быстрый старт Nginx](QUICK-START-NGINX.md)** - для серверов с существующим Nginx
- **[Deployment Guide](DEPLOYMENT.md)** - детальная документация развертывания

### 🔧 Скрипты автоматизации
- `start-prod.sh` - запуск в production
- `stop-prod.sh` - остановка с бэкапом
- `backup.sh` - резервное копирование БД
- `setup-nginx.sh` - настройка Nginx на сервере

---

## �🚀 Быстрый старт (3 шага)

### 1. Установите Docker Desktop
- Windows/Mac: https://www.docker.com/products/docker-desktop
- Linux: `sudo apt-get install docker.io docker-compose`

### 2. Запустите проект
```bash
docker-compose up -d
```

### 3. Откройте в браузере
- **Frontend**: http://localhost:8080
- **Auth API**: http://localhost:8000/auth/docs
- **Posts API**: http://localhost:3000/docs

## 📁 Структура проекта

```
ss.lv/
├── auth/              # Сервис аутентификации (JWT, пользователи)
│   ├── Dockerfile
│   ├── main.py
│   ├── auth_router.py
│   ├── auth_service.py
│   ├── models.py
│   └── database.py
│
├── posts/             # Сервис объявлений (iPhone, покупки)
│   ├── Dockerfile
│   ├── main.py
│   ├── post_router.py
│   ├── bought_router.py
│   ├── models.py
│   └── database.py
│
├── main/              # Frontend (HTML шаблоны)
│   ├── Dockerfile
│   ├── main.py
│   ├── frontend_router.py
│   └── templates/
│
├── docker-compose.yml # Конфигурация всех сервисов
├── .env               # Переменные окружения
├── Makefile           # Команды для управления
└── DOCKER_GUIDE.md    # Полная документация
```

## 🎯 Основные команды

### Docker Compose
```bash
# Запуск всех сервисов
docker-compose up -d

# Остановка
docker-compose down

# Просмотр логов
docker-compose logs -f

# Статус сервисов
docker-compose ps

# Перезапуск
docker-compose restart
```

### Makefile (альтернатива)
```bash
# Показать все команды
make help

# Запустить проект
make up

# Остановить
make down

# Логи
make logs

# Проверка здоровья
make health

# Подключиться к БД
make db-shell
```

## 🏗 Архитектура

```
┌─────────────────────────────────────────────────────┐
│              LAIS Marketplace                       │
│  http://localhost:8080                             │
└──────────────┬──────────────────────────────────────┘
               │
     ┌─────────┼─────────┐
     │         │         │
┌────▼────┐ ┌─▼───────┐ ┌─▼──────────┐
│  Main   │ │  Auth   │ │   Posts    │
│ :8080   │ │ :8000   │ │   :3000    │
│Frontend │ │JWT/Users│ │iPhone/Buy  │
└─────────┘ └────┬────┘ └─────┬──────┘
                 │            │
                 └──────┬─────┘
                        │
                 ┌──────▼──────┐
                 │ PostgreSQL  │
                 │    :5432    │
                 └─────────────┘
```

## 🔧 Технологии

- **Backend**: FastAPI, SQLModel, PostgreSQL
- **Frontend**: Jinja2, HTML, CSS, JavaScript
- **Auth**: JWT tokens, bcrypt
- **Deploy**: Docker, Docker Compose
- **Database**: PostgreSQL 15

## 📊 Функционал

### Auth Service (`:8000`)
- ✅ Регистрация пользователей
- ✅ Авторизация (JWT токены)
- ✅ Профиль пользователя
- ✅ Управление аватарами
- ✅ API документация: `/auth/docs`

### Posts Service (`:3000`)
- ✅ CRUD объявлений о продаже iPhone
- ✅ Система покупок
- ✅ Статистика просмотров
- ✅ Фильтры и поиск
- ✅ API документация: `/docs`

### Main Service (`:8080`)
- ✅ Главная страница
- ✅ Страница товара
- ✅ Профиль пользователя
- ✅ Форма создания объявления
- ✅ Модальные окна (покупка, контакты)

## 🗄 База данных

### Таблицы:
- `user` - Пользователи (auth)
- `iphone` - Объявления (posts)
- `bought` - Покупки (posts)
- `postreport` - Жалобы на объявления (moderation)
- `postview` - Уникальные просмотры (analytics)

### Подключение:
```bash
# Через Docker
docker-compose exec postgres psql -U postgres -d lais_marketplace

# Локально (если PostgreSQL установлен)
psql -U postgres -h localhost -p 5432 -d lais_marketplace
```

## 👑 Управление администраторами

### Быстрый способ (Python скрипт):
```bash
# Установка зависимостей (один раз)
pip install tabulate

# Показать всех пользователей
python admin_manager.py list

# Назначить админа
python admin_manager.py set admin username

# Назначить модератора
python admin_manager.py set support username

# Убрать права
python admin_manager.py set regular username
```

### GUI программы для PostgreSQL:
- **pgAdmin 4** (рекомендуется): https://www.pgadmin.org/download/
- **DBeaver**: https://dbeaver.io/download/
- **TablePlus**: https://tableplus.com/

**Подробная инструкция**: [ADMIN_GUIDE.md](./ADMIN_GUIDE.md)

## 🔐 Переменные окружения (`.env`)

```env
# PostgreSQL
USE_POSTGRES=true
POSTGRES_USER=postgres
POSTGRES_PASSWORD=pass
POSTGRES_HOST=postgres
POSTGRES_PORT=5432
POSTGRES_DB=lais_marketplace
```

## 🚨 Troubleshooting

### Порт занят
```bash
# Найти процесс
netstat -ano | findstr :8000

# Убить процесс (Windows)
taskkill /PID <PID> /F

# Или изменить порт в docker-compose.yml
```

### БД не подключается
```bash
# Проверить статус PostgreSQL
docker-compose ps postgres

# Проверить логи
docker-compose logs postgres

# Перезапустить
docker-compose restart postgres
```

### Таблицы не созданы
```bash
# Запустить миграцию вручную
docker-compose exec posts-service python migrate_to_postgres.py
```

## 📖 Документация

- **Полная документация**: [DOCKER_GUIDE.md](./DOCKER_GUIDE.md)
- **API Auth**: http://localhost:8000/auth/docs
- **API Posts**: http://localhost:3000/docs

## 🎯 Development

### Локальная разработка (без Docker)

1. Установите PostgreSQL локально
2. Создайте виртуальные окружения:
   ```bash
   cd auth && python -m venv auth
   cd ../posts && python -m venv posts
   ```
3. Установите зависимости:
   ```bash
   pip install -r requirements.txt  # или requirments.txt для auth
   ```
4. Запустите сервисы:
   ```bash
   # Терминал 1
   cd auth && uvicorn main:app --port 8000
   
   # Терминал 2
   cd posts && uvicorn main:app --port 3000
   
   # Терминал 3
   cd main && uvicorn main:app --port 8080
   ```

### Hot Reload

Docker volumes настроены автоматически - изменения в коде применяются без перезапуска.

## 🤝 Contributing

1. Fork проекта
2. Создайте feature branch (`git checkout -b feature/AmazingFeature`)
3. Commit изменений (`git commit -m 'Add some AmazingFeature'`)
4. Push в branch (`git push origin feature/AmazingFeature`)
5. Откройте Pull Request

## 📝 License

MIT License

## 👥 Authors

- **Yuniversia** - [GitHub](https://github.com/Yuniversia)

## 🌟 Roadmap

- [ ] Добавить тесты (pytest)
- [ ] CI/CD с GitHub Actions
- [ ] Мониторинг (Prometheus + Grafana)
- [ ] Резервное копирование БД
- [ ] SSL сертификаты
- [ ] Admin панель
- [ ] Email уведомления
- [ ] Чат между покупателем и продавцом
- [ ] Рейтинги и отзывы
- [ ] Мобильное приложение

---

**Версия:** 1.0.0  
**Дата:** 2025-11-29

