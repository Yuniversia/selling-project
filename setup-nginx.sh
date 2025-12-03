#!/bin/bash

###############################################################################
# Скрипт настройки хостового Nginx для LAIS Marketplace
# Автоматическая настройка конфигурации Nginx на сервере
###############################################################################

set -e

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

print_status() { echo -e "${BLUE}[INFO]${NC} $1"; }
print_success() { echo -e "${GREEN}[SUCCESS]${NC} $1"; }
print_warning() { echo -e "${YELLOW}[WARNING]${NC} $1"; }
print_error() { echo -e "${RED}[ERROR]${NC} $1"; }

echo "========================================================================"
echo "  🌐 LAIS Marketplace - Nginx Host Configuration"
echo "========================================================================"
echo ""

###############################################################################
# 1. Проверка прав
###############################################################################

if [ "$EUID" -eq 0 ]; then 
    print_error "Не запускайте этот скрипт от root. Используйте sudo внутри."
    exit 1
fi

###############################################################################
# 2. Ввод домена
###############################################################################

print_status "Настройка домена для проекта"
echo ""
read -p "Введите ваш домен (например: api.example.com): " DOMAIN

if [ -z "$DOMAIN" ]; then
    print_error "Домен не может быть пустым"
    exit 1
fi

print_success "Домен: $DOMAIN"
echo ""

###############################################################################
# 3. Проверка Nginx
###############################################################################

print_status "Проверка Nginx..."

if ! command -v nginx &> /dev/null; then
    print_error "Nginx не установлен!"
    read -p "Установить Nginx сейчас? (y/n): " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        sudo pacman -S nginx
        sudo systemctl enable nginx
        sudo systemctl start nginx
    else
        exit 1
    fi
fi

print_success "Nginx установлен: $(nginx -v 2>&1)"

###############################################################################
# 4. Создание конфигурации
###############################################################################

print_status "Создание конфигурации Nginx..."

CONFIG_FILE="/etc/nginx/sites-available/lais-api"
ENABLED_FILE="/etc/nginx/sites-enabled/lais-api"

# Создание директорий
sudo mkdir -p /etc/nginx/sites-available
sudo mkdir -p /etc/nginx/sites-enabled
sudo mkdir -p /var/www/certbot

# Создание конфигурации
sudo tee "$CONFIG_FILE" > /dev/null << EOF
# LAIS Marketplace - $DOMAIN
# Generated: $(date)

upstream lais_docker {
    server 127.0.0.1:8080;
    keepalive 32;
}

server {
    listen 80;
    listen [::]:80;
    server_name $DOMAIN;

    location /.well-known/acme-challenge/ {
        root /var/www/certbot;
    }

    location / {
        return 301 https://\$server_name\$request_uri;
    }
}

server {
    listen 443 ssl http2;
    listen [::]:443 ssl http2;
    server_name $DOMAIN;

    ssl_certificate /etc/letsencrypt/live/$DOMAIN/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/$DOMAIN/privkey.pem;
    ssl_trusted_certificate /etc/letsencrypt/live/$DOMAIN/chain.pem;

    ssl_protocols TLSv1.2 TLSv1.3;
    ssl_ciphers 'ECDHE-ECDSA-AES128-GCM-SHA256:ECDHE-RSA-AES128-GCM-SHA256:ECDHE-ECDSA-AES256-GCM-SHA384:ECDHE-RSA-AES256-GCM-SHA384';
    ssl_prefer_server_ciphers on;
    ssl_session_cache shared:SSL:10m;
    ssl_session_timeout 1d;
    ssl_session_tickets off;

    ssl_stapling on;
    ssl_stapling_verify on;
    resolver 8.8.8.8 8.8.4.4 valid=300s;

    add_header Strict-Transport-Security "max-age=31536000; includeSubDomains" always;
    add_header X-Frame-Options "SAMEORIGIN" always;
    add_header X-Content-Type-Options "nosniff" always;
    add_header X-XSS-Protection "1; mode=block" always;

    client_max_body_size 100M;
    proxy_connect_timeout 600s;
    proxy_send_timeout 600s;
    proxy_read_timeout 600s;

    access_log /var/log/nginx/lais-access.log combined;
    error_log /var/log/nginx/lais-error.log warn;

    location / {
        proxy_pass http://lais_docker;
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto \$scheme;
        proxy_set_header Cookie \$http_cookie;
        proxy_http_version 1.1;
        proxy_set_header Connection "";
    }

    location /ws/ {
        proxy_pass http://lais_docker;
        proxy_http_version 1.1;
        proxy_set_header Upgrade \$http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_read_timeout 86400;
    }

    location ~* \.(jpg|jpeg|png|gif|ico|css|js|svg|woff|woff2|ttf)$ {
        proxy_pass http://lais_docker;
        expires 30d;
        add_header Cache-Control "public, immutable";
    }
}
EOF

