import logging

from llm_errors import ProviderFailureCode
from redis_pool import get_sync_redis_client

from config import settings

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


def get_global_status_key(provider: str) -> str:
    return f"provider:health:{provider}:global:status"


def get_status_key(provider: str, canonical_model_id: str | None = None) -> str:
    if canonical_model_id:
        return f"provider:health:{provider}:{canonical_model_id}:status"
    return f"provider:health:{provider}:status"


def get_failures_key(provider: str, canonical_model_id: str | None = None) -> str:
    if canonical_model_id:
        return f"provider:health:{provider}:{canonical_model_id}:failures"
    return f"provider:health:{provider}:failures"


def is_circuit_open(
    provider: str,
    canonical_model_id: str | None = None,
    *,
    credential_scope: str = "server",
) -> bool:
    """Check shared hosted-provider circuit state for this credential scope.

    Shared circuit keys describe server/hosted credentials. User-owned BYOK
    credentials are an independent failure domain: a server key can be invalid,
    rate-limited, or out of balance while the user's own key is healthy. BYOK
    calls therefore bypass shared circuit state just as their successes/failures
    never mutate that state.
    """
    if credential_scope == "user":
        return False

    redis_client = get_redis()
    if not redis_client:
        return False

    try:
        # 1. Check provider-global status key
        global_status = redis_client.get(get_global_status_key(provider))
        if global_status == "open":
            logger.warning(f"Global circuit breaker is OPEN for provider: {provider}")
            return True

        # 2. Check model-specific (or fallback) status key
        status_key = get_status_key(provider, canonical_model_id)
        status = redis_client.get(status_key)
        if status == "open":
            logger.warning(f"Circuit breaker is OPEN for provider: {provider}, model: {canonical_model_id or 'default'}")
            return True

        return False
    except Exception as e:
        logger.error(f"Error checking circuit status in Redis for {provider}: {e}")
        return False


def record_success(
    provider: str,
    canonical_model_id: str | None = None,
    *,
    credential_scope: str = "server",
):
    """Record a shared-provider success.

    User-supplied BYOK calls are isolated from shared provider health: a
    successful user key must not reset failures observed by hosted routes.
    """
    if credential_scope == "user":
        return
    redis_client = get_redis()
    if not redis_client:
        return

    try:
        pipe = redis_client.pipeline()
        pipe.delete(get_status_key(provider, canonical_model_id))
        pipe.delete(get_failures_key(provider, canonical_model_id))
        if canonical_model_id:
            pipe.delete(get_status_key(provider, None))
            pipe.delete(get_failures_key(provider, None))
        pipe.execute()
    except Exception as e:
        logger.error(f"Error resetting provider health in Redis for {provider}: {e}")


def record_failure(
    provider: str,
    failure_code: str,
    error_msg: str,
    canonical_model_id: str | None = None,
    *,
    credential_scope: str = "server",
):
    """Record a shared-provider failure and update the circuit breaker.

    Failures from a user-owned BYOK credential are tenant-local. They may
    represent an invalid key, exhausted personal balance, or personal quota
    and therefore must never open or increment a circuit shared by others.
    """
    if credential_scope == "user":
        logger.info(
            "Ignoring user-scoped provider health mutation: provider=%s model=%s code=%s",
            provider,
            canonical_model_id,
            failure_code,
        )
        return
    redis_client = get_redis()
    if not redis_client:
        return

    try:
        # 1. Non-transient terminal errors (invalid keys / billing issues) -> Fast-trip global provider circuit!
        if failure_code in (
            ProviderFailureCode.INVALID_CREDENTIALS.value,
            ProviderFailureCode.INSUFFICIENT_BALANCE.value,
        ):
            global_key = get_global_status_key(provider)
            logger.error(f"Terminal failure ({failure_code}) for provider {provider}. Fast-tripping global provider circuit.")
            redis_client.set(global_key, "open", ex=3600)  # Open for 1 hour
            return

        status_key = get_status_key(provider, canonical_model_id)
        failures_key = get_failures_key(provider, canonical_model_id)

        # 2. Rate limit exceeded -> Open immediately for cooldown period
        if failure_code == ProviderFailureCode.RATE_LIMIT_EXCEEDED.value:
            logger.warning(
                f"Rate limit exceeded for provider {provider} (model={canonical_model_id}). "
                f"Tripping circuit for {COOLDOWN_SECONDS}s."
            )
            redis_client.set(status_key, "open", ex=COOLDOWN_SECONDS)
            return

        # 3. Other errors (timeout, API error, unknown) -> Increment consecutive failures
        failures = redis_client.incr(failures_key)
        redis_client.expire(failures_key, 300)  # expire failures count after 5 minutes

        if failures >= CIRCUIT_FAILURE_THRESHOLD:
            logger.error(
                f"Consecutive failures threshold ({failures}) reached for provider {provider} "
                f"(model={canonical_model_id}). Tripping circuit for {COOLDOWN_SECONDS}s."
            )
            redis_client.set(status_key, "open", ex=COOLDOWN_SECONDS)
    except Exception as e:
        logger.error(f"Error updating provider failure in Redis for {provider}: {e}")
