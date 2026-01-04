# Быстрый запуск обновлений чата

## 1. Применить миграции БД (ОБЯЗАТЕЛЬНО!)

```bash
# Linux/macOS - применяем ВСЕ миграции по порядку
docker exec -i lais-postgres psql -U postgres -d lais_marketplace < chat/migrations/001_create_chat_tables.sql
docker exec -i lais-postgres psql -U postgres -d lais_marketplace < chat/migrations/002_add_support_and_files.sql
docker exec -i lais-postgres psql -U postgres -d lais_marketplace < chat/migrations/003_fix_old_messages.sql

# Windows PowerShell
$env:PGPASSWORD="your_password"
Get-Content "chat\migrations\001_create_chat_tables.sql" | docker exec -i lais-postgres psql -U postgres -d lais_marketplace
Get-Content "chat\migrations\002_add_support_and_files.sql" | docker exec -i lais-postgres psql -U postgres -d lais_marketplace
Get-Content "chat\migrations\003_fix_old_messages.sql" | docker exec -i lais-postgres psql -U postgres -d lais_marketplace
```

## 2. Создать иконки для уведомлений

Нужно создать PNG из SVG файлов или использовать любые 192x192 и 72x72 PNG:

```
main/templates/static/icon-192.png
main/templates/static/badge-72.png  
```

## 3. Перезапустить chat-service

```bash
# Пересобрать и перезапустить chat-service
docker-compose up -d --build chat

# Проверить что запустился
docker ps | grep chat

# Посмотреть логи (должно быть: "Application startup complete")
docker logs lais-chat --tail 30
```

## 4. Проверить что работает

1. Откройте /profile
2. Откройте консоль (F12)
3. Проверьте что Service Worker зарегистрирован:
   - Application → Service Workers → должен быть sw.js
4. Проверьте уведомления - разрешите когда попросит
5. Откройте чат - должно работать

## Что работает прямо сейчас:

✅ Тех поддержка (бэкенд готов, нужен UI)
✅ Push-уведомления (работают)
✅ Загрузка файлов (бэкенд + UI готовы!)
✅ WebSocket с новыми типами сообщений
✅ Миграция БД
✅ UI для прикрепления файлов в чате
✅ Превью изображений в чате

## Что нужно доработать:

⏳ UI для тех поддержки в profile.html
⏳ Обновление счетчика непрочитанных сообщений в реальном времени

## Проблемы?

Проверьте логи:
```bash
# Чат-сервис
docker logs chat

# PostgreSQL
docker logs postgres

# Браузер
F12 → Console
```
