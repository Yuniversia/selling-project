import uuid

from fastapi import HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

from api_response import error_response


class RequestContextMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        request_id = request.headers.get("X-Request-ID") or str(uuid.uuid4())
        request.state.request_id = request_id

        response = await call_next(request)
        response.headers["X-Request-ID"] = request_id
        return response


async def http_exception_handler(request: Request, exc: HTTPException):
    code = str(exc.status_code)
    message = str(exc.detail)
    return JSONResponse(
        status_code=exc.status_code,
        content=error_response(request, code=code, message=message),
    )


async def validation_exception_handler(request: Request, exc: RequestValidationError):
    return JSONResponse(
        status_code=422,
        content=error_response(
            request,
            code="VALIDATION_ERROR",
            message="Request validation failed",
            details={"errors": exc.errors()},
        ),
    )


async def unhandled_exception_handler(request: Request, exc: Exception):
    return JSONResponse(
        status_code=500,
        content=error_response(
            request,
            code="INTERNAL_ERROR",
            message="Internal server error",
        ),
    )
