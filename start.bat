@echo off
REM Скрипт быстрого запуска LAIS Marketplace для Windows
REM Использование: start.bat

echo ================================================
echo    LAIS Marketplace - Quick Start
echo ================================================
echo.

REM Проверка установки Docker
echo [1/4] Проверка Docker...
docker --version >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Docker не установлен!
    echo.
    echo Установите Docker Desktop:
    echo https://www.docker.com/products/docker-desktop
    echo.
    pause
    exit /b 1
)
echo [OK] Docker установлен

REM Проверка запущен ли Docker
echo [2/4] Проверка Docker Engine...
docker info >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Docker Engine не запущен!
    echo.
    echo Запустите Docker Desktop и повторите попытку.
    echo.
    pause
    exit /b 1
)
echo [OK] Docker Engine работает

REM Запуск контейнеров
echo [3/4] Запуск контейнеров...
echo.
docker-compose up -d

if errorlevel 1 (
    echo.
    echo [ERROR] Ошибка при запуске контейнеров!
    echo.
    echo Попробуйте:
    echo   docker-compose down
    echo   docker-compose up -d --build
    echo.
    pause
    exit /b 1
)

REM Ожидание запуска сервисов
echo.
echo [4/4] Ожидание запуска сервисов...
timeout /t 5 /nobreak >nul

REM Проверка статуса
echo.
echo ================================================
echo    Статус сервисов:
echo ================================================
docker-compose ps

echo.
echo ================================================
echo    Сервисы запущены!
echo ================================================
echo.
echo Frontend:  http://localhost:8080
echo Auth API:  http://localhost:8000/auth/docs
echo Posts API: http://localhost:3000/docs
echo.
echo ================================================
echo.

REM Открыть Frontend в браузере
set /p open="Открыть Frontend в браузере? (y/n): "
if /i "%open%"=="y" (
    start http://localhost:8080
)

echo.
echo Для остановки: docker-compose down
echo Для логов: docker-compose logs -f
echo.
pause
