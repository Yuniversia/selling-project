@echo off
REM Скрипт остановки LAIS Marketplace для Windows

echo ================================================
echo    LAIS Marketplace - Stop
echo ================================================
echo.

echo Остановка сервисов...
docker-compose down

if errorlevel 1 (
    echo.
    echo [ERROR] Ошибка при остановке!
    pause
    exit /b 1
)

echo.
echo [OK] Все сервисы остановлены
echo.

set /p cleanup="Удалить данные PostgreSQL? (y/n): "
if /i "%cleanup%"=="y" (
    echo.
    echo Удаление volumes...
    docker-compose down -v
    echo [OK] Данные удалены
)

echo.
pause
