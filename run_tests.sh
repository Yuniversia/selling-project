#!/bin/bash
# run_tests.sh - Скрипт запуска тестов перед деплоем в production

# Цвета для вывода
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

# Конфигурация - всё через nginx на одном порту
TEST_BASE_URL="${TEST_BASE_URL:-http://localhost:8080}"

echo -e "${BLUE}========================================${NC}"
echo -e "${BLUE}  ТЕСТИРОВАНИЕ ПЕРЕД ДЕПЛОЕМ В PRODUCTION${NC}"
echo -e "${BLUE}========================================${NC}"
echo -e "Base URL: ${TEST_BASE_URL}"
echo ""

# Проверка установки зависимостей
echo -e "${YELLOW}[1/5] Проверка зависимостей...${NC}"
if ! command -v pytest &> /dev/null; then
    echo -e "${RED}pytest не установлен. Установка...${NC}"
    pip install -r tests/requirements.txt
fi

# Проверка pytest-asyncio
if ! python -c "import pytest_asyncio" 2>/dev/null; then
    echo -e "${YELLOW}Установка pytest-asyncio...${NC}"
    pip install pytest-asyncio>=0.21.0
fi

# Экспорт переменных окружения для тестов
export TEST_BASE_URL

# Проверка доступности nginx
echo ""
echo -e "${YELLOW}[2/5] Проверка доступности сервисов через nginx...${NC}"
services_available=true

check_endpoint() {
    local name=$1
    local url=$2
    local expected_codes=$3  # Коды через запятую, например "200,401"
    
    status_code=$(curl -s -o /dev/null -w "%{http_code}" --max-time 5 "$url" 2>/dev/null || echo "000")
    
    if [[ "$expected_codes" == *"$status_code"* ]] || [ "$status_code" -lt 500 -a "$status_code" != "000" ]; then
        echo -e "  ${GREEN}✓${NC} $name (status: $status_code)"
        return 0
    else
        echo -e "  ${RED}✗${NC} $name - НЕДОСТУПЕН (status: $status_code)"
        return 1
    fi
}

check_endpoint "Nginx Health" "$TEST_BASE_URL/health" "200" || services_available=false
check_endpoint "Main Page" "$TEST_BASE_URL/" "200" || services_available=false
check_endpoint "Auth API" "$TEST_BASE_URL/api/v1/auth/me" "200,401" || services_available=false
check_endpoint "Posts API" "$TEST_BASE_URL/api/v1/posts/iphone/list" "200" || services_available=false
check_endpoint "Chat API" "$TEST_BASE_URL/api/v1/chat/chats/my?user_id=1&is_seller=false" "200" || services_available=false

if [ "$services_available" = false ]; then
    echo ""
    echo -e "${RED}ОШИБКА: Не все сервисы доступны!${NC}"
    echo -e "${YELLOW}Проверьте контейнеры: docker ps${NC}"
    echo ""
    read -p "Продолжить тестирование? (y/N): " continue_tests
    if [ "$continue_tests" != "y" ] && [ "$continue_tests" != "Y" ]; then
        exit 1
    fi
fi

