# Быстрый деплой - Инструкция

## Что было исправлено:

1. ✅ Все HTML шаблоны теперь используют относительные пути `/auth` и `/api/v1`
2. ✅ Отключено кеширование шаблонов в Jinja2
3. ✅ Добавлены заголовки для отключения кеша HTML в браузере
4. ✅ Исправлены порты в docker-compose.prod.yml (8080:80)

## Как задеплоить изменения:

### Вариант 1: Автоматический деплой (рекомендуется)

```powershell
.\deploy-to-server.ps1
```

### Вариант 2: Вручную через SSH

1. **Коммит и пуш изменений:**
```powershell
git add .
git commit -m "Fix mixed content and caching issues"
git push origin main
```

2. **На сервере (через SSH):**
```bash
cd /root/lais
git pull origin main
docker-compose -f docker-compose.prod.yml restart main-service
docker-compose -f docker-compose.prod.yml restart nginx
```

### Вариант 3: Копирование файлов через SCP

Если git не настроен на сервере:
```powershell
scp -r main/templates root@136.169.38.242:/root/lais/main/
scp -r main/frontend_router.py root@136.169.38.242:/root/lais/main/
scp docker-compose.prod.yml root@136.169.38.242:/root/lais/
```

Затем на сервере:
```bash
cd /root/lais
docker-compose -f docker-compose.prod.yml restart main-service nginx
```

## Очистка кеша браузера:

После деплоя обязательно очистите кеш:

1. **Открыть DevTools:** Нажмите `F12`
2. **Кликните правой кнопкой** на кнопке обновления (↻) в браузере
3. **Выберите:** "Empty Cache and Hard Reload" / "Очистить кеш и жёсткая перезагрузка"

Или:
- Chrome/Edge: `Ctrl + Shift + Delete` → выберите "Кэшированные изображения и файлы" → Удалить
- Firefox: `Ctrl + Shift + Delete` → выберите "Кэш" → Удалить

## Проверка:

После деплоя откройте консоль браузера (F12) и убедитесь:
```
✅ AUTH API URL: /auth
✅ POSTS API URL: /api/v1
✅ Нет ошибок Mixed Content
✅ cachedFetch определён
```
