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


class ConfigurationError(AppError):
    """Server-side configuration errors that require operator action."""
    def __init__(
        self,
        message: str = "Application configuration error",
        code: str = "configuration_error",
        status_code: int = 500,
        details: Optional[Dict[str, Any]] = None,
        hint: Optional[str] = None,
    ):
        super().__init__(
            message,
            code,
            status_code,
            details,
            hint,
            retryable=False,
        )


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
        hint: Optional[str] = None,
        retryable: bool = False,
    ):
        super().__init__(message, code, status_code, details, hint, retryable)


class RateLimitError(AppError):
    """Rate limit exceeded errors with backward-compatible quota diagnostics."""
    def __init__(
        self,
        message: str = "Rate limit exceeded",
        code: str = "rate_limit.exceeded",
        status_code: int = 429,
        details: Optional[Dict[str, Any]] = None,
        hint: Optional[str] = "Please wait a moment before trying again.",
        retryable: bool = True,
        retry_after_seconds: Optional[int] = None,
    ):
        super().__init__(message, code, status_code, details, hint, retryable)
        self.retry_after_seconds = retry_after_seconds
        # Legacy usage-limit callers read ``detail`` and ``reset_at`` directly.
        # Keep those diagnostics on the canonical error so billing quota errors
        # and hourly quota errors can share one catch path without AttributeError.
        self.detail = message
        self.reset_at = self.details.get("reset_at")


class ProviderCircuitOpenError(AppError):
    """Circuit breaker open error.

    ``auth.configuration_error`` historically flowed through this class from the
    OAuth redirect helper. Preserve that call-site compatibility while ensuring
    operator configuration failures are never marked retryable or surfaced as a
    provider-outage 503.
    """
    def __init__(
        self,
        message: str = "Service temporarily unavailable",
        code: str = "service.circuit_open",
        status_code: int = 503,
        details: Optional[Dict[str, Any]] = None,
        hint: Optional[str] = "The service is temporarily unavailable. Please try again later.",
        retryable: bool = True,
    ):
        if code == "auth.configuration_error":
            status_code = 500
            retryable = False
            hint = "Server configuration requires operator action."
        super().__init__(message, code, status_code, details, hint, retryable)


class ContinuationTransitionError(RuntimeError):
    """Raised when a continuation state transition is invalid or conflicts.

    This is a domain-level invariant violation (not an HTTP error).
    The caller decides how to surface it to the client.
    """
    def __init__(
        self,
        continuation_id: str,
        current_status: str,
        target_status: str,
        message: Optional[str] = None,
    ):
        self.continuation_id = continuation_id
        self.current_status = current_status
        self.target_status = target_status
        msg = message or (
            f"Invalid continuation transition: {current_status} → {target_status} "
            f"(continuation_id={continuation_id})"
        )
        super().__init__(msg)