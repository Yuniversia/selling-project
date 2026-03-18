import logging

import redis
from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.middleware.cors import CORSMiddleware

from api_response import error_response, success_response
from configs import settings
from database import create_db_and_tables, db_health_check
from middlewares import (
    RequestContextMiddleware,
    http_exception_handler,
    unhandled_exception_handler,
    validation_exception_handler,
)
from payment_router import payments_router


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("payments.main")


class HealthcheckAccessFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        message = record.getMessage()
        if '"GET /health ' in message:
            return False
        return True


logging.getLogger("uvicorn.access").addFilter(HealthcheckAccessFilter())


create_db_and_tables()

app = FastAPI(
    title="Payments API Service",
    description="Payments microservice with Stripe integration.",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
)

app.add_middleware(RequestContextMiddleware)
app.add_exception_handler(HTTPException, http_exception_handler)
app.add_exception_handler(RequestValidationError, validation_exception_handler)
app.add_exception_handler(Exception, unhandled_exception_handler)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["*"],
)

app.include_router(payments_router)


def _redis_health_check() -> bool:
    try:
        client = redis.Redis.from_url(settings.redis_url)
        client.ping()
        return True
    except Exception:
        logger.exception("Redis health check failed")
        return False


@app.get("/health")
async def health_check(request: Request):
    db_ok = db_health_check()
    redis_ok = _redis_health_check()

    if db_ok and redis_ok:
        return success_response(
            request,
            {
                "service": settings.service_name,
                "database": "ok",
                "redis": "ok",
            },
        )

    return JSONResponse(
        status_code=503,
        content=error_response(
            request,
            code="SERVICE_UNHEALTHY",
            message="Service dependency check failed",
            details={
                "database": "ok" if db_ok else "unavailable",
                "redis": "ok" if redis_ok else "unavailable",
            },
        ),
    )


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host=settings.backend_host, port=settings.port)
