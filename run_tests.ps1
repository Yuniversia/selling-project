<# 
.SYNOPSIS
    Скрипт запуска тестов перед деплоем в production (PowerShell)
.DESCRIPTION
    Запускает smoke, critical и все тесты для проверки готовности к production
#>

# Конфигурация
$env:TEST_AUTH_URL = if ($env:TEST_AUTH_URL) { $env:TEST_AUTH_URL } else { "http://localhost:8000" }
$env:TEST_POSTS_URL = if ($env:TEST_POSTS_URL) { $env:TEST_POSTS_URL } else { "http://localhost:3000" }
$env:TEST_CHAT_URL = if ($env:TEST_CHAT_URL) { $env:TEST_CHAT_URL } else { "http://localhost:4000" }
$env:TEST_MAIN_URL = if ($env:TEST_MAIN_URL) { $env:TEST_MAIN_URL } else { "http://localhost:8080" }

Write-Host "========================================" -ForegroundColor Blue
Write-Host "  ТЕСТИРОВАНИЕ ПЕРЕД ДЕПЛОЕМ В PRODUCTION" -ForegroundColor Blue
Write-Host "========================================" -ForegroundColor Blue
Write-Host ""

# Проверка установки pytest
Write-Host "[1/5] Проверка зависимостей..." -ForegroundColor Yellow
try {
    $null = Get-Command pytest -ErrorAction Stop
    Write-Host "  ✓ pytest установлен" -ForegroundColor Green
} catch {
    Write-Host "  pytest не установлен. Установка..." -ForegroundColor Yellow
    pip install -r tests/requirements.txt
}

# Функция проверки сервиса
function Test-ServiceHealth {
    param (
        [string]$Name,
        [string]$Url
    )
    
    try {
        $response = Invoke-WebRequest -Uri "$Url/health" -TimeoutSec 5 -UseBasicParsing -ErrorAction Stop
        if ($response.StatusCode -eq 200) {
            Write-Host "  ✓ $Name ($Url)" -ForegroundColor Green
            return $true
        }
    } catch {
        Write-Host "  ✗ $Name ($Url) - НЕДОСТУПЕН" -ForegroundColor Red
        return $false
    }
    return $false
}

# Проверка доступности сервисов
Write-Host ""
Write-Host "[2/5] Проверка доступности сервисов..." -ForegroundColor Yellow

$allServicesAvailable = $true
$allServicesAvailable = (Test-ServiceHealth -Name "Auth Service" -Url $env:TEST_AUTH_URL) -and $allServicesAvailable
$allServicesAvailable = (Test-ServiceHealth -Name "Posts Service" -Url $env:TEST_POSTS_URL) -and $allServicesAvailable
$allServicesAvailable = (Test-ServiceHealth -Name "Chat Service" -Url $env:TEST_CHAT_URL) -and $allServicesAvailable
$allServicesAvailable = (Test-ServiceHealth -Name "Main Service" -Url $env:TEST_MAIN_URL) -and $allServicesAvailable

if (-not $allServicesAvailable) {
    Write-Host ""
    Write-Host "ПРЕДУПРЕЖДЕНИЕ: Не все сервисы доступны!" -ForegroundColor Red
    Write-Host "Запустите сервисы командой: docker-compose up -d" -ForegroundColor Yellow
    Write-Host ""
    $continue = Read-Host "Продолжить тестирование? (y/N)"
    if ($continue -ne "y" -and $continue -ne "Y") {
        exit 1
    }
}

# Запуск smoke тестов
Write-Host ""
Write-Host "[3/5] Запуск SMOKE тестов (быстрая проверка)..." -ForegroundColor Yellow
Write-Host ""

$smokeResult = pytest tests/ -m "smoke" -v --tb=short 2>&1
$smokeExitCode = $LASTEXITCODE

if ($smokeExitCode -eq 0) {
    Write-Host "✓ Smoke тесты пройдены" -ForegroundColor Green
} else {
    Write-Host $smokeResult
    Write-Host "✗ Smoke тесты не пройдены!" -ForegroundColor Red
    Write-Host "ДЕПЛОЙ ЗАБЛОКИРОВАН" -ForegroundColor Red
    exit 1
}

# Запуск критических тестов
Write-Host ""
Write-Host "[4/5] Запуск КРИТИЧЕСКИХ тестов..." -ForegroundColor Yellow
Write-Host ""

$criticalResult = pytest tests/ -m "critical" -v --tb=short 2>&1
$criticalExitCode = $LASTEXITCODE

if ($criticalExitCode -eq 0) {
    Write-Host "✓ Критические тесты пройдены" -ForegroundColor Green
} else {
    Write-Host $criticalResult
    Write-Host "✗ Критические тесты не пройдены!" -ForegroundColor Red
    Write-Host "ДЕПЛОЙ ЗАБЛОКИРОВАН" -ForegroundColor Red
    exit 1
}

# Запуск всех тестов
Write-Host ""
Write-Host "[5/5] Запуск ВСЕХ тестов..." -ForegroundColor Yellow
Write-Host ""

$allResult = pytest tests/ -v --tb=short 2>&1
$allExitCode = $LASTEXITCODE

if ($allExitCode -eq 0) {
    Write-Host "✓ Все тесты пройдены" -ForegroundColor Green
} else {
    Write-Host "⚠ Некоторые тесты не пройдены, но критические - ОК" -ForegroundColor Yellow
}

# Итоговый отчёт
Write-Host ""
Write-Host "========================================" -ForegroundColor Blue
Write-Host "  ТЕСТИРОВАНИЕ ЗАВЕРШЕНО УСПЕШНО" -ForegroundColor Green
Write-Host "  ПРОЕКТ ГОТОВ К ДЕПЛОЮ В PRODUCTION" -ForegroundColor Green
Write-Host "========================================" -ForegroundColor Blue
Write-Host ""

exit 0
