# 🚀 Шпаргалка по развертыванию

## ⚡ Быстрый старт на Arch Linux (5 минут)

```bash
# 1. Клонирование
git clone https://github.com/Yuniversia/selling-project.git
cd selling-project

# 2. Настройка
cp .env.example .env
nano .env
# Заполните: DOMAIN, POSTGRES_PASSWORD, SECRET_KEY, JWT_SECRET_KEY

# 3. Запуск Docker
chmod +x *.sh
./start-prod.sh

# 4. Настройка Nginx
./setup-nginx.sh
# Введите домен: api.example.com

# 5. Проверка
curl https://api.example.com
```

---

## 📝 Минимальная настройка .env

```bash
# === ДОМЕН ===
DOMAIN=api.example.com
PROTOCOL=https

# === URLS (с доменом) ===
AUTH_SERVICE_URL=https://api.example.com/auth
POSTS_SERVICE_URL=https://api.example.com/api/v1
CHAT_SERVICE_URL=https://api.example.com/ws
IMEI_SERVICE_URL=https://api.example.com/imei

# === БАЗА ДАННЫХ ===
POSTGRES_USER=lais_user
POSTGRES_PASSWORD=$(openssl rand -hex 16)
POSTGRES_DB=lais_db

# === БЕЗОПАСНОСТЬ ===
SECRET_KEY=$(openssl rand -hex 32)
JWT_SECRET_KEY=$(openssl rand -hex 32)
COOKIE_SECURE=true
```

---

## 🔧 Команды управления

```bash
# === ЗАПУСК / ОСТАНОВКА ===
./start-prod.sh          # Запустить проект
./stop-prod.sh           # Остановить с опцией бэкапа
docker-compose restart   # Быстрый перезапуск
docker-compose ps        # Статус контейнеров

# === ЛОГИ ===
docker-compose logs -f              # Все логи
docker-compose logs -f nginx        # Только Nginx
sudo tail -f /var/log/nginx/lais-error.log  # Хостовый Nginx

# === РЕЗЕРВНОЕ КОПИРОВАНИЕ ===
./backup.sh              # Ручной бэкап
# Автобэкап (cron):
crontab -e
# 0 2 * * * cd ~/selling-project && ./backup.sh

# === ОБНОВЛЕНИЕ ===
git pull
docker-compose up -d --build

# === NGINX ===
sudo nginx -t                        # Проверка конфига
sudo systemctl reload nginx          # Перезапуск
./setup-nginx.sh                     # Переконфигурация

# === SSL ===
sudo certbot certificates            # Статус сертификатов
sudo certbot renew                   # Обновить
```

---

## 🐛 Быстрые решения проблем

### Docker не запускается
```bash
docker-compose logs <service-name>
docker-compose restart <service-name>
```

### Nginx 502 Bad Gateway
```bash
# Проверить Docker Nginx
curl http://localhost:8080

# Перезапустить
docker-compose restart nginx
```

### База данных не доступна
```bash
docker-compose logs postgres
docker-compose restart postgres
```

### SSL не работает
```bash
# Проверить DNS
dig api.example.com

# Получить сертификат заново
sudo certbot certonly --standalone -d api.example.com
```

---

## 📁 Важные файлы

```
selling-project/
├── .env                           # НАСТРОЙТЕ ОБЯЗАТЕЛЬНО
├── docker-compose.yml             # Обновлен (порт 8080)
│
├── start-prod.sh                  # Запуск ✅
├── stop-prod.sh                   # Остановка ✅
├── backup.sh                      # Бэкап ✅
├── setup-nginx.sh                 # Настройка Nginx ✅
│
├── ARCH-LINUX-DEPLOYMENT.md       # 📖 Главная документация
├── QUICK-START-NGINX.md           # ⚡ Быстрый старт
└── DEPLOYMENT.md                  # 📚 Полная документация
```

---

## ✅ Чеклист

**Перед запуском:**
- [ ] Docker установлен и запущен
- [ ] `.env` файл настроен
- [ ] DNS указывает на сервер
- [ ] Порты 80, 443 открыты

**После запуска:**
- [ ] Docker контейнеры работают (`docker-compose ps`)
- [ ] Nginx на хосте настроен
- [ ] SSL сертификат получен
- [ ] Сайт доступен по HTTPS
- [ ] Автобэкап настроен

---

## 🌐 Архитектура

```
Интернет → Nginx (хост) :80/443
           ↓
           api.example.com
           ↓
           Nginx (Docker) :8080 (localhost)
           ↓
           ┌─────────┬──────────┬────────┐
           Auth      Posts      Chat
           :8000     :3000      :4000
           └─────────┴──────────┴────────┘
                     ↓
                  PostgreSQL
```

---

## 📞 Помощь

Если что-то не работает:
1. Проверьте логи: `docker-compose logs -f`
2. Проверьте статус: `docker-compose ps`
3. Проверьте Nginx: `sudo nginx -t`
4. Проверьте SSL: `sudo certbot certificates`

**Документация:**
- [ARCH-LINUX-DEPLOYMENT.md](ARCH-LINUX-DEPLOYMENT.md) - полное руководство
- [QUICK-START-NGINX.md](QUICK-START-NGINX.md) - быстрый старт
- [DEPLOYMENT.md](DEPLOYMENT.md) - детальная документация
