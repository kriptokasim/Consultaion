import asyncio
from dataclasses import dataclass
from enum import Enum

import litellm


class TransientLLMError(Exception):
    """Represents a transient/temporary LLM failure eligible for retry."""

    def __init__(self, message: str, *, error_code: str | None = None, cause: Exception | None = None):
        super().__init__(message)
        self.error_code = error_code
        self.cause = cause


class ProviderFailureCode(str, Enum):
    INVALID_CREDENTIALS = "invalid_credentials"
    INSUFFICIENT_BALANCE = "insufficient_balance"
    RATE_LIMIT_EXCEEDED = "rate_limit_exceeded"
    MODEL_TIMEOUT = "model_timeout"
    API_ERROR = "api_error"
    UNKNOWN = "unknown"


@dataclass
class ProviderCallFailure:
    code: ProviderFailureCode
    message: str
    raw_error: str


def classify_provider_exception(e: Exception) -> ProviderCallFailure:
    err_str = str(e)
    lower = err_str.lower()

    if isinstance(e, litellm.AuthenticationError):
        return ProviderCallFailure(ProviderFailureCode.INVALID_CREDENTIALS, "Invalid or expired API key.", err_str)
    elif isinstance(e, litellm.BudgetExceededError):
        return ProviderCallFailure(ProviderFailureCode.INSUFFICIENT_BALANCE, "Provider account/credits balance is too low.", err_str)
    elif isinstance(e, litellm.RateLimitError):
        return ProviderCallFailure(ProviderFailureCode.RATE_LIMIT_EXCEEDED, "Provider rate limit exceeded.", err_str)
    elif isinstance(e, asyncio.TimeoutError) or "timeout" in lower or "timed out" in lower:
        return ProviderCallFailure(ProviderFailureCode.MODEL_TIMEOUT, "Provider request timed out.", err_str)

    if "credit balance is too low" in lower or "insufficient" in lower or "requires more credits" in lower:
        return ProviderCallFailure(ProviderFailureCode.INSUFFICIENT_BALANCE, "Provider account/credits balance is too low.", err_str)
    elif "api key not valid" in lower or "invalid api key" in lower or "authentication" in lower or "unauthorized" in lower:
        return ProviderCallFailure(ProviderFailureCode.INVALID_CREDENTIALS, "Invalid or expired API key.", err_str)
    elif "rate limit" in lower or "429" in lower or "too many requests" in lower:
        return ProviderCallFailure(ProviderFailureCode.RATE_LIMIT_EXCEEDED, "Provider rate limit exceeded.", err_str)
    elif "timeout" in lower or "timed out" in lower:
        return ProviderCallFailure(ProviderFailureCode.MODEL_TIMEOUT, "Provider request timed out.", err_str)
    elif "api_error" in lower or "bad request" in lower or "500" in lower or "internal server error" in lower:
        return ProviderCallFailure(ProviderFailureCode.API_ERROR, "Provider API returned an error.", err_str)

    return ProviderCallFailure(ProviderFailureCode.UNKNOWN, "An unknown provider error occurred.", err_str)


# Normal application imports reach llm_errors before the provider adapters are
# fully initialized. Defer bootstrap until the import graph has settled so the
# runtime patch cannot create a circular import. This also avoids relying on
# sitecustomize, which is not guaranteed by Render's uvicorn invocation.
try:
    from model_gateway.production_bootstrap import start_production_model_bootstrap

    start_production_model_bootstrap()
except Exception:
    # Provider bootstrap must never prevent the API from starting; the bootstrap
    # itself emits a structured failure if it cannot initialize.
    pass
