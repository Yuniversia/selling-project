# Makefile для LAIS Marketplace
# Использование: make <command>

.PHONY: help build up down restart logs clean test migrate backup restore

# Цвета для вывода
GREEN  := $(shell tput -Txterm setaf 2)
YELLOW := $(shell tput -Txterm setaf 3)
RESET  := $(shell tput -Txterm sgr0)

help: ## Показать эту справку
	@echo "$(GREEN)LAIS Marketplace - Доступные команды:$(RESET)"
	@echo ""
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | \
		awk 'BEGIN {FS = ":.*?## "}; {printf "  $(YELLOW)%-15s$(RESET) %s\n", $$1, $$2}'
	@echo ""

# ============================================
# Основные команды
# ============================================

build: ## Собрать все Docker образы
	@echo "$(GREEN)Сборка Docker образов...$(RESET)"
	docker-compose build

up: ## Запустить все сервисы
	@echo "$(GREEN)Запуск всех сервисов...$(RESET)"
	docker-compose up -d
	@echo "$(GREEN)✓ Сервисы запущены!$(RESET)"
	@echo "Frontend: http://localhost:8080"
	@echo "Auth API: http://localhost:8000/auth/docs"
	@echo "Posts API: http://localhost:3000/docs"

down: ## Остановить все сервисы
	@echo "$(YELLOW)Остановка сервисов...$(RESET)"
	docker-compose down

restart: ## Перезапустить все сервисы
	@echo "$(YELLOW)Перезапуск сервисов...$(RESET)"
	docker-compose restart

logs: ## Показать логи всех сервисов
	docker-compose logs -f

status: ## Показать статус сервисов
	@echo "$(GREEN)Статус сервисов:$(RESET)"
	docker-compose ps

# ============================================
# Разработка
# ============================================

dev: ## Запуск в режиме разработки (с логами)
	@echo "$(GREEN)Запуск в режиме разработки...$(RESET)"
	docker-compose up

rebuild: ## Пересобрать и перезапустить
	@echo "$(YELLOW)Пересборка и перезапуск...$(RESET)"
	docker-compose up -d --build

clean: ## Удалить контейнеры и volumes
	@echo "$(YELLOW)Очистка...$(RESET)"
	docker-compose down -v
	docker system prune -f

# ============================================
# Отдельные сервисы
# ============================================

auth-logs: ## Логи Auth сервиса
	docker-compose logs -f auth-service

posts-logs: ## Логи Posts сервиса
	docker-compose logs -f posts-service

main-logs: ## Логи Main сервиса
	docker-compose logs -f main-service

db-logs: ## Логи PostgreSQL
	docker-compose logs -f postgres

auth-restart: ## Перезапустить Auth сервис
	docker-compose restart auth-service

posts-restart: ## Перезапустить Posts сервис
	docker-compose restart posts-service

main-restart: ## Перезапустить Main сервис
	docker-compose restart main-service

# ============================================
# База данных
# ============================================

db-shell: ## Подключиться к PostgreSQL
	docker-compose exec postgres psql -U postgres -d lais_marketplace

db-tables: ## Показать таблицы
	docker-compose exec postgres psql -U postgres -d lais_marketplace -c "\dt"

migrate: ## Запустить миграции
	@echo "$(GREEN)Запуск миграций...$(RESET)"
	docker-compose exec posts-service python migrate_to_postgres.py

backup: ## Создать бэкап базы данных
	@echo "$(GREEN)Создание бэкапа...$(RESET)"
	docker-compose exec postgres pg_dump -U postgres lais_marketplace > backup_$(shell date +%Y%m%d_%H%M%S).sql
	@echo "$(GREEN)✓ Бэкап создан!$(RESET)"

restore: ## Восстановить из последнего бэкапа
	@echo "$(YELLOW)Восстановление из бэкапа...$(RESET)"
	@bash -c 'docker-compose exec -T postgres psql -U postgres -d lais_marketplace < $$(ls -t backup_*.sql | head -1)'
	@echo "$(GREEN)✓ Восстановлено!$(RESET)"

