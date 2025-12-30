# Обновления чат-системы

## Что было добавлено

### 1. Техническая поддержка в чатах ✅

**Backend (chat/):**
- Добавлены поля `support_joined` и `support_user_id` в модель Chat
- Новые эндпоинты:
  - `POST /api/chat/chats/{chat_id}/invite-support` - Пригласить поддержку
  - `POST /api/chat/chats/{chat_id}/join-support` - Присоединиться к чату (для поддержки)
  - `POST /api/chat/chats/{chat_id}/leave-support` - Покинуть чат (для поддержки)
  - `GET /api/chat/chats/support/pending` - Список чатов, ожидающих помощи

**Функционал:**
- Пользователи могут одной кнопкой пригласить поддержку
- Системные сообщения оповещают участников о присоединении/выходе поддержки
- Поддержка может видеть все чаты, где она нужна
- WebSocket обрабатывает приглашения в реальном времени

### 2. Push-уведомления ✅

**Исправлено:**
- `notifications.js` - улучшена проверка активности окна и текущего чата
- `sw.js` - обновлены пути к иконкам и параметры уведомлений
- `chat.js` - добавлено отслеживание `window.currentOpenChatId`

**Как работает:**
- Уведомления НЕ показываются если чат открыт и окно активно
- Уведомления показываются на мобильных и десктопах через Service Worker
- Автоматическое закрытие через `requireInteraction: false`
- Вибрация на мобильных устройствах

**Настройка:**
1. Service Worker регистрируется автоматически при загрузке страницы
2. Пользователю показывается запрос разрешения через 3 секунды
3. После получения разрешения уведомления работают автоматически

### 3. Загрузка файлов в чат ✅

**Backend:**
- Добавлены поля для файлов в модель Message:
  - `message_type` (text/image/file/system)
  - `file_url` - URL в Cloudflare R2
  - `file_name` - имя файла
  - `file_size` - размер в байтах
- Новый файл `cloudflare_r2.py` для работы с R2
- Новые эндпоинты:
  - `GET /api/chat/upload-url` - Получить URL для загрузки
  - `POST /api/chat/file-uploaded` - Подтвердить загрузку

**Использование:**
```javascript
// 1. Получить URL для загрузки
const { upload_url, id } = await fetch('/api/v1/chat/upload-url').then(r => r.json());

// 2. Загрузить файл
const formData = new FormData();
formData.append('file', fileInput.files[0]);
await fetch(upload_url, { method: 'POST', body: formData });

// 3. Получить публичный URL
const { public_url } = await fetch(
  `/api/v1/chat/file-uploaded?file_id=${id}&file_name=${name}&file_size=${size}`
).then(r => r.json());

// 4. Отправить в чат
ws.send(JSON.stringify({
  type: 'message',
  message_type: 'image', // или 'file'
  file_url: public_url,
  file_name: name,
  file_size: size
}));
```

### 4. Миграция базы данных

**Файл:** `chat/migrations/002_add_support_and_files.sql`

**Запустить миграцию:**
```bash
# Подключиться к БД
psql -U postgres -d your_database

# Выполнить миграцию
\i chat/migrations/002_add_support_and_files.sql
```

**Что добавляется:**
- Поля для тех поддержки в таблице `chat`
- Поля для файлов в таблице `message`
- Индексы для быстрого поиска
- `message_text` становится nullable (для файловых сообщений)

## TODO для фронтенда

### Profile.html - Индикатор новых сообщений
Нужно добавить обновление счетчика непрочитанных в реальном времени.

### UI для загрузки файлов
Добавить в chat.js и seller-chats.js:
- Кнопку "📎 Прикрепить файл"
- Превью изображений
- Отображение PDF с иконкой
- Прогресс-бар загрузки

### UI для тех поддержки
В profile.html для админов/поддержки:
- Список ожидающих чатов
- Кнопка "Присоединиться к чату"
- Кнопка "Покинуть чат"
- Уведомления о новых запросах

## Иконки для уведомлений

Создайте PNG иконки из SVG:
- `main/templates/static/icon-192.png` (192x192px)
- `main/templates/static/badge-72.png` (72x72px)

Или используйте существующие:
```bash
# Конвертировать SVG в PNG (если установлен ImageMagick)
convert icon-192.png.svg icon-192.png
convert badge-72.png.svg badge-72.png
```

## Переменные окружения

Убедитесь что настроены:
```env
# Cloudflare
CF_ACCOUNT_ID=your_account_id
CF_API_TOKEN=your_api_token
CF_ACCOUNT_HASH=your_account_hash
```

## Тестирование

### Тест уведомлений:
1. Откройте сайт в двух окнах/устройствах
2. Авторизуйтесь под разными пользователями
3. Отправьте сообщение
4. На втором устройстве должно появиться уведомление

### Тест тех поддержки:
1. В чате нажмите кнопку "Пригласить поддержку"
2. Админ/поддержка должен увидеть чат в списке ожидающих
3. Присоединитесь к чату
4. Все участники увидят системное сообщение

### Тест загрузки файлов:
1. Выберите изображение или PDF
2. Загрузите через UI
3. Проверьте что файл отображается в чате
4. Проверьте что файл доступен по публичному URL

## Известные ограничения

1. **Размер файлов**: Ограничен настройками Cloudflare (обычно 10MB для бесплатного плана)
2. **Типы файлов**: Рекомендуется ограничить: изображения (jpg, png, gif, webp), PDF
3. **Уведомления на iOS**: Могут не работать в Safari из-за ограничений Apple
4. **Service Worker**: Требует HTTPS в продакшене

## Структура файлов

```
chat/
├── models.py (обновлено)
├── chat_router.py (обновлено)
├── chat_service.py
├── websocket_manager.py
├── cloudflare_r2.py (новое)
└── migrations/
    └── 002_add_support_and_files.sql (новое)

main/templates/static/
├── notifications.js (исправлено)
├── sw.js (исправлено)
├── notification-prompt.js
├── chat.js (обновлено)
├── seller-chats.js (требует обновления)
├── icon-192.png (создать из SVG)
└── badge-72.png (создать из SVG)
```

## Следующие шаги

1. ✅ Применить миграцию БД
2. ⏳ Добавить UI для загрузки файлов  
3. ⏳ Добавить UI для тех поддержки в profile.html
4. ⏳ Обновить seller-chats.js для продавцов
5. ⏳ Создать PNG иконки из SVG
6. ⏳ Протестировать на мобильных устройствах

## Контакты для вопросов

Если возникнут вопросы по реализации - проверьте:
- Логи в консоли браузера (F12)
- Логи WebSocket соединения
- Статус Service Worker в DevTools → Application → Service Workers
