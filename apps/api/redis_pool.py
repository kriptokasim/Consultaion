"""
Patchset 112: Centralized Redis connection pooling.

Provides a shared Redis connection pool for all Redis-dependent services:
- Rate Limiting
- Server-Sent Events (SSE)
- Counts caching

This avoids creating multiple Redis connections per request/service.

CRITICAL BEHAVIOR:
- There is NO silent fallback in production. 
- If REDIS_URL is configured but connection fails, behavior depends on REDIS_POOL_STRICT:
  - REDIS_POOL_STRICT=true (default in production): Raises RuntimeError on failure immediately to avoid masking misconfigurations.
  - REDIS_POOL_STRICT=false (default in local): Returns None, allows in-memory fallback.

This ensures production misconfigurations are surfaced immediately rather than
silently degrading to in-memory fallbacks.
"""
from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Optional

from config import settings

if TYPE_CHECKING:
    import redis
    import redis.asyncio as aioredis

logger = logging.getLogger(__name__)


def _is_strict_mode() -> bool:
    """Determine if Redis pool failures should be fatal.

    In production/staging, Redis misconfiguration should fail loudly.
    In local/dev, silent fallback is acceptable.
    """
    # Check for explicit setting first
    strict_setting = getattr(settings, "REDIS_POOL_STRICT", None)
    if strict_setting is not None:
        return strict_setting
    # Default: strict in non-local environments
    return not getattr(settings, "IS_LOCAL_ENV", True)

# Sync Redis pool (for ratelimit, debates count cache)
_sync_pool: Optional["redis.ConnectionPool"] = None
_sync_client: Optional["redis.Redis"] = None

# Async Redis pool (for SSE)
_async_pool: Optional["aioredis.ConnectionPool"] = None
_async_client: Optional["aioredis.Redis"] = None


def get_sync_redis_client() -> Optional["redis.Redis"]:
    """
    Get a shared sync Redis client with connection pooling.

    Returns None if Redis is not configured or unavailable.
    """
    global _sync_pool, _sync_client

    if not settings.REDIS_URL:
        return None

    if _sync_client is not None:
        return _sync_client

    try:
        import redis
        from metrics import increment_metric

        if _sync_pool is None:
            _sync_pool = redis.ConnectionPool.from_url(
                settings.REDIS_URL,
                max_connections=20,
                socket_connect_timeout=5,
                socket_timeout=5,
                retry_on_timeout=True,
                decode_responses=True,
            )

        _sync_client = redis.Redis(connection_pool=_sync_pool)
        # Verify connection
        _sync_client.ping()
        logger.info("Sync Redis connection pool initialized")
        increment_metric("redis.pool.sync.created")
        return _sync_client
    except ImportError:
        logger.warning("redis library not installed, sync Redis unavailable")
        return None
    except Exception as exc:
        try:
            from metrics import increment_metric
            increment_metric("redis.pool.sync.failed")
        except Exception:
            pass

        if _is_strict_mode():
            logger.error("FATAL: Sync Redis pool failed in strict mode: %s", exc)
            raise RuntimeError(
                f"Redis pool initialization failed (REDIS_POOL_STRICT=true): {exc}"
            ) from exc
        else:
            logger.warning("Sync Redis pool failed, falling back to None: %s", exc)
            return None


def get_async_redis_client() -> Optional["aioredis.Redis"]:
    """
    Get a shared async Redis client with connection pooling.

    Returns None if Redis is not configured.
    Note: Async client connection is verified on first use.
    """
    global _async_pool, _async_client

    url = settings.SSE_REDIS_URL or settings.REDIS_URL
    if not url:
        return None

    if _async_client is not None:
        return _async_client

    try:
        import redis.asyncio as aioredis
        from metrics import increment_metric

        if _async_pool is None:
            _async_pool = aioredis.ConnectionPool.from_url(
                url,
                max_connections=50,
                socket_connect_timeout=5,
                socket_timeout=10,
                socket_keepalive=True,
                health_check_interval=30,
                retry_on_timeout=True,
                decode_responses=True,
            )

        _async_client = aioredis.Redis(connection_pool=_async_pool)
        logger.info("Async Redis connection pool initialized")
        increment_metric("redis.pool.async.created")
        return _async_client
    except ImportError:
        logger.warning("redis.asyncio not available, async Redis unavailable")
        return None
    except Exception as exc:
        try:
            from metrics import increment_metric
            increment_metric("redis.pool.async.failed")
        except Exception:
            pass

        if _is_strict_mode():
            logger.error("FATAL: Async Redis pool failed in strict mode: %s", exc)
            raise RuntimeError(
                f"Async Redis pool initialization failed (REDIS_POOL_STRICT=true): {exc}"
            ) from exc
        else:
            logger.warning("Async Redis pool failed, falling back to None: %s", exc)
            return None


async def close_async_redis() -> None:
    """Close the async Redis connection pool. Call on shutdown."""
    global _async_client, _async_pool
    if _async_client is not None:
        await _async_client.aclose()
        _async_client = None
    if _async_pool is not None:
        await _async_pool.disconnect()
        _async_pool = None


def close_sync_redis() -> None:
    """Close the sync Redis connection pool. Call on shutdown."""
    global _sync_client, _sync_pool
    if _sync_client is not None:
        _sync_client.close()
        _sync_client = None
    if _sync_pool is not None:
        _sync_pool.disconnect()
        _sync_pool = None


def reset_pools_for_tests() -> None:
    """Reset all pools for test isolation."""
    global _sync_pool, _sync_client, _async_pool, _async_client
    _sync_pool = None
    _sync_client = None
    _async_pool = None
    _async_client = None