# ============================================
# Тестирование и проверка
# ============================================

health: ## Проверить здоровье всех сервисов
	@echo "$(GREEN)Проверка сервисов...$(RESET)"
	@echo -n "Auth Service: "; curl -s http://localhost:8000/health | jq -r '.status' 2>/dev/null || echo "ERROR"
	@echo -n "Posts Service: "; curl -s http://localhost:3000/health | jq -r '.status' 2>/dev/null || echo "ERROR"
	@echo -n "Main Service: "; curl -s http://localhost:8080/health | jq -r '.status' 2>/dev/null || echo "ERROR"
	@echo -n "PostgreSQL: "; docker-compose exec postgres pg_isready -U postgres -q && echo "healthy" || echo "ERROR"

test: ## Запустить ВСЕ тесты
	@echo "$(GREEN)Запуск всех тестов...$(RESET)"
	pytest tests/ -v --tb=short

test-smoke: ## Запустить SMOKE тесты (быстрая проверка)
	@echo "$(GREEN)Запуск smoke тестов...$(RESET)"
	pytest tests/ -m "smoke" -v --tb=short

test-critical: ## Запустить КРИТИЧЕСКИЕ тесты
	@echo "$(GREEN)Запуск критических тестов...$(RESET)"
	pytest tests/ -m "critical" -v --tb=short

test-auth: ## Тесты Auth сервиса
	@echo "$(GREEN)Тесты Auth сервиса...$(RESET)"
	pytest tests/test_auth_service.py -v --tb=short

test-posts: ## Тесты Posts сервиса
	@echo "$(GREEN)Тесты Posts сервиса...$(RESET)"
	pytest tests/test_posts_service.py -v --tb=short

test-chat: ## Тесты Chat сервиса
	@echo "$(GREEN)Тесты Chat сервиса...$(RESET)"
	pytest tests/test_chat_service.py -v --tb=short

test-frontend: ## Тесты Frontend сервиса
	@echo "$(GREEN)Тесты Frontend сервиса...$(RESET)"
	pytest tests/test_frontend_service.py -v --tb=short

test-integration: ## Интеграционные тесты
	@echo "$(GREEN)Интеграционные тесты...$(RESET)"
	pytest tests/test_integration.py -v --tb=short

test-install: ## Установить зависимости для тестов
	@echo "$(GREEN)Установка зависимостей для тестов...$(RESET)"
	pip install -r tests/requirements.txt

test-report: ## Запустить тесты с HTML отчётом
	@echo "$(GREEN)Запуск тестов с HTML отчётом...$(RESET)"
	pytest tests/ -v --html=test_report.html --self-contained-html

test-pre-deploy: ## Полное тестирование перед деплоем
	@echo "$(GREEN)========================================$(RESET)"
	@echo "$(GREEN)  ТЕСТИРОВАНИЕ ПЕРЕД ДЕПЛОЕМ$(RESET)"
	@echo "$(GREEN)========================================$(RESET)"
	@$(MAKE) health
	@echo ""
	@$(MAKE) test-smoke
	@echo ""
	@$(MAKE) test-critical
	@echo ""
	@echo "$(GREEN)✓ Все критические тесты пройдены!$(RESET)"
	@echo "$(GREEN)  Проект готов к деплою$(RESET)"

# ============================================
# Очистка
# ============================================

clean-all: ## Полная очистка (контейнеры, образы, volumes)
	@echo "$(YELLOW)Полная очистка Docker...$(RESET)"
	docker-compose down -v --rmi all
	docker system prune -af --volumes
	@echo "$(GREEN)✓ Очистка завершена!$(RESET)"

# ============================================
# Production
# ============================================

prod-up: ## Запуск в production режиме
	@echo "$(GREEN)Запуск в production...$(RESET)"
	docker-compose -f docker-compose.prod.yml up -d

prod-down: ## Остановка production
	docker-compose -f docker-compose.prod.yml down

# ============================================
# По умолчанию
# ============================================

.DEFAULT_GOAL := help
