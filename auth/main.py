# main.py

import os
import logging
from fastapi import FastAPI
from contextlib import asynccontextmanager
from starlette.middleware.sessions import SessionMiddleware
from starlette.middleware.cors import CORSMiddleware

from database import create_db_and_tables, apply_schema_patches
from auth_router import auth_router

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s | %(message)s"
)
logger = logging.getLogger("auth.main")

@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Creating database tables...")
    create_db_and_tables()
    apply_schema_patches()
    yield
    logger.info("Application shutdown complete.")

app = FastAPI(
    title="Modular FastAPI Auth App",
    description="Auth microservice with FastAPI and SQLAlchemy/SQLModel.",
    docs_url="/auth/docs",
    version="1.0.0",
    lifespan=lifespan
)

# CORS - allow specific origins for credential-bearing requests
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost",
        "http://localhost:8080",
        "http://127.0.0.1",
        "http://127.0.0.1:8080",
        "http://136.169.38.242",
        "http://136.169.38.242:8080",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["*"],
)

# Session middleware required for Google OAuth state parameter
SESSION_SECRET = os.getenv('SESSION_SECRET', 'ANY_RANDOM_STRING_FOR_SESSION')
app.add_middleware(SessionMiddleware, secret_key=SESSION_SECRET)

app.include_router(auth_router)

@app.get("/health")
async def health_check():
    return {"status": "healthy", "service": "auth"}