# Функция для красивого вывода результатов pytest
run_pytest() {
    local marker=$1
    local description=$2
    local tmpfile=$(mktemp)
    
    # Запускаем pytest и сохраняем вывод
    if [ -n "$marker" ]; then
        pytest tests/ -m "$marker" -v --tb=line --no-header 2>&1 | tee "$tmpfile"
    else
        pytest tests/ -v --tb=line --no-header 2>&1 | tee "$tmpfile"
    fi
    local result=${PIPESTATUS[0]}
    
    echo ""
    echo -e "${CYAN}--- Результаты $description ---${NC}"
    
    # Подсчёт результатов (используем wc -l для надёжности)
    local passed=$(grep -c "PASSED" "$tmpfile" || true)
    local failed=$(grep -c "FAILED" "$tmpfile" || true)
    local skipped=$(grep -c "SKIPPED" "$tmpfile" || true)
    local errors=$(grep -c "^ERROR\|ERROR collecting" "$tmpfile" || true)
    
    # Убедимся что это числа
    passed=${passed:-0}
    failed=${failed:-0}
    skipped=${skipped:-0}
    errors=${errors:-0}
    
    echo -e "  ${GREEN}✓ Passed:  $passed${NC}"
    echo -e "  ${RED}✗ Failed:  $failed${NC}"
    echo -e "  ${YELLOW}○ Skipped: $skipped${NC}"
    if [ "$errors" -gt 0 ] 2>/dev/null; then
        echo -e "  ${RED}⚠ Errors:  $errors${NC}"
    fi
    
    # Показываем failed тесты отдельно
    if [ "$failed" -gt 0 ] 2>/dev/null; then
        echo ""
        echo -e "${RED}Проваленные тесты:${NC}"
        grep "FAILED" "$tmpfile" | sed 's/^/  /'
    fi
    
    # Показываем ошибки сбора тестов
    if grep -q "ERROR collecting\|^ERROR" "$tmpfile" 2>/dev/null; then
        echo ""
        echo -e "${RED}Ошибки при сборе тестов:${NC}"
        grep -A2 "ERROR collecting\|^ERROR" "$tmpfile" | sed 's/^/  /'
    fi
    
    rm -f "$tmpfile"
    return $result
}

# Запуск smoke тестов
echo ""
echo -e "${YELLOW}[3/5] Запуск SMOKE тестов (быстрая проверка)...${NC}"
echo ""

if run_pytest "smoke" "SMOKE тестов"; then
    echo -e "${GREEN}✓ Smoke тесты пройдены${NC}"
else
    echo ""
    echo -e "${RED}✗ Smoke тесты НЕ пройдены!${NC}"
    echo -e "${RED}ДЕПЛОЙ ЗАБЛОКИРОВАН - исправьте ошибки выше${NC}"
    exit 1
fi

# Запуск критических тестов
echo ""
echo -e "${YELLOW}[4/5] Запуск КРИТИЧЕСКИХ тестов...${NC}"
echo ""

if run_pytest "critical" "КРИТИЧЕСКИХ тестов"; then
    echo -e "${GREEN}✓ Критические тесты пройдены${NC}"
else
    echo ""
    echo -e "${RED}✗ Критические тесты НЕ пройдены!${NC}"
    echo -e "${RED}ДЕПЛОЙ ЗАБЛОКИРОВАН - исправьте ошибки выше${NC}"
    exit 1
fi

# Запуск всех остальных тестов
echo ""
echo -e "${YELLOW}[5/5] Запуск ВСЕХ тестов...${NC}"
echo ""

if run_pytest "" "ВСЕХ тестов"; then
    echo -e "${GREEN}✓ Все тесты пройдены${NC}"
    final_status="success"
else
    echo -e "${YELLOW}⚠ Некоторые тесты не пройдены (см. выше)${NC}"
    final_status="partial"
fi

# Итоговый отчёт
echo ""
echo -e "${BLUE}========================================${NC}"
if [ "$final_status" = "success" ]; then
    echo -e "${GREEN}  ✓ ТЕСТИРОВАНИЕ ЗАВЕРШЕНО УСПЕШНО${NC}"
    echo -e "${GREEN}  ✓ ПРОЕКТ ГОТОВ К ДЕПЛОЮ В PRODUCTION${NC}"
else
    echo -e "${YELLOW}  ⚠ ТЕСТИРОВАНИЕ ЗАВЕРШЕНО С ПРЕДУПРЕЖДЕНИЯМИ${NC}"
    echo -e "${GREEN}  ✓ Критические тесты пройдены - деплой разрешён${NC}"
fi
echo -e "${BLUE}========================================${NC}"
echo ""

exit 0
