import json
import logging
import secrets
import time
from typing import Any, Optional

from config import settings

logger = logging.getLogger(__name__)


class OAuthStateStore:
    def __init__(self):
        self._redis = None
        self._owns_connection = False
        self._memory_store: dict[str, tuple[float, Any]] = {}

        if settings.REDIS_URL:  # Use Redis whenever REDIS_URL is set, regardless of RATE_LIMIT_BACKEND
            try:
                from redis_pool import get_sync_redis_client
                pooled = get_sync_redis_client()
                if pooled is not None:
                    self._redis = pooled
                    self._owns_connection = False
                else:
                    import redis
                    self._redis = redis.from_url(settings.REDIS_URL, decode_responses=True)
                    self._owns_connection = True
            except Exception as exc:
                logger.warning("OAuthStateStore: failed to connect to Redis: %s", exc)

        if not self._redis and not settings.IS_LOCAL_ENV:
            raise RuntimeError(
                "OAuth state store requires Redis in staging/production. "
                "Set REDIS_URL environment variable."
            )

    def close(self) -> None:
        if self._redis and self._owns_connection:
            try:
                self._redis.close()
            except Exception:
                pass

    def create_state(self, meta: dict[str, Any], ttl: int = 600) -> str:
        state = secrets.token_urlsafe(32)
        if self._redis:
            self._redis.setex(f"oauth:{state}", ttl, json.dumps(meta))
        else:
            self._cleanup_memory()
            self._memory_store[state] = (time.time() + ttl, meta)
        return state

    def consume_state(self, state: str) -> Optional[dict[str, Any]]:
        if not state:
            return None

        if self._redis:
            key = f"oauth:{state}"
            try:
                data_str = self._redis.getdel(key)
            except AttributeError:
                pipeline = self._redis.pipeline()
                pipeline.get(key)
                pipeline.delete(key)
                results = pipeline.execute()
                data_str = results[0]

            if not data_str:
                return None
            try:
                return json.loads(data_str)
            except json.JSONDecodeError:
                return None
        else:
            self._cleanup_memory()
            if state in self._memory_store:
                expire_at, meta = self._memory_store.pop(state)
                if time.time() < expire_at:
                    return meta
            return None

    def _cleanup_memory(self):
        now = time.time()
        if len(self._memory_store) > 100:
            expired = [k for k, v in self._memory_store.items() if v[0] < now]
            for k in expired:
                del self._memory_store[k]


state_store = OAuthStateStore()
