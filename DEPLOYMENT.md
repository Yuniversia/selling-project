# 🚀 Развертывание проекта на Arch Linux с доменом 3-го уровня

## 📋 Содержание
1. [Требования](#требования)
2. [Установка на Arch Linux](#установка-на-arch-linux)
3. [Настройка домена](#настройка-домена)
4. [Развертывание на сервере](#развертывание-на-сервере)
5. [SSL сертификаты (Let's Encrypt)](#ssl-сертификаты)
6. [Мониторинг и логи](#мониторинг-и-логи)
7. [Обслуживание](#обслуживание)

---

## 🔧 Требования

### Минимальные требования сервера:
- **CPU**: 2 ядра
- **RAM**: 4 GB
- **Disk**: 20 GB SSD
- **OS**: Arch Linux (последняя версия)
- **Network**: Статический IP адрес
- **Domain**: Домен 3-го уровня (например: `api.your-domain.com`)

### Необходимое ПО:
- Docker & Docker Compose
- Git
- Nginx
- Certbot (для SSL)
- PostgreSQL (через Docker)

---

## 📦 Установка на Arch Linux

### 1. Обновление системы

```bash
sudo pacman -Syu
```

### 2. Установка Docker

```bash
# Установка Docker
sudo pacman -S docker docker-compose

# Запуск Docker
sudo systemctl start docker
sudo systemctl enable docker

# Добавление пользователя в группу docker
sudo usermod -aG docker $USER

# Перелогиньтесь для применения изменений
newgrp docker

# Проверка установки
docker --version
docker-compose --version
```

### 3. Установка дополнительных пакетов

```bash
# Git для клонирования репозитория
sudo pacman -S git

# Nginx (для reverse proxy)
sudo pacman -S nginx

# Certbot для SSL сертификатов
sudo pacman -S certbot certbot-nginx

# Утилиты
sudo pacman -S htop net-tools
```

### 4. Настройка Firewall (UFW)

```bash
# Установка UFW
sudo pacman -S ufw

# Разрешаем необходимые порты
sudo ufw allow 22/tcp      # SSH
sudo ufw allow 80/tcp      # HTTP
sudo ufw allow 443/tcp     # HTTPS

# Включаем firewall
sudo ufw enable

# Проверяем статус
sudo ufw status
```

---

## 🌐 Настройка домена

### 1. DNS настройки

На панели управления вашего доменного регистратора добавьте **A-запись**:

```
Тип: A
Имя: api (или ваш поддомен)
Значение: ВАШ_IP_АДРЕС_СЕРВЕРА
TTL: 3600
```

Пример для домена `example.com`:
- `api.example.com` → `123.45.67.89`

### 2. Проверка DNS

```bash
# Проверка распространения DNS (может занять до 24 часов)
dig api.example.com

# Или
nslookup api.example.com
```

---

## 🚀 Развертывание на сервере

### 1. Клонирование репозитория

```bash
# Переход в домашнюю директорию
cd ~

# Клонирование проекта
git clone https://github.com/Yuniversia/selling-project.git
cd selling-project

# Или если репозиторий приватный
git clone git@github.com:Yuniversia/selling-project.git
```

### 2. Настройка окружения

```bash
# Копирование примера конфигурации
cp .env.example .env

# Редактирование конфигурации
nano .env
```

**Обновите следующие переменные в `.env`:**

```bash
# === DOMAIN CONFIGURATION ===
DOMAIN=api.example.com
PROTOCOL=https

# === SERVICE URLS ===
AUTH_SERVICE_URL=https://api.example.com/auth
POSTS_SERVICE_URL=https://api.example.com/api/v1
CHAT_SERVICE_URL=https://api.example.com/ws
IMEI_SERVICE_URL=https://api.example.com/imei

# === DATABASE ===
POSTGRES_USER=lais_user
POSTGRES_PASSWORD=your_strong_password_here
POSTGRES_DB=lais_db
POSTGRES_HOST=postgres
POSTGRES_PORT=5432

# === SECURITY ===
SECRET_KEY=your_very_long_random_secret_key_here
COOKIE_SECURE=true

# === JWT ===
JWT_SECRET_KEY=another_random_secret_key_for_jwt
JWT_ALGORITHM=HS256

# === GOOGLE OAUTH (опционально) ===
GOOGLE_CLIENT_ID=your_google_client_id
GOOGLE_CLIENT_SECRET=your_google_client_secret
GOOGLE_REDIRECT_URI=https://api.example.com/auth/google/callback

# === REDIS (для кэширования) ===
REDIS_HOST=redis
REDIS_PORT=6379
```

### 3. Настройка Nginx для production

Создайте файл конфигурации Nginx:

```bash
sudo nano /etc/nginx/sites-available/lais-api
```

Добавьте следующую конфигурацию:

```nginx
# Upstream для Docker контейнеров
upstream lais_backend {
    server 127.0.0.1:80;
}

# HTTP -> HTTPS редирект
server {
    listen 80;
    listen [::]:80;
    server_name api.example.com;

    location /.well-known/acme-challenge/ {
        root /var/www/certbot;
    }

    location / {
        return 301 https://$server_name$request_uri;
    }
}

# HTTPS конфигурация
server {
    listen 443 ssl http2;
    listen [::]:443 ssl http2;
    server_name api.example.com;

    # SSL сертификаты (будут созданы Certbot)
    ssl_certificate /etc/letsencrypt/live/api.example.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/api.example.com/privkey.pem;

    # SSL настройки
    ssl_protocols TLSv1.2 TLSv1.3;
    ssl_ciphers HIGH:!aNULL:!MD5;
    ssl_prefer_server_ciphers on;
    ssl_session_cache shared:SSL:10m;
    ssl_session_timeout 10m;

    # Security headers
    add_header Strict-Transport-Security "max-age=31536000; includeSubDomains" always;
    add_header X-Frame-Options "SAMEORIGIN" always;
    add_header X-Content-Type-Options "nosniff" always;
    add_header X-XSS-Protection "1; mode=block" always;

    # Максимальный размер загружаемых файлов
    client_max_body_size 100M;

    # Таймауты
    proxy_connect_timeout 600s;
    proxy_send_timeout 600s;
    proxy_read_timeout 600s;

    # Логи
    access_log /var/log/nginx/lais-access.log;
    error_log /var/log/nginx/lais-error.log;

    # Проксирование на Docker Nginx
    location / {
        proxy_pass http://lais_backend;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_set_header Cookie $http_cookie;
        proxy_cookie_path / /;
    }

    # WebSocket поддержка для чата
    location /ws/ {
        proxy_pass http://lais_backend;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }
}
```

### 4. Активация конфигурации Nginx

```bash
# Создание директории для sites-enabled (если не существует)
sudo mkdir -p /etc/nginx/sites-enabled

# Создание символической ссылки
sudo ln -s /etc/nginx/sites-available/lais-api /etc/nginx/sites-enabled/

# Обновление главного конфига nginx
sudo nano /etc/nginx/nginx.conf
```

Убедитесь что в `nginx.conf` есть строка:
```nginx
include /etc/nginx/sites-enabled/*;
```

```bash
# Проверка конфигурации
sudo nginx -t

# Перезапуск Nginx
sudo systemctl restart nginx
sudo systemctl enable nginx
```

### 5. Обновление docker-compose для production

Обновите `docker-compose.yml` для использования портов только внутри Docker сети:

```bash
nano docker-compose.yml
```

Убедитесь что Nginx контейнер использует только локальный адрес:
```yaml
nginx:
  ports:
    - "127.0.0.1:80:80"  # Только локальный доступ
```

---

## 🔐 SSL сертификаты (Let's Encrypt)

### 1. Получение сертификата (первый раз)

```bash
# Остановка Nginx временно
sudo systemctl stop nginx

# Получение сертификата
sudo certbot certonly --standalone -d api.example.com

# Запуск Nginx обратно
sudo systemctl start nginx
```

### 2. Автоматическое обновление сертификатов

```bash
# Тест автообновления
sudo certbot renew --dry-run

# Создание cronjob для автообновления
sudo crontab -e
```

Добавьте строку:
```cron
0 3 * * * certbot renew --quiet --post-hook "systemctl reload nginx"
```

### 3. Проверка сертификата

```bash
# Проверка срока действия
sudo certbot certificates

# Проверка через браузер
curl -I https://api.example.com
```

---

## 🏃 Запуск проекта

### 1. Использование скрипта автозапуска

```bash
# Сделать скрипт исполняемым
chmod +x start-prod.sh

# Запуск
./start-prod.sh
```

### 2. Ручной запуск

```bash
# Сборка и запуск контейнеров
docker-compose up -d --build

# Проверка статуса
docker-compose ps

# Просмотр логов
docker-compose logs -f
```

### 3. Проверка работы сервисов

```bash
# Проверка Nginx
curl http://localhost:80

# Проверка auth-service
curl http://localhost:80/auth/health || echo "Health endpoint may not exist"

# Проверка posts-service
curl http://localhost:80/api/v1/posts

# Проверка через домен (после DNS)
curl https://api.example.com
```

---

## 📊 Мониторинг и логи

### 1. Просмотр логов Docker

```bash
# Все сервисы
docker-compose logs -f

# Конкретный сервис
docker-compose logs -f nginx
docker-compose logs -f auth-service
docker-compose logs -f posts-service

# Последние 100 строк
docker-compose logs --tail=100 nginx
```

### 2. Логи Nginx

```bash
# Access логи
sudo tail -f /var/log/nginx/lais-access.log

# Error логи
sudo tail -f /var/log/nginx/lais-error.log

# Анализ ошибок за последний час
sudo grep "$(date -d '1 hour ago' '+%d/%b/%Y:%H')" /var/log/nginx/lais-error.log
```

### 3. Мониторинг ресурсов

```bash
# Использование ресурсов контейнерами
docker stats

# Дисковое пространство
docker system df

# Использование системы
htop
```

### 4. Проверка здоровья сервисов

```bash
# Проверка всех контейнеров
docker-compose ps

# Детальная информация
docker inspect <container_name>

# Проверка базы данных
docker-compose exec postgres psql -U lais_user -d lais_db -c "SELECT version();"
```

---

## 🔧 Обслуживание

### 1. Обновление кода

```bash
# Переход в директорию проекта
cd ~/selling-project

# Получение последних изменений
git pull origin main

# Пересборка и перезапуск
docker-compose down
docker-compose up -d --build

# Проверка
docker-compose ps
```

### 2. Резервное копирование базы данных

```bash
# Создание директории для бэкапов
mkdir -p ~/backups

# Бэкап базы данных
docker-compose exec -T postgres pg_dump -U lais_user lais_db > ~/backups/lais_db_$(date +%Y%m%d_%H%M%S).sql

# Автоматизация через cron
crontab -e
```

Добавьте:
```cron
0 2 * * * cd ~/selling-project && docker-compose exec -T postgres pg_dump -U lais_user lais_db > ~/backups/lais_db_$(date +\%Y\%m\%d_\%H\%M\%S).sql
```

### 3. Восстановление базы данных

```bash
# Восстановление из бэкапа
docker-compose exec -T postgres psql -U lais_user lais_db < ~/backups/lais_db_20231201_120000.sql
```

### 4. Очистка Docker

```bash
# Остановка всех контейнеров
docker-compose down

# Удаление неиспользуемых образов
docker image prune -a

# Удаление неиспользуемых томов
docker volume prune

# Полная очистка системы
docker system prune -a --volumes
```

### 5. Перезапуск отдельного сервиса

```bash
# Перезапуск одного контейнера
docker-compose restart auth-service

# Пересборка одного сервиса
docker-compose up -d --no-deps --build auth-service
```

---

## 🐛 Устранение неполадок

### 1. Контейнер не запускается

```bash
# Проверка логов
docker-compose logs <service-name>

# Проверка конфигурации
docker-compose config

# Пересоздание контейнера
docker-compose up -d --force-recreate <service-name>
```

### 2. Проблемы с базой данных

```bash
# Вход в контейнер PostgreSQL
docker-compose exec postgres psql -U lais_user -d lais_db

# Проверка подключений
docker-compose exec postgres psql -U lais_user -d lais_db -c "SELECT * FROM pg_stat_activity;"

# Проверка таблиц
docker-compose exec postgres psql -U lais_user -d lais_db -c "\dt"
```

### 3. Проблемы с SSL

```bash
# Проверка сертификатов
sudo certbot certificates

# Тест конфигурации Nginx
sudo nginx -t

# Перевыпуск сертификата
sudo certbot certonly --standalone -d api.example.com --force-renewal
```

### 4. Проблемы с CORS

Если с фронтенда не проходят запросы:
1. Проверьте `.env` - `PROTOCOL=https` и `DOMAIN=api.example.com`
2. Проверьте CORS настройки в `auth/main.py` и `posts/main.py`
3. Добавьте домен в `allow_origins`:
```python
allow_origins=[
    "https://api.example.com",
    "https://your-frontend-domain.com"
]
```

---

## 📈 Рекомендации по безопасности

### 1. Регулярные обновления

```bash
# Обновление системы
sudo pacman -Syu

# Обновление Docker образов
docker-compose pull
docker-compose up -d
```

### 2. Ограничение SSH доступа

```bash
sudo nano /etc/ssh/sshd_config
```

Рекомендуемые настройки:
```
PermitRootLogin no
PasswordAuthentication no
PubkeyAuthentication yes
Port 22  # Можно изменить на нестандартный
```

### 3. Мониторинг безопасности

```bash
# Установка fail2ban
sudo pacman -S fail2ban

# Настройка fail2ban
sudo systemctl enable fail2ban
sudo systemctl start fail2ban
```

### 4. Регулярные бэкапы

- База данных: ежедневно
- Конфигурация: при каждом изменении
- Хранение: минимум 7 дней
- Тестирование восстановления: ежемесячно

---

## 📞 Поддержка

При возникновении проблем:
1. Проверьте логи: `docker-compose logs -f`
2. Проверьте статус: `docker-compose ps`
3. Проверьте DNS: `dig api.example.com`
4. Проверьте SSL: `curl -I https://api.example.com`

---

## ✅ Чеклист после развертывания

- [ ] DNS настроен и работает
- [ ] SSL сертификат получен и автообновление настроено
- [ ] Все контейнеры запущены (`docker-compose ps`)
- [ ] База данных доступна и таблицы созданы
- [ ] Nginx проксирует запросы корректно
- [ ] CORS настроен правильно
- [ ] Firewall настроен (порты 80, 443, 22)
- [ ] Автоматические бэкапы БД настроены
- [ ] Мониторинг логов настроен
- [ ] Google OAuth настроен (если используется)
- [ ] Тестирование всех endpoints прошло успешно

---

**Готово!** Ваш проект развернут на Arch Linux с доменом 3-го уровня и SSL сертификатом! 🎉
