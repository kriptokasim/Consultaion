from typing import Any, Dict, Optional


class AppError(Exception):
    """Base class for all application errors."""
    def __init__(
        self,
        message: str,
        code: str = "error",
        status_code: int = 500,
        details: Optional[Dict[str, Any]] = None,
        hint: Optional[str] = None,
        retryable: bool = False,
    ):
        self.message = message
        self.code = code
        self.status_code = status_code
        self.details = details or {}
        self.hint = hint
        self.retryable = retryable
        super().__init__(message)

class AuthError(AppError):
    """Authentication and authorization errors."""
    def __init__(
        self,
        message: str = "Authentication failed",
        code: str = "auth.failed",
        status_code: int = 401,
        details: Optional[Dict[str, Any]] = None,
    ):
        super().__init__(message, code, status_code, details)

class PermissionError(AppError):
    """Permission denied errors."""
    def __init__(
        self,
        message: str = "Permission denied",
        code: str = "permission.denied",
        status_code: int = 403,
        details: Optional[Dict[str, Any]] = None,
    ):
        super().__init__(message, code, status_code, details)

class NotFoundError(AppError):
    """Resource not found errors."""
    def __init__(
        self,
        message: str = "Resource not found",
        code: str = "not_found",
        status_code: int = 404,
        details: Optional[Dict[str, Any]] = None,
    ):
        super().__init__(message, code, status_code, details)

class ValidationError(AppError):
    """Data validation errors."""
    def __init__(
        self,
        message: str = "Validation failed",
        code: str = "validation_error",
        status_code: int = 400,
        details: Optional[Dict[str, Any]] = None,
    ):
        super().__init__(message, code, status_code, details)

class RateLimitError(AppError):
    """Rate limit exceeded errors."""
    def __init__(
        self,
        message: str = "Rate limit exceeded",
        code: str = "rate_limit.exceeded",
        status_code: int = 429,
        details: Optional[Dict[str, Any]] = None,
        hint: Optional[str] = "Please wait a moment before trying again.",
        retryable: bool = True,
    ):
        super().__init__(message, code, status_code, details, hint, retryable)

class ProviderCircuitOpenError(AppError):
    """Circuit breaker open error."""
    def __init__(
        self,
        message: str = "Service temporarily unavailable",
        code: str = "service.circuit_open",
        status_code: int = 503,
        details: Optional[Dict[str, Any]] = None,
        hint: Optional[str] = "The service is temporarily unavailable. Please try again later.",
        retryable: bool = True,
    ):
        super().__init__(message, code, status_code, details, hint, retryable)
