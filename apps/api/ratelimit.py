from __future__ import annotations

import json
import logging
import time
from collections import deque
from datetime import datetime
from typing import Optional
import os

from config import settings

try:  # pragma: no cover - optional dependency
    import redis  # type: ignore
except ImportError:  # pragma: no cover
    redis = None

RECENT_EVENTS_MAX = 200
logger = logging.getLogger(__name__)


class BaseRateLimiterBackend:
    def allow(self, key: str, window_seconds: int, max_requests: int) -> bool:
        raise NotImplementedError

    def record_429(self, ip: str, path: str) -> None:
        raise NotImplementedError

    def recent_429(self) -> list[dict]:
        raise NotImplementedError

    def ping(self) -> Optional[bool]:  # pragma: no cover - overridden where supported
        return None


class MemoryRateLimiterBackend(BaseRateLimiterBackend):
    def __init__(self) -> None:
        self._buckets: dict[str, dict[str, float]] = {}
        self._recent: deque[dict] = deque(maxlen=RECENT_EVENTS_MAX)

    def allow(self, key: str, window_seconds: int, max_requests: int) -> bool:
        now = time.time()
        bucket = self._buckets.get(key)
        if not bucket or bucket.get("reset", 0) < now:
            bucket = {"count": 0, "reset": now + window_seconds}
        bucket["count"] = bucket.get("count", 0) + 1
        self._buckets[key] = bucket
        return bucket["count"] <= max_requests

    def record_429(self, ip: str, path: str) -> None:
        self._recent.append({"ip": ip, "path": path, "ts": datetime.utcnow().isoformat() + "Z"})

    def recent_429(self) -> list[dict]:
        return list(self._recent)


class RedisRateLimiterBackend(BaseRateLimiterBackend):
    RECENT_KEY = "rl:recent"

    def __init__(self, url: str, max_events: int = RECENT_EVENTS_MAX) -> None:
        if redis is None:  # pragma: no cover - import guard
            raise RuntimeError("redis library is required for Redis rate limiting")
        self._client = redis.Redis.from_url(url)
        self._max_events = max_events

    def allow(self, key: str, window_seconds: int, max_requests: int) -> bool:
        redis_key = f"rl:ip:{key}:{window_seconds}"
        try:
            current = self._client.incr(redis_key)
            if current == 1:
                self._client.expire(redis_key, window_seconds)
            return int(current) <= max_requests
        except Exception as exc:  # pragma: no cover - redis failure path
            logger.error("Redis rate limiter failed, allowing request: %s", exc)
            return True

    def record_429(self, ip: str, path: str) -> None:
        entry = {"ip": ip, "path": path, "ts": datetime.utcnow().isoformat() + "Z"}
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
    env_value = os.getenv("RATE_LIMIT_BACKEND")
    if env_value and env_value.lower() in {"redis", "memory"}:
        if env_value.lower() != settings.RATE_LIMIT_BACKEND.lower():
            settings.reload()
        return env_value.lower()
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


def increment_ip_bucket(ip: str, window_seconds: int, max_requests: int) -> bool:
    backend = get_rate_limiter_backend()
    return backend.allow(ip, window_seconds, max_requests)


def record_429(ip: str, path: str) -> None:
    backend = get_rate_limiter_backend()
    backend.record_429(ip, path)


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
