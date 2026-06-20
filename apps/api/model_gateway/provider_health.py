import logging

from config import settings
from llm_errors import ProviderFailureCode
from redis_pool import get_sync_redis_client

logger = logging.getLogger("model_gateway.provider_health")

CIRCUIT_FAILURE_THRESHOLD = getattr(settings, "PROVIDER_HEALTH_MIN_CALLS", 3)
if CIRCUIT_FAILURE_THRESHOLD > 10:
    # Safe fallback if min calls is set too high
    CIRCUIT_FAILURE_THRESHOLD = 3

COOLDOWN_SECONDS = getattr(settings, "PROVIDER_HEALTH_COOLDOWN_SECONDS", 60)

def get_redis():
    try:
        return get_sync_redis_client()
    except Exception as e:
        logger.warning(f"Failed to get Redis client in provider health: {e}")
        return None

def get_status_key(provider: str) -> str:
    return f"provider:health:{provider}:status"

def get_failures_key(provider: str) -> str:
    return f"provider:health:{provider}:failures"

def is_circuit_open(provider: str) -> bool:
    """Check if the circuit is open for the given provider."""
    redis_client = get_redis()
    if not redis_client:
        return False
    
    try:
        status = redis_client.get(get_status_key(provider))
        if status == "open":
            logger.warning(f"Circuit breaker is OPEN for provider: {provider}")
            return True
        return False
    except Exception as e:
        logger.error(f"Error checking circuit status in Redis for {provider}: {e}")
        return False

def record_success(provider: str):
    """Record a successful call to the provider, resetting failure counts."""
    redis_client = get_redis()
    if not redis_client:
        return
    
    try:
        pipe = redis_client.pipeline()
        pipe.delete(get_status_key(provider))
        pipe.delete(get_failures_key(provider))
        pipe.execute()
    except Exception as e:
        logger.error(f"Error resetting provider health in Redis for {provider}: {e}")

def record_failure(provider: str, failure_code: str, error_msg: str):
    """Record a failure for the provider and update the circuit breaker state."""
    redis_client = get_redis()
    if not redis_client:
        return
        
    try:
        status_key = get_status_key(provider)
        failures_key = get_failures_key(provider)
        
        # 1. Non-transient terminal errors (invalid keys / billing issues) -> Trip immediately!
        if failure_code in (ProviderFailureCode.INVALID_CREDENTIALS.value, ProviderFailureCode.INSUFFICIENT_BALANCE.value):
            logger.error(f"Terminal failure ({failure_code}) for provider {provider}. Fast-tripping circuit.")
            redis_client.set(status_key, "open", ex=3600)  # Open for 1 hour
            return
            
        # 2. Rate limit exceeded -> Open immediately for cooldown period
        if failure_code == ProviderFailureCode.RATE_LIMIT_EXCEEDED.value:
            logger.warning(f"Rate limit exceeded for provider {provider}. Tripping circuit for {COOLDOWN_SECONDS}s.")
            redis_client.set(status_key, "open", ex=COOLDOWN_SECONDS)
            return
            
        # 3. Other errors (timeout, API error, unknown) -> Increment consecutive failures
        failures = redis_client.incr(failures_key)
        redis_client.expire(failures_key, 300)  # expire failures count after 5 minutes
        
        if failures >= CIRCUIT_FAILURE_THRESHOLD:
            logger.error(f"Consecutive failures threshold ({failures}) reached for provider {provider}. Tripping circuit for {COOLDOWN_SECONDS}s.")
            redis_client.set(status_key, "open", ex=COOLDOWN_SECONDS)
    except Exception as e:
        logger.error(f"Error updating provider failure in Redis for {provider}: {e}")