print_success "Конфигурация создана: $CONFIG_FILE"

###############################################################################
# 5. Активация конфигурации
###############################################################################

print_status "Активация конфигурации..."

# Создание симлинка
if [ -L "$ENABLED_FILE" ]; then
    sudo rm "$ENABLED_FILE"
fi
sudo ln -s "$CONFIG_FILE" "$ENABLED_FILE"

print_success "Конфигурация активирована"

###############################################################################
# 6. Обновление главного конфига
###############################################################################

print_status "Проверка главного конфига Nginx..."

if ! grep -q "include /etc/nginx/sites-enabled/\*;" /etc/nginx/nginx.conf; then
    print_warning "Добавляю include для sites-enabled..."
    sudo sed -i '/http {/a \    include /etc/nginx/sites-enabled/*;' /etc/nginx/nginx.conf
fi

###############################################################################
# 7. Проверка конфигурации (без SSL)
###############################################################################

print_status "Временное отключение SSL для получения сертификата..."

sudo tee "$CONFIG_FILE" > /dev/null << EOF
upstream lais_docker {
    server 127.0.0.1:8080;
}

server {
    listen 80;
    listen [::]:80;
    server_name $DOMAIN;

    location /.well-known/acme-challenge/ {
        root /var/www/certbot;
    }

    location / {
        proxy_pass http://lais_docker;
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
    }
}
EOF

if sudo nginx -t; then
    print_success "Конфигурация Nginx корректна"
else
    print_error "Ошибка в конфигурации Nginx"
    exit 1
fi

###############################################################################
# 8. Перезапуск Nginx
###############################################################################

print_status "Перезапуск Nginx..."

sudo systemctl reload nginx

print_success "Nginx перезапущен"

###############################################################################
# 9. Certbot
###############################################################################

print_status "Настройка SSL сертификата..."
echo ""

if ! command -v certbot &> /dev/null; then
    print_warning "Certbot не установлен"
    read -p "Установить Certbot? (y/n): " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        sudo pacman -S certbot certbot-nginx
    else
        print_warning "Пропуск настройки SSL"
        echo ""
        echo "========================================================================"
        print_success "Базовая настройка завершена!"
        echo "========================================================================"
        exit 0
    fi
fi

read -p "Получить SSL сертификат сейчас? (y/n): " -n 1 -r
echo
if [[ $REPLY =~ ^[Yy]$ ]]; then
    print_status "Получение SSL сертификата для $DOMAIN..."
    
    if sudo certbot certonly --nginx -d "$DOMAIN"; then
        print_success "SSL сертификат получен!"
        
        # Восстановление полной конфигурации с SSL
        print_status "Обновление конфигурации с SSL..."
        sudo cp nginx/nginx-host.conf "$CONFIG_FILE"
        sudo sed -i "s/api.example.com/$DOMAIN/g" "$CONFIG_FILE"
        
        sudo nginx -t && sudo systemctl reload nginx
        
        print_success "SSL настроен и активирован!"
    else
        print_error "Ошибка при получении SSL сертификата"
        print_warning "Проверьте что:"
        print_warning "  1. DNS настроен и указывает на этот сервер"
        print_warning "  2. Домен доступен из интернета"
        print_warning "  3. Порты 80 и 443 открыты в firewall"
    fi
fi

###############################################################################
# 10. Финальная информация
###############################################################################

echo ""
echo "========================================================================"
echo "  ✅ Настройка завершена!"
echo "========================================================================"
echo ""

print_status "Конфигурация сохранена в: $CONFIG_FILE"
print_status "Ваш домен: $DOMAIN"
echo ""

print_status "Следующие шаги:"
echo "  1. Обновите .env файл проекта:"
echo "     DOMAIN=$DOMAIN"
echo "     PROTOCOL=https"
echo ""
echo "  2. Запустите Docker контейнеры:"
echo "     cd ~/selling-project"
echo "     ./start-prod.sh"
echo ""
echo "  3. Проверьте работу:"
echo "     curl https://$DOMAIN"
echo ""

print_status "Полезные команды:"
echo "  Проверка Nginx:        sudo nginx -t"
echo "  Перезапуск Nginx:      sudo systemctl reload nginx"
echo "  Логи Nginx:            sudo tail -f /var/log/nginx/lais-error.log"
echo "  Обновление SSL:        sudo certbot renew"
echo ""

print_success "🎉 Готово!"
