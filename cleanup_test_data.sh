#!/bin/bash
# cleanup_test_data.sh - Очистка тестовых данных из БД
# 
# Использование:
#   ./cleanup_test_data.sh              - Очистить все тестовые данные
#   ./cleanup_test_data.sh --dry-run    - Показать что будет удалено (без удаления)
#
# Тестовые данные идентифицируются по:
#   - username/email начинающийся с "_test_"
#   - description объявления содержащий "_test_"
#   - imei начинающийся с "00000"

set -e

BASE_URL="${TEST_BASE_URL:-http://localhost:8080}"
DRY_RUN=false

# Проверяем аргументы
if [ "$1" == "--dry-run" ]; then
    DRY_RUN=true
    echo "🔍 Режим DRY RUN - данные НЕ будут удалены"
fi

echo ""
echo "=============================================="
echo "🧹 ОЧИСТКА ТЕСТОВЫХ ДАННЫХ"
echo "=============================================="
echo "   Base URL: $BASE_URL"
echo ""

# Проверяем доступность сервисов
echo "📡 Проверка доступности сервисов..."

if curl -s -o /dev/null -w "%{http_code}" "$BASE_URL/health" | grep -q "200\|301\|302"; then
    echo "   ✅ Nginx доступен"
else
    echo "   ❌ Nginx недоступен на $BASE_URL"
    echo "   Проверьте что контейнеры запущены: docker ps"
    exit 1
fi

if curl -s -o /dev/null -w "%{http_code}" "$BASE_URL/api/v1/auth/me" | grep -q "200\|401\|403"; then
    echo "   ✅ Auth сервис доступен"
else
    echo "   ⚠️  Auth сервис может быть недоступен"
fi

if curl -s -o /dev/null -w "%{http_code}" "$BASE_URL/api/v1/posts/iphone/list" | grep -q "200"; then
    echo "   ✅ Posts сервис доступен"
else
    echo "   ⚠️  Posts сервис может быть недоступен"
fi

echo ""
echo "=============================================="

# Очистка объявлений
echo ""
echo "📌 Очистка тестовых объявлений..."

if [ "$DRY_RUN" == "true" ]; then
    echo "   (DRY RUN - показываем что будет удалено)"
    # Здесь можно добавить запрос для просмотра что будет удалено
else
    POSTS_RESULT=$(curl -s -X DELETE "$BASE_URL/api/v1/posts/test/iphone/cleanup" 2>/dev/null)
    if echo "$POSTS_RESULT" | grep -q "deleted_count"; then
        DELETED_COUNT=$(echo "$POSTS_RESULT" | grep -oP '"deleted_count":\s*\K\d+' || echo "0")
        echo "   ✅ Удалено объявлений: $DELETED_COUNT"
    else
        echo "   ❌ Ошибка очистки объявлений: $POSTS_RESULT"
    fi
fi

# Очистка пользователей
echo ""
echo "👤 Очистка тестовых пользователей..."

if [ "$DRY_RUN" == "true" ]; then
    echo "   (DRY RUN - показываем что будет удалено)"
else
    USERS_RESULT=$(curl -s -X DELETE "$BASE_URL/api/v1/auth/test/users/cleanup" 2>/dev/null)
    if echo "$USERS_RESULT" | grep -q "deleted_count"; then
        DELETED_COUNT=$(echo "$USERS_RESULT" | grep -oP '"deleted_count":\s*\K\d+' || echo "0")
        echo "   ✅ Удалено пользователей: $DELETED_COUNT"
    else
        echo "   ❌ Ошибка очистки пользователей: $USERS_RESULT"
    fi
fi

echo ""
echo "=============================================="
echo "✅ Очистка завершена!"
echo "=============================================="
echo ""
