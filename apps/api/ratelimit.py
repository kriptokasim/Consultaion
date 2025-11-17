import logging
import os
import time
from collections import deque
from datetime import datetime
from typing import Optional

RATE_LIMIT_BACKEND = os.getenv("RATE_LIMIT_BACKEND", "memory").lower()
REDIS_URL = os.getenv("REDIS_URL")

_redis_client = None
_ip_buckets: dict[str, dict[str, float]] = {}
_recent_429_events: deque[dict] = deque(maxlen=200)
logger = logging.getLogger(__name__)


def _get_redis_client():
    global _redis_client
    if _redis_client is None and RATE_LIMIT_BACKEND == "redis" and REDIS_URL:
        try:
            import redis

            _redis_client = redis.Redis.from_url(REDIS_URL)
        except Exception:
            _redis_client = None
    return _redis_client


def _increment_ip_bucket_memory(ip: str, window_seconds: int, max_requests: int) -> bool:
    now = time.time()
    bucket = _ip_buckets.get(ip)
    if not bucket or bucket.get("reset", 0) < now:
        bucket = {"count": 0, "reset": now + window_seconds}
    bucket["count"] += 1
    _ip_buckets[ip] = bucket
    return bucket["count"] <= max_requests


def increment_ip_bucket(ip: str, window_seconds: int, max_requests: int) -> bool:
    """
    Return True if the request is allowed, False if rate limited.

    Uses Redis when RATE_LIMIT_BACKEND=redis and REDIS_URL is set, otherwise falls back to in-memory buckets.
    """
    if RATE_LIMIT_BACKEND == "redis" and REDIS_URL:
        client = _get_redis_client()
        if client:
            try:
                key = f"rl:ip:{ip}:{window_seconds}"
                current = client.incr(key)
                if current == 1:
                    client.expire(key, window_seconds)
                return current <= max_requests
            except Exception:
                # fall through to memory fallback
                pass
    return _increment_ip_bucket_memory(ip, window_seconds, max_requests)


def record_429(ip: str, path: str) -> None:
    try:
        _recent_429_events.append(
            {
                "ip": ip,
                "path": path,
                "ts": datetime.utcnow().isoformat() + "Z",
            }
        )
    except Exception as exc:
        logger.error("Failed to record 429 for ip=%s path=%s: %s", ip, path, exc)
        return


def get_recent_429_events() -> list[dict]:
    return list(_recent_429_events)


def ensure_rate_limiter_ready(raise_on_failure: bool = False) -> tuple[str, Optional[bool]]:
    """
    Verify the configured rate limit backend is reachable.
    Returns (backend, redis_ok) and optionally raises if misconfigured.
    """
    redis_ok = None
    if RATE_LIMIT_BACKEND == "redis":
        client = _get_redis_client()
        try:
            redis_ok = bool(client.ping()) if client else False
        except Exception as exc:
            logger.error("Redis rate limit backend unreachable: %s", exc)
            redis_ok = False
        if raise_on_failure and not redis_ok:
            raise RuntimeError("RATE_LIMIT_BACKEND=redis but Redis is unreachable or REDIS_URL unset")
    return RATE_LIMIT_BACKEND, redis_ok
