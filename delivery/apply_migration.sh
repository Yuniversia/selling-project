#!/bin/bash
# apply_migration.sh - Скрипт для применения миграции delivery-service

echo "🚀 Applying delivery-service migration..."
echo "================================"

# Проверяем наличие PostgreSQL
if ! command -v psql &> /dev/null; then
    echo "❌ Error: psql не установлен"
    echo "Установите PostgreSQL клиент: sudo apt install postgresql-client"
    exit 1
fi

# Параметры подключения
DB_USER="${DB_USER:-lais_user}"
DB_NAME="${DB_NAME:-lais_marketplace}"
DB_HOST="${DB_HOST:-localhost}"
DB_PORT="${DB_PORT:-5432}"

echo "📊 Connecting to database:"
echo "   Host: $DB_HOST:$DB_PORT"
echo "   Database: $DB_NAME"
echo "   User: $DB_USER"
echo ""

# Применяем миграцию
echo "📝 Applying migration: 001_create_delivery_tables.sql"

PGPASSWORD="${DB_PASSWORD:-lais_password}" psql -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" -d "$DB_NAME" -f "$(dirname "$0")/migrations/001_create_delivery_tables.sql"

if [ $? -eq 0 ]; then
    echo ""
    echo "✅ Migration applied successfully!"
    echo ""
    echo "📋 Created tables:"
    PGPASSWORD="${DB_PASSWORD:-lais_password}" psql -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" -d "$DB_NAME" -c "\dt delivery*"
else
    echo ""
    echo "❌ Migration failed! Check the error above."
    exit 1
fi
