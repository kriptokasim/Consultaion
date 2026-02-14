import secrets
import json
from typing import Any, Optional
import time

from config import settings
# We'll use the existing redis client if available, or a simple memory fallback
# For now, let's assume we can import a redis client or creating one.
# Given the existing code, let's check if there is a centralized redis client.
# Inspecting `apps/api/deps.py` or similar might be useful, but `sse_backend.py` uses redis.
# Let's verify how redis is accessed in `sse_backend.py` or create a new connection here if needed.
# For simplicity and robustness, I will implement a class that handles both Redis (if configured) and Memory.

import redis

class OAuthStateStore:
    def __init__(self):
        self._redis: Optional[redis.Redis] = None
        self._memory_store: dict[str, tuple[float, Any]] = {}  # state -> (expire_at, meta)
        
        if settings.RATE_LIMIT_BACKEND == "redis" and settings.REDIS_URL:
             try:
                self._redis = redis.from_url(settings.REDIS_URL, decode_responses=True)
             except Exception:
                # Fallback or log?
                pass

    def create_state(self, meta: dict[str, Any], ttl: int = 600) -> str:
        """
        Create a secure random state string and store metadata associated with it.
        """
        state = secrets.token_urlsafe(32)
        if self._redis:
            self._redis.setex(f"oauth:{state}", ttl, json.dumps(meta))
        else:
            self._cleanup_memory()
            self._memory_store[state] = (time.time() + ttl, meta)
        return state

    def consume_state(self, state: str) -> Optional[dict[str, Any]]:
        """
        Retrieve and delete the state metadata. Returns None if invalid or expired.
        Atomic get-and-delete is preferred.
        """
        if not state:
            return None
            
        if self._redis:
            # Redis get and delete
            key = f"oauth:{state}"
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
        # Randomly clean up occassionally or just iterate copy? 
        # For low volume memory fallback, iterating keys is okay-ish but inefficient.
        # Let's just remove expired keys if we touch them or maybe just lazy expiry on access + occasional sweep?
        # A full sweep on every create might be expensive if many pending states.
        # Let's limits size?
        if len(self._memory_store) > 1000:
             # Force cleanup
             expired = [k for k, v in self._memory_store.items() if v[0] < now]
             for k in expired:
                 del self._memory_store[k]

state_store = OAuthStateStore()
