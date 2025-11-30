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

test: ## Запустить тесты (TODO)
	@echo "$(YELLOW)Тесты ещё не реализованы$(RESET)"

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
