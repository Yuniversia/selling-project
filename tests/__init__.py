# tests/__init__.py
# Пакет автоматических тестов для LAIS Marketplace

"""
Автоматические тесты для проверки работоспособности проекта перед деплоем в production.

Запуск тестов:
    pytest tests/ -v              # Все тесты
    pytest tests/ -m "smoke"      # Только smoke тесты
    pytest tests/ -m "critical"   # Только критические тесты
    
Структура:
    - test_auth_service.py     - Тесты Auth сервиса
    - test_posts_service.py    - Тесты Posts сервиса
    - test_chat_service.py     - Тесты Chat сервиса
    - test_frontend_service.py - Тесты Frontend сервиса
    - test_integration.py      - Интеграционные тесты
    - test_smoke.py            - Быстрые smoke тесты
    - test_security.py         - Тесты безопасности
    - test_notifications.py    - Тесты уведомлений
    - test_imei_service.py     - Тесты IMEI сервиса
"""

__version__ = "1.0.0"

