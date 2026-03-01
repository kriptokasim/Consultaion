import logging
from typing import Any, Dict

from fastapi import Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException

from exceptions import AppError

logger = logging.getLogger(__name__)


def build_error_response(
    code: str,
    message: str,
    status_code: int,
    details: Dict[str, Any] | None = None,
    hint: str | None = None,
    retryable: bool = False,
    retry_after_seconds: int | None = None,
) -> JSONResponse:
    """Builds the standardized error envelope for all public API responses."""
    error_payload = {
        "code": code,
        "message": message,
        "details": details or {},
        "hint": hint,
        "retryable": retryable,
    }
    
    headers: dict[str, str] = {}
    if retry_after_seconds is not None:
        error_payload["retry_after_seconds"] = retry_after_seconds
        headers["Retry-After"] = str(retry_after_seconds)

    return JSONResponse(
        status_code=status_code,
        content={"error": error_payload},
        headers=headers if headers else None,
    )


async def app_error_handler(request: Request, exc: AppError) -> JSONResponse:
    """Handles domain-specific AppErrors."""
    logger.error(
        "AppError",
        extra={
            "code": exc.code,
            "details": exc.details,
            "status_code": exc.status_code,
            "request_path": request.url.path,
            "request_method": request.method,
            "request_id": request.headers.get("x-request-id"),
            "user_id": getattr(request.state, "user_id", None),
        },
    )
    
    retry_after = getattr(exc, "retry_after_seconds", None)
    return build_error_response(
        code=exc.code,
        message=exc.message,
        status_code=exc.status_code,
        details=exc.details,
        hint=exc.hint,
        retryable=exc.retryable,
        retry_after_seconds=retry_after,
    )


async def http_exception_handler(request: Request, exc: HTTPException) -> JSONResponse:
    """Handles standard FastAPI/Starlette HTTPExceptions, mapping them to the standard envelope."""
    # Special case for 404 to provide a cleaner code
    code = "not_found" if exc.status_code == 404 else "http_error"
    
    # Try to extract detailed message if it's a dict (some FastAPI internals do this)
    message = exc.detail
    details = {}
    if isinstance(message, dict):
        details = message
        message = message.get("message", "HTTP Error")
    elif not isinstance(message, str):
         message = str(message)
         
    return build_error_response(
        code=code,
        message=message,
        status_code=exc.status_code,
        details=details,
        retryable=exc.status_code in {408, 429, 502, 503, 504},
    )


async def validation_exception_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
    """Handles Pydantic validation errors."""
    return build_error_response(
        code="validation_error",
        message="Request validation failed",
        status_code=422,
        details={"errors": exc.errors()},
        hint="Check the request payload and parameter types.",
        retryable=False,
    )
