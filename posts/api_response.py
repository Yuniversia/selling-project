from typing import Any

from fastapi import Request


def request_id_from(request: Request) -> str:
    return getattr(request.state, "request_id", "")


def ok_response(request: Request, data: Any) -> dict:
    return {
        "status": "success",
        "data": data,
        "request_id": request_id_from(request),
    }
