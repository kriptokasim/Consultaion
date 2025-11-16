import os
import time
from collections import deque
from datetime import datetime

RATE_LIMIT_BACKEND = os.getenv("RATE_LIMIT_BACKEND", "memory").lower()
REDIS_URL = os.getenv("REDIS_URL")

_redis_client = None
_ip_buckets: dict[str, dict[str, float]] = {}
_recent_429_events: deque[dict] = deque(maxlen=200)


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
    except Exception:
        return


def get_recent_429_events() -> list[dict]:
    return list(_recent_429_events)
