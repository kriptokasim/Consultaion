import secrets
import json
import logging
from typing import Any, Optional
import time

from config import settings

logger = logging.getLogger(__name__)

import redis


class OAuthStateStore:
    def __init__(self):
        self._redis: Optional[redis.Redis] = None
        self._memory_store: dict[str, tuple[float, Any]] = {}
        
        if settings.RATE_LIMIT_BACKEND == "redis" and settings.REDIS_URL:
             try:
                self._redis = redis.from_url(settings.REDIS_URL, decode_responses=True)
             except Exception:
                pass

        # FH125 C-6: Require Redis in staging/production — no memory fallback
        if not self._redis and not settings.IS_LOCAL_ENV:
            logger.error("OAuthStateStore: Redis required in staging/production but REDIS_URL not configured")
            raise RuntimeError(
                "OAuth state store requires Redis in staging/production. "
                "Set REDIS_URL environment variable."
            )

    def create_state(self, meta: dict[str, Any], ttl: int = 600) -> str:
        """Create a secure random state string and store metadata associated with it."""
        state = secrets.token_urlsafe(32)
        if self._redis:
            self._redis.setex(f"oauth:{state}", ttl, json.dumps(meta))
        else:
            self._cleanup_memory()
            self._memory_store[state] = (time.time() + ttl, meta)
        return state

    def consume_state(self, state: str) -> Optional[dict[str, Any]]:
        """Retrieve and delete the state metadata atomically. Returns None if invalid or expired."""
        if not state:
            return None
            
        if self._redis:
            # FH125 C-6: Use GETDEL for atomic get-and-delete
            key = f"oauth:{state}"
            try:
                data_str = self._redis.getdel(key)
            except AttributeError:
                # Fallback for older redis-py versions without getdel
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
        """Simple cleanup for memory store to prevent leaks."""
        now = time.time()
        if len(self._memory_store) > 1000:
             expired = [k for k, v in self._memory_store.items() if v[0] < now]
             for k in expired:
                 del self._memory_store[k]

state_store = OAuthStateStore()
