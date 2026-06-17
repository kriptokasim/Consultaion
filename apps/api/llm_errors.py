import asyncio
from enum import Enum
from dataclasses import dataclass
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
    
    # Check LiteLLM specific exception types first
    if isinstance(e, litellm.AuthenticationError):
        return ProviderCallFailure(
            code=ProviderFailureCode.INVALID_CREDENTIALS,
            message="Invalid or expired API key.",
            raw_error=err_str
        )
    elif isinstance(e, litellm.BudgetExceededError):
        return ProviderCallFailure(
            code=ProviderFailureCode.INSUFFICIENT_BALANCE,
            message="Provider account/credits balance is too low.",
            raw_error=err_str
        )
    elif isinstance(e, litellm.RateLimitError):
        return ProviderCallFailure(
            code=ProviderFailureCode.RATE_LIMIT_EXCEEDED,
            message="Provider rate limit exceeded.",
            raw_error=err_str
        )
    elif isinstance(e, asyncio.TimeoutError) or "timeout" in lower or "timed out" in lower:
        return ProviderCallFailure(
            code=ProviderFailureCode.MODEL_TIMEOUT,
            message="Provider request timed out.",
            raw_error=err_str
        )
    
    # Generic content checks (very robust for OpenRouter, proxy adapters, etc.)
    if "credit balance is too low" in lower or "insufficient" in lower or "requires more credits" in lower:
        return ProviderCallFailure(
            code=ProviderFailureCode.INSUFFICIENT_BALANCE,
            message="Provider account/credits balance is too low.",
            raw_error=err_str
        )
    elif "api key not valid" in lower or "invalid api key" in lower or "authentication" in lower or "unauthorized" in lower:
        return ProviderCallFailure(
            code=ProviderFailureCode.INVALID_CREDENTIALS,
            message="Invalid or expired API key.",
            raw_error=err_str
        )
    elif "rate limit" in lower or "429" in lower or "too many requests" in lower:
        return ProviderCallFailure(
            code=ProviderFailureCode.RATE_LIMIT_EXCEEDED,
            message="Provider rate limit exceeded.",
            raw_error=err_str
        )
    elif "timeout" in lower or "timed out" in lower:
        return ProviderCallFailure(
            code=ProviderFailureCode.MODEL_TIMEOUT,
            message="Provider request timed out.",
            raw_error=err_str
        )
    elif "api_error" in lower or "bad request" in lower or "500" in lower or "internal server error" in lower:
        return ProviderCallFailure(
            code=ProviderFailureCode.API_ERROR,
            message="Provider API returned an error.",
            raw_error=err_str
        )
        
    return ProviderCallFailure(
        code=ProviderFailureCode.UNKNOWN,
        message="An unknown provider error occurred.",
        raw_error=err_str
    )
