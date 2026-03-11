# apply_migration.ps1 - PowerShell скрипт для применения миграции delivery-service

Write-Host "🚀 Applying delivery-service migration..." -ForegroundColor Green
Write-Host "================================" -ForegroundColor Green

# Параметры подключения
$DB_USER = if ($env:DB_USER) { $env:DB_USER } else { "lais_user" }
$DB_NAME = if ($env:DB_NAME) { $env:DB_NAME } else { "lais_marketplace" }
$DB_HOST = if ($env:DB_HOST) { $env:DB_HOST } else { "localhost" }
$DB_PORT = if ($env:DB_PORT) { $env:DB_PORT } else { "5432" }

Write-Host "📊 Connecting to database:" -ForegroundColor Cyan
Write-Host "   Host: $DB_HOST:$DB_PORT"
Write-Host "   Database: $DB_NAME"
Write-Host "   User: $DB_USER"
Write-Host ""

# Путь к миграции
$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$migrationFile = Join-Path $scriptDir "migrations\001_create_delivery_tables.sql"

if (-not (Test-Path $migrationFile)) {
    Write-Host "❌ Error: Migration file not found: $migrationFile" -ForegroundColor Red
    exit 1
}

Write-Host "📝 Applying migration: 001_create_delivery_tables.sql" -ForegroundColor Yellow

# Применяем миграцию через Docker
Write-Host ""
Write-Host "🐳 Using Docker to apply migration..." -ForegroundColor Cyan

# Копируем файл миграции в контейнер
docker cp $migrationFile postgres:/tmp/001_create_delivery_tables.sql

if ($LASTEXITCODE -ne 0) {
    Write-Host "❌ Failed to copy migration file to container" -ForegroundColor Red
    exit 1
}

# Применяем миграцию
docker exec -it postgres psql -U $DB_USER -d $DB_NAME -f /tmp/001_create_delivery_tables.sql

if ($LASTEXITCODE -eq 0) {
    Write-Host ""
    Write-Host "✅ Migration applied successfully!" -ForegroundColor Green
    Write-Host ""
    Write-Host "📋 Checking created tables..." -ForegroundColor Cyan
    docker exec -it postgres psql -U $DB_USER -d $DB_NAME -c "\dt delivery*"
    
    # Очистка временного файла
    docker exec -it postgres rm /tmp/001_create_delivery_tables.sql
} else {
    Write-Host ""
    Write-Host "❌ Migration failed! Check the error above." -ForegroundColor Red
    exit 1
}

Write-Host ""
Write-Host "🎉 Done!" -ForegroundColor Green
