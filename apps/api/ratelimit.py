from __future__ import annotations

import json
import logging
import time
from collections import deque
from datetime import datetime, timezone
from typing import Optional

from config import settings

try:  # pragma: no cover - optional dependency
    import redis  # type: ignore
except ImportError:  # pragma: no cover
    redis = None

RECENT_EVENTS_MAX = 200
logger = logging.getLogger(__name__)


class BaseRateLimiterBackend:
    def allow(self, key: str, window_seconds: int, max_requests: int) -> tuple[bool, int | None]:
        """Check if request is allowed. Returns (allowed, retry_after_seconds)."""
        raise NotImplementedError

    def allow_weighted(
        self, key: str, window_seconds: int, max_requests: int, weight: int
    ) -> tuple[bool, int | None, int, int]:
        """Check if request is allowed under cost weight.

        Returns (allowed, retry_after_seconds, remaining_budget, reset_epoch).
        """
        raise NotImplementedError

    def acquire_sse_lease(self, key: str, lease_id: str, max_active: int, ttl: int = 30) -> bool:
        """Acquire/refresh a concurrent SSE lease. Returns True if accepted, False if limit reached."""
        raise NotImplementedError

    def release_sse_lease(self, key: str, lease_id: str) -> None:
        """Release an active SSE lease."""
        raise NotImplementedError

    def record_429(self, ip: str, path: str) -> None:
        raise NotImplementedError

    def recent_429(self) -> list[dict]:
        raise NotImplementedError

    def ping(self) -> Optional[bool]:  # pragma: no cover - overridden where supported
        return None


def _utc_timestamp() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


class MemoryRateLimiterBackend(BaseRateLimiterBackend):
    def __init__(self) -> None:
        self._buckets: dict[str, dict[str, float]] = {}
        self._recent: deque[dict] = deque(maxlen=RECENT_EVENTS_MAX)
        self._sse_leases: dict[str, dict[str, float]] = {}

    def allow(self, key: str, window_seconds: int, max_requests: int) -> tuple[bool, int | None]:
        """Check if request is allowed and return retry_after_seconds if not."""
        now = time.time()
        bucket = self._buckets.get(key)
        if not bucket or bucket.get("reset", 0) < now:
            bucket = {"count": 0, "reset": now + window_seconds}
        bucket["count"] = bucket.get("count", 0) + 1
        self._buckets[key] = bucket
        allowed = bucket["count"] <= max_requests
        retry_after = None if allowed else max(1, int(bucket["reset"] - now))
        return allowed, retry_after

    def allow_weighted(
        self, key: str, window_seconds: int, max_requests: int, weight: int
    ) -> tuple[bool, int | None, int, int]:
        """Check if request under cost weight is allowed.

        Returns (allowed, retry_after_seconds, remaining_budget, reset_epoch).
        """
        now = time.time()
        bucket = self._buckets.get(key)
        if not bucket or bucket.get("reset", 0) < now:
            bucket = {"count": 0.0, "reset": now + window_seconds}
        
        current = bucket.get("count", 0.0)
        ttl = max(1, int(bucket["reset"] - now))
        reset_epoch = int(bucket["reset"])

        if current + weight <= max_requests:
            bucket["count"] = current + weight
            self._buckets[key] = bucket
            remaining = int(max_requests - bucket["count"])
            return True, None, remaining, reset_epoch
        else:
            self._buckets[key] = bucket
            remaining = int(max_requests - current)
            return False, ttl, remaining, reset_epoch

    def acquire_sse_lease(self, key: str, lease_id: str, max_active: int, ttl: int = 30) -> bool:
        """Acquire or refresh SSE lease in memory."""
        now = time.time()
        leases = self._sse_leases.setdefault(key, {})

        # Clean expired leases
        expired = [lid for lid, exp in leases.items() if exp < now]
        for lid in expired:
            leases.pop(lid, None)

        # If already exists, refresh
        if lease_id in leases:
            leases[lease_id] = now + ttl
            return True

        # Check limit
        if len(leases) >= max_active:
            return False

        # Add lease
        leases[lease_id] = now + ttl
        return True

    def release_sse_lease(self, key: str, lease_id: str) -> None:
        """Release SSE lease in memory."""
        if key in self._sse_leases:
            self._sse_leases[key].pop(lease_id, None)

    def record_429(self, ip: str, path: str) -> None:
        self._recent.append({"ip": ip, "path": path, "ts": _utc_timestamp()})

    def recent_429(self) -> list[dict]:
        return list(self._recent)


