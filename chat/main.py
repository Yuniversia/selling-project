from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager

from database import create_db_and_tables
from chat_router import router as chat_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifecycle events"""
    # Startup
    print("🚀 Starting Chat Service...")
    create_db_and_tables()
    print("✅ Database tables created")
    yield
    # Shutdown
    print("👋 Shutting down Chat Service...")


app = FastAPI(
    title="Chat Service API",
    description="WebSocket чат для маркетплейса",
    version="1.0.0",
    lifespan=lifespan
)

# CORS настройки
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:8080",
        "http://localhost:8000",
        "http://localhost:3000",
        "http://localhost:4000",
        "http://localhost:5500",
        
        "http://127.0.0.1:8080",
        "http://127.0.0.1:8000",
        "http://127.0.0.1:3000",
        "http://127.0.0.1:4000",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["*"],
)

# Подключаем роутеры
app.include_router(chat_router)


@app.get("/")
def root():
    """Root endpoint"""
    return {
        "service": "chat",
        "version": "1.0.0",
        "status": "running"
    }


@app.get("/health")
@app.head("/health")
def health_check():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "service": "chat"
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=4000,
        reload=True
    )
