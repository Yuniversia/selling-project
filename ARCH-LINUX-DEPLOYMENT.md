# 📦 Файлы для развертывания на Arch Linux с существующим Nginx

## 📁 Структура файлов

```
selling-project/
├── 📘 DEPLOYMENT.md              # Полная документация развертывания
├── 📗 QUICK-START-NGINX.md       # Быстрый старт для существующего Nginx
├── 🚀 start-prod.sh              # Скрипт запуска проекта
├── 🛑 stop-prod.sh               # Скрипт остановки проекта
├── 💾 backup.sh                  # Скрипт резервного копирования
├── 🔧 setup-nginx.sh             # Автоматическая настройка Nginx
├── docker-compose.yml            # Docker конфигурация (обновлен)
└── nginx/
    ├── nginx.conf                # Nginx для Docker (внутренний)
    └── nginx-host.conf           # Nginx для хоста (внешний)
```

---

## 🎯 Быстрый старт

### Вариант 1: Автоматическая настройка (Рекомендуется)

```bash
# 1. Клонирование
git clone https://github.com/Yuniversia/selling-project.git
cd selling-project

# 2. Настройка .env
cp .env.example .env
nano .env  # Заполните необходимые переменные

# 3. Запуск Docker контейнеров
chmod +x start-prod.sh
./start-prod.sh

# 4. Настройка хостового Nginx
chmod +x setup-nginx.sh
./setup-nginx.sh
# Следуйте инструкциям на экране

# 5. Готово!
curl https://ваш-домен.com
```

### Вариант 2: Ручная настройка

См. **QUICK-START-NGINX.md** для пошаговой инструкции.

---

## 📖 Описание файлов

### 📘 DEPLOYMENT.md
**Полная документация по развертыванию**
- Установка Arch Linux
- Настройка Docker
- Настройка DNS и домена
- SSL сертификаты
- Мониторинг и логи
- Резервное копирование
- Troubleshooting

### 📗 QUICK-START-NGINX.md
**Быстрая инструкция для серверов с существующим Nginx**
- Минимальные шаги развертывания
- Интеграция с хостовым Nginx
- Проверка работы
- Основные команды

### 🚀 start-prod.sh
**Скрипт автоматического запуска проекта**

Что делает:
- ✅ Проверяет зависимости (Docker, docker-compose)
- ✅ Проверяет конфигурационные файлы
- ✅ Валидирует переменные окружения
- ✅ Проверяет доступность порта 8080
- ✅ Создает необходимые директории
- ✅ Останавливает старые контейнеры
- ✅ Собирает и запускает новые контейнеры
- ✅ Проверяет здоровье сервисов
- ✅ Выводит статус и полезную информацию

Использование:
```bash
chmod +x start-prod.sh
./start-prod.sh
```

### 🛑 stop-prod.sh
**Скрипт graceful остановки проекта**

Что делает:
- ✅ Проверяет запущенные контейнеры
- ✅ Предлагает создать резервную копию БД
- ✅ Останавливает контейнеры с таймаутом
- ✅ Опционально удаляет volumes
- ✅ Очищает неиспользуемые образы

Использование:
```bash
chmod +x stop-prod.sh
./stop-prod.sh
```

### 💾 backup.sh
**Автоматическое резервное копирование**

Что делает:
- ✅ Создает резервную копию PostgreSQL
- ✅ Сжимает бэкап (gzip)
- ✅ Сохраняет конфигурационные файлы
- ✅ Удаляет старые бэкапы (>7 дней)
- ✅ Выводит статистику

Использование:
```bash
chmod +x backup.sh
./backup.sh

# Или добавить в crontab для ежедневного бэкапа
crontab -e
# 0 2 * * * cd ~/selling-project && ./backup.sh >> logs/backup.log 2>&1
```

### 🔧 setup-nginx.sh
**Автоматическая настройка хостового Nginx**

Что делает:
- ✅ Проверяет наличие Nginx
- ✅ Запрашивает ваш домен
- ✅ Создает конфигурацию Nginx
- ✅ Активирует конфигурацию
- ✅ Получает SSL сертификат (Certbot)
- ✅ Настраивает HTTPS редирект
- ✅ Проверяет корректность конфигурации

Использование:
```bash
chmod +x setup-nginx.sh
./setup-nginx.sh
# Введите ваш домен когда спросит
```

### 🐳 docker-compose.yml
**Обновленная конфигурация Docker**

Изменения:
```yaml
nginx:
  ports:
    - "127.0.0.1:8080:80"  # Только локальный доступ
```

Теперь Docker Nginx слушает только **127.0.0.1:8080**, а хостовый Nginx проксирует на него.

### 📄 nginx/nginx-host.conf
**Конфигурация для хостового Nginx**

Особенности:
- ✅ Проксирование на Docker Nginx (127.0.0.1:8080)
- ✅ SSL/TLS настройки
- ✅ WebSocket поддержка
- ✅ Кэширование статики
- ✅ Security headers
- ✅ Rate limiting (опционально)

Установка:
```bash
sudo cp nginx/nginx-host.conf /etc/nginx/sites-available/lais-api
sudo sed -i 's/api.example.com/ваш-домен/g' /etc/nginx/sites-available/lais-api
sudo ln -s /etc/nginx/sites-available/lais-api /etc/nginx/sites-enabled/
sudo nginx -t
sudo systemctl reload nginx
```

---

## 🔐 Настройка переменных окружения

Обязательные переменные в `.env`:

```bash
# Domain (ваш домен 3-го уровня)
DOMAIN=api.example.com
PROTOCOL=https

# Service URLs (с вашим доменом)
AUTH_SERVICE_URL=https://api.example.com/auth
POSTS_SERVICE_URL=https://api.example.com/api/v1
CHAT_SERVICE_URL=https://api.example.com/ws
IMEI_SERVICE_URL=https://api.example.com/imei

# Database
POSTGRES_USER=lais_user
POSTGRES_PASSWORD=ваш_сложный_пароль
POSTGRES_DB=lais_db

# Security
SECRET_KEY=ваш_случайный_ключ_минимум_32_символа
JWT_SECRET_KEY=другой_случайный_ключ_для_jwt
COOKIE_SECURE=true

# Google OAuth (опционально)
GOOGLE_CLIENT_ID=ваш_google_client_id
GOOGLE_CLIENT_SECRET=ваш_google_client_secret
GOOGLE_REDIRECT_URI=https://api.example.com/auth/google/callback
```

Генерация случайных ключей:
```bash
openssl rand -hex 32
```

---

## 🏗️ Архитектура

```
┌─────────────────────────────────────────────────────────────┐
│                         Интернет                            │
└──────────────────────────┬──────────────────────────────────┘
                           │
                    ┌──────▼──────┐
                    │  Nginx Host │ :80, :443
                    │  (Arch)     │
                    └──────┬──────┘
                           │
        ┏━━━━━━━━━━━━━━━━━━┻━━━━━━━━━━━━━━━━━━┓
        ┃              api.example.com        ┃
        ┃         (Proxy to 127.0.0.1:8080)   ┃
        ┗━━━━━━━━━━━━━━━━━━┳━━━━━━━━━━━━━━━━━━┛
                           │
                    ┌──────▼──────┐
                    │Docker Nginx │ :8080 (localhost only)
                    └──────┬──────┘
                           │
        ┌──────────────────┼──────────────────┐
        │                  │                  │
    ┌───▼────┐      ┌─────▼─────┐      ┌────▼────┐
    │  Auth  │      │   Posts   │      │  Chat   │
    │ :8000  │      │   :3000   │      │  :4000  │
    └────────┘      └───────────┘      └─────────┘
        │                  │                  │
        └──────────────────┼──────────────────┘
                           │
                    ┌──────▼──────┐
                    │ PostgreSQL  │ :5432
                    └─────────────┘
```

---

## 🚀 Порядок развертывания

### 1️⃣ Подготовка сервера
```bash
# Обновление системы
sudo pacman -Syu

# Установка Docker
sudo pacman -S docker docker-compose
sudo systemctl start docker
sudo systemctl enable docker
sudo usermod -aG docker $USER

# Перелогиниться
logout
```

### 2️⃣ Клонирование и настройка
```bash
cd ~
git clone https://github.com/Yuniversia/selling-project.git
cd selling-project
cp .env.example .env
nano .env  # Настроить переменные
```

### 3️⃣ Запуск Docker
```bash
chmod +x start-prod.sh
./start-prod.sh
```

### 4️⃣ Настройка Nginx
```bash
chmod +x setup-nginx.sh
./setup-nginx.sh
# Ввести домен: api.example.com
```

### 5️⃣ Проверка
```bash
# Локально
curl http://localhost:8080

# Через домен
curl https://api.example.com

# В браузере
https://api.example.com
```

---

## 🔧 Полезные команды

### Docker
```bash
# Статус контейнеров
docker-compose ps

# Логи
docker-compose logs -f
docker-compose logs -f nginx

# Перезапуск
docker-compose restart

# Остановка
./stop-prod.sh
```

### Nginx
```bash
# Проверка конфигурации
sudo nginx -t

# Перезапуск
sudo systemctl reload nginx

# Логи
sudo tail -f /var/log/nginx/lais-error.log
sudo tail -f /var/log/nginx/lais-access.log
```

### Резервное копирование
```bash
# Ручной бэкап
./backup.sh

# Восстановление
docker-compose exec -T postgres psql -U lais_user lais_db < backups/database/backup.sql
```

### SSL
```bash
# Проверка сертификатов
sudo certbot certificates

# Обновление
sudo certbot renew

# Тест автообновления
sudo certbot renew --dry-run
```

---

## 🐛 Troubleshooting

### Docker Nginx не запускается
```bash
# Проверить порт 8080
sudo netstat -tulpn | grep 8080

# Логи
docker-compose logs nginx
```

### Хостовый Nginx возвращает 502
```bash
# Проверить Docker Nginx
curl http://localhost:8080

# Проверить upstream
sudo nginx -t
```

### SSL не работает
```bash
# Проверить сертификаты
sudo certbot certificates

# DNS
dig api.example.com

# Порты
sudo ufw status
```

---

## 📚 Дополнительная информация

- **DEPLOYMENT.md** - полная документация
- **QUICK-START-NGINX.md** - быстрый старт
- **Логи**: `logs/` директория
- **Бэкапы**: `backups/` директория

---

## ✅ Чеклист после развертывания

- [ ] Docker контейнеры запущены
- [ ] Nginx на хосте настроен и работает
- [ ] DNS указывает на сервер
- [ ] SSL сертификат получен
- [ ] HTTPS редирект работает
- [ ] Все endpoints доступны
- [ ] WebSocket (чат) работает
- [ ] База данных инициализирована
- [ ] Автоматические бэкапы настроены
- [ ] Firewall настроен (80, 443, 22)
- [ ] Логи проверены на ошибки

---

**🎉 Готово! Ваш проект развернут на Arch Linux с доменом 3-го уровня!**