class RedisRateLimiterBackend(BaseRateLimiterBackend):
    RECENT_KEY = "rl:recent"

    def __init__(self, url: str, max_events: int = RECENT_EVENTS_MAX) -> None:
        if redis is None:  # pragma: no cover - import guard
            raise RuntimeError("redis library is required for Redis rate limiting")
        from redis_pool import get_sync_redis_client
        pooled_client = get_sync_redis_client()
        if pooled_client is not None:
            self._client = pooled_client
        else:
            self._client = redis.Redis.from_url(url)
        self._max_events = max_events
        self._fallback = MemoryRateLimiterBackend()

    def allow(self, key: str, window_seconds: int, max_requests: int) -> tuple[bool, int | None]:
        """Check if request is allowed. Returns (allowed, retry_after_seconds)."""
        redis_key = f"rl:ip:{key}:{window_seconds}"
        try:
            current = self._client.incr(redis_key)
            if current == 1:
                self._client.expire(redis_key, window_seconds)
            allowed = int(current) <= max_requests
            retry_after = None
            if not allowed:
                ttl = self._client.ttl(redis_key)
                retry_after = max(1, ttl) if ttl and ttl > 0 else window_seconds
            return allowed, retry_after
        except Exception as exc:  # pragma: no cover - redis failure path
            logger.warning("Redis rate limiter failed (%s), falling back to memory", exc)
            return self._fallback.allow(key, window_seconds, max_requests)

    def allow_weighted(
        self, key: str, window_seconds: int, max_requests: int, weight: int
    ) -> tuple[bool, int | None, int, int]:
        """Check if request under cost weight is allowed.

        Returns (allowed, retry_after_seconds, remaining_budget, reset_epoch).
        """
        redis_key = f"rl:ip:{key}:{window_seconds}"
        lua_script = """
local key = KEYS[1]
local window = tonumber(ARGV[1])
local max_requests = tonumber(ARGV[2])
local weight = tonumber(ARGV[3])

local current = tonumber(redis.call('get', key) or "0")
local ttl = redis.call('ttl', key)
if ttl < 0 then
    ttl = window
end

if current + weight <= max_requests then
    redis.call('incrby', key, weight)
    if current == 0 then
        redis.call('expire', key, window)
    end
    local new_val = current + weight
    local remaining = max_requests - new_val
    return {1, ttl, remaining}
else
    local remaining = max_requests - current
    return {0, ttl, remaining}
end
"""
        try:
            res = self._client.eval(lua_script, 1, redis_key, window_seconds, max_requests, weight)
            allowed = bool(res[0])
            ttl = int(res[1])
            remaining = int(res[2])
            
            retry_after = ttl if not allowed else None
            reset_epoch = int(time.time() + ttl)
            return allowed, retry_after, remaining, reset_epoch
        except Exception as exc:  # pragma: no cover - redis failure path
            logger.warning("Redis weighted rate limiter failed (%s), falling back to memory", exc)
            return self._fallback.allow_weighted(key, window_seconds, max_requests, weight)

    def acquire_sse_lease(self, key: str, lease_id: str, max_active: int, ttl: int = 30) -> bool:
        """Acquire/refresh a concurrent SSE lease using Redis sorted sets."""
        redis_key = f"sse:active:{key}"
        now = time.time()
        lua_script = """
local key = KEYS[1]
local lease_id = ARGV[1]
local max_active = tonumber(ARGV[2])
local ttl = tonumber(ARGV[3])
local now = tonumber(ARGV[4])

redis.call('zremrangebyscore', key, '-inf', now)

local score = redis.call('zscore', key, lease_id)
if score then
    redis.call('zadd', key, now + ttl, lease_id)
    redis.call('expire', key, ttl + 10)
    return 1
end

local count = redis.call('zcard', key)
if count >= max_active then
    return 0
end

redis.call('zadd', key, now + ttl, lease_id)
redis.call('expire', key, ttl + 10)
return 1
"""
        try:
            res = self._client.eval(lua_script, 1, redis_key, lease_id, max_active, ttl, now)
            return bool(res)
        except Exception as exc:
            logger.warning("Redis acquire_sse_lease failed (%s), falling back to memory", exc)
            return self._fallback.acquire_sse_lease(key, lease_id, max_active, ttl)

    def release_sse_lease(self, key: str, lease_id: str) -> None:
        """Release SSE lease from Redis sorted set using atomic Lua."""
        redis_key = f"sse:active:{key}"
        try:
            from services.lease import atomic_release_lease
            atomic_release_lease(self._client, redis_key, lease_id)
        except Exception as exc:
            logger.warning("Redis release_sse_lease failed (%s), falling back to memory", exc)
            self._fallback.release_sse_lease(key, lease_id)

    def record_429(self, ip: str, path: str) -> None:
        entry = {"ip": ip, "path": path, "ts": _utc_timestamp()}
        try:
            self._client.rpush(self.RECENT_KEY, json.dumps(entry))
            self._client.ltrim(self.RECENT_KEY, -self._max_events, -1)
        except Exception as exc:  # pragma: no cover - redis failure path
            logger.error("Failed to record 429 event in Redis: %s", exc)

    def recent_429(self) -> list[dict]:
        try:
            raw_entries = self._client.lrange(self.RECENT_KEY, -self._max_events, -1)
            results: list[dict] = []
            for item in raw_entries:
                if not item:
                    continue
                try:
                    results.append(json.loads(item))
                except json.JSONDecodeError:
                    continue
            return results
        except Exception as exc:  # pragma: no cover - redis failure path
            logger.error("Failed to read recent 429 events from Redis: %s", exc)
            return []

    def ping(self) -> Optional[bool]:
        try:
            return bool(self._client.ping())
        except Exception:  # pragma: no cover - redis failure path
            return False


