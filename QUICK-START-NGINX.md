# 🔄 Быстрая инструкция для интеграции с существующим Nginx

Если у вас уже есть Nginx на сервере с другими сайтами, следуйте этой инструкции.

## 📋 Архитектура

```
Интернет
    ↓
Хостовый Nginx :80, :443 (все ваши сайты)
    ├─ api.example.com → Docker Nginx (127.0.0.1:8080) → Микросервисы
    ├─ site1.com → /var/www/site1
    └─ site2.com → /var/www/site2
```

## 🚀 Быстрый старт (5 минут)

### 1. Клонирование и настройка проекта

```bash
# Клонирование
cd ~
git clone https://github.com/Yuniversia/selling-project.git
cd selling-project

# Настройка окружения
cp .env.example .env
nano .env
```

**Обновите в `.env`:**
```bash
DOMAIN=api.example.com
PROTOCOL=https
AUTH_SERVICE_URL=https://api.example.com/auth
POSTS_SERVICE_URL=https://api.example.com/api/v1
CHAT_SERVICE_URL=https://api.example.com/ws
IMEI_SERVICE_URL=https://api.example.com/imei
COOKIE_SECURE=true
POSTGRES_PASSWORD=your_strong_password
SECRET_KEY=your_random_secret_key
```

### 2. Запуск Docker контейнеров

```bash
# Запуск
docker-compose up -d --build

# Проверка
docker-compose ps
curl http://localhost:8080
```

### 3. Настройка хостового Nginx

```bash
# Копирование конфигурации
sudo cp nginx/nginx-host.conf /etc/nginx/sites-available/lais-api

# Редактирование - замените api.example.com на ваш домен
sudo nano /etc/nginx/sites-available/lais-api

# Активация
sudo ln -s /etc/nginx/sites-available/lais-api /etc/nginx/sites-enabled/

# Проверка
sudo nginx -t
```

### 4. Получение SSL сертификата

```bash
# Остановите Nginx временно
sudo systemctl stop nginx

# Получите сертификат
sudo certbot certonly --standalone -d api.example.com

# Запустите Nginx
sudo systemctl start nginx
sudo nginx -t
sudo systemctl reload nginx
```

### 5. Проверка работы

```bash
# Проверка через curl
curl https://api.example.com

# Проверка в браузере
https://api.example.com
```

## ✅ Готово!

Ваш проект интегрирован с существующим Nginx и доступен по домену!

---

## 🔧 Полезные команды

```bash
# Логи Docker
docker-compose logs -f nginx

# Логи хостового Nginx
sudo tail -f /var/log/nginx/lais-error.log

# Перезапуск проекта
cd ~/selling-project
docker-compose restart

# Обновление проекта
git pull
docker-compose up -d --build

# Резервная копия БД
docker-compose exec -T postgres pg_dump -U lais_user lais_db > backup.sql
```

---

## 📝 Что изменено для интеграции

### docker-compose.yml
- Docker Nginx теперь слушает только **127.0.0.1:8080** (не 80)
- Хостовый Nginx проксирует запросы на Docker Nginx

### nginx/nginx-host.conf
- Конфигурация для хостового Nginx
- Проксирование на `http://127.0.0.1:8080`
- SSL через Let's Encrypt
- WebSocket поддержка для чата

### .env
- `DOMAIN` должен содержать ваш поддомен 3-го уровня
- `PROTOCOL=https`
- Все `*_SERVICE_URL` используют ваш домен

---

## 🐛 Troubleshooting

### Docker Nginx не отвечает
```bash
# Проверка портов
sudo netstat -tulpn | grep 8080

# Проверка контейнера
docker-compose logs nginx
```

### Хостовый Nginx не проксирует
```bash
# Проверка конфигурации
sudo nginx -t

# Проверка upstream
curl http://127.0.0.1:8080
```

### SSL не работает
```bash
# Проверка сертификатов
sudo certbot certificates

# Обновление сертификатов
sudo certbot renew
```

---

## 📚 Дополнительно

См. полную документацию в **DEPLOYMENT.md** для:
- Мониторинга
- Резервного копирования
- Безопасности
- Обновлений
