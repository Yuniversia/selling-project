from typing import Any, Optional

from fastapi import Request


SERVICE_NAME = "payments-service"


def request_id_from(request: Request) -> str:
    return getattr(request.state, "request_id", "")


def success_response(request: Request, data: Any, meta: Optional[dict] = None) -> dict:
    response = {
        "status": "success",
        "data": data,
        "request_id": request_id_from(request),
    }
    if meta is not None:
        response["meta"] = meta
    return response


def error_response(
    request: Request,
    *,
    code: str,
    message: str,
    details: Optional[dict] = None,
) -> dict:
    return {
        "status": "error",
        "error": {
            "code": code,
            "message": message,
            "service": SERVICE_NAME,
            "details": details or {},
        },
        "request_id": request_id_from(request),
    }