_backend: BaseRateLimiterBackend | None = None


def _resolved_backend_name() -> str:
    return settings.RATE_LIMIT_BACKEND.lower()


def get_rate_limiter_backend() -> BaseRateLimiterBackend:
    global _backend
    if _backend is not None:
        return _backend

    backend_name = _resolved_backend_name()
    if backend_name == "redis" and settings.REDIS_URL:
        try:
            _backend = RedisRateLimiterBackend(settings.REDIS_URL)
            return _backend
        except Exception as exc:
            logger.error("Falling back to memory rate limiter: %s", exc)
    _backend = MemoryRateLimiterBackend()
    return _backend


def reset_rate_limiter_backend_for_tests() -> None:
    global _backend
    _backend = None


def increment_ip_bucket(
    ip: str, window_seconds: int, max_requests: int, user_id: Optional[str] = None
) -> tuple[bool, int | None]:
    """Check if request is allowed. Returns (allowed, retry_after_seconds)."""
    backend = get_rate_limiter_backend()
    key = f"{ip}:{user_id}" if user_id else ip
    return backend.allow(key, window_seconds, max_requests)


def acquire_sse_lease(key: str, lease_id: str, max_active: int, ttl: int = 30) -> bool:
    """Acquire/refresh SSE lease."""
    backend = get_rate_limiter_backend()
    return backend.acquire_sse_lease(key, lease_id, max_active, ttl)


def release_sse_lease(key: str, lease_id: str) -> None:
    """Release SSE lease."""
    backend = get_rate_limiter_backend()
    backend.release_sse_lease(key, lease_id)


from log_config import log_event


def record_429(ip: str, path: str) -> None:
    backend = get_rate_limiter_backend()
    backend.record_429(ip, path)
    log_event("rate_limit.exceeded", ip=ip, path=path, backend=settings.RATE_LIMIT_BACKEND)


def get_recent_429_events() -> list[dict]:
    backend = get_rate_limiter_backend()
    return backend.recent_429()


def ensure_rate_limiter_ready(raise_on_failure: bool = False) -> tuple[str, Optional[bool]]:
    backend_name = _resolved_backend_name()
    redis_ok: Optional[bool] = None
    if backend_name == "redis":
        backend = get_rate_limiter_backend()
        if isinstance(backend, RedisRateLimiterBackend):
            redis_ok = backend.ping()
        else:
            redis_ok = False
        if raise_on_failure and not redis_ok:
            raise RuntimeError("RATE_LIMIT_BACKEND=redis but Redis is unreachable")
    return backend_name, redis_ok
