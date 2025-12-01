# main.py (для микросервиса Frontend)

import os
from fastapi import FastAPI
from frontend_router import frontend_router
from fastapi.staticfiles import StaticFiles
from starlette.middleware.cors import CORSMiddleware

# Загружаем конфигурацию
BACKEND_HOST = os.getenv("BACKEND_HOST", "0.0.0.0")
FRONTEND_URL = os.getenv("FRONTEND_URL", "http://localhost:8080")

def configure_static(app: FastAPI):
    app.mount("/templates/static", StaticFiles(directory="templates/static"), name="static")

# Создаем экземпляр FastAPI
app = FastAPI(
    title="Frontend Renderer Service",
    description="Микросервис, который только отдает HTML-страницы (шаблоны).",
    version="1.0.0",
    docs_url=None, # Часто отключают для Frontend-сервисов, чтобы не путать с API-сервисами
    redoc_url=None
)
configure_static(app)

# Настройка CORS - разрешаем все origins для локальной сети
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Разрешаем все origins для локальной сети
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["*"],
)

# Подключаем роутер для отдачи страниц
app.include_router(frontend_router)

# API для проверки IMEI
@app.get("/api/check-imei")
async def check_imei(imei: str):
    """Проверка IMEI через iphone_checker сервис"""
    import httpx
    import os
    
    # URL сервиса из переменной окружения или localhost
    imei_service_url = os.getenv("IMEI_CHECKER_URL", "http://localhost:5001")
    
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            # Запрос к сервису проверки IMEI
            response = await client.get(f"{imei_service_url}/check/{imei}")
            
            if response.status_code == 200:
                return response.json()
            else:
                return {
                    "error": "IMEI не найден",
                    "imei": imei,
                    "model": "Неизвестно",
                    "color": "—",
                    "memory": None,
                    "find_my_iphone": None,
                    "activation_lock": None,
                    "serial_number": "—",
                    "purchase_date": "—",
                    "warranty_status": "—"
                }
    except Exception as e:
        print(f"Ошибка проверки IMEI: {e}")
        return {
            "error": "Ошибка подключения к сервису проверки",
            "imei": imei,
            "model": "Неизвестно",
            "color": "—",
            "memory": None,
            "find_my_iphone": None,
            "activation_lock": None,
            "serial_number": "—",
            "purchase_date": "—",
            "warranty_status": "—"
        }

# Health check endpoint для Docker
@app.get("/health")
async def health_check():
    """Проверка здоровья сервиса для Docker healthcheck"""
    return {"status": "healthy", "service": "main"}

# Важно: Здесь нет логики аутентификации, БД или бизнес-операций.
# Все это должно быть в других микросервисах (например, в вашем auth-сервисе).

# Пример: Если бы этот сервис был также шлюзом, он мог бы проксировать запросы
# к API-микросервису под префиксом /api.
# @app.include_router(auth_router, prefix="/api/auth") # Просто для примера