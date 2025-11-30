# main.py (для микросервиса Frontend)

from fastapi import FastAPI
from frontend_router import frontend_router
from fastapi.staticfiles import StaticFiles
from starlette.middleware.cors import CORSMiddleware

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

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:8080",
        "http://localhost:8000",
        "http://localhost:3000",
        "http://localhost:5500",
        "http://127.0.0.1:8080",
        "http://127.0.0.1:8000",
        "http://127.0.0.1:3000",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["*"],
)

# Подключаем роутер для отдачи страниц
app.include_router(frontend_router)

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