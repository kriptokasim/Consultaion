"""Distributed lease / lock primitives with atomic Lua release.

Provides LockAcquireResult enum, Redis Lua lease scripts, and a
complement to the existing DB-based orchestrator lease mechanism.
"""

from __future__ import annotations

import enum
import logging
import time
from typing import Optional

logger = logging.getLogger(__name__)


class LockAcquireResult(enum.Enum):
    """Result of attempting to acquire a distributed lock."""
    ACQUIRED = "acquired"
    HELD = "held"
    BACKEND_UNAVAILABLE = "backend_unavailable"


LEASE_RELEASE_LUA = """
-- KEYS[1] = lease key (e.g. debate:{id}:lease)
-- ARGV[1] = expected holder (runner_id or subscriber_id)
-- Returns 1 if released, 0 if not held

local holder = redis.call('get', KEYS[1])
if holder == ARGV[1] then
    redis.call('del', KEYS[1])
    return 1
end

-- Also handle sorted set based leases (SSE streams)
local score = redis.call('zscore', KEYS[1], ARGV[1])
if score ~= false then
    redis.call('zrem', KEYS[1], ARGV[1])
    return 1
end

return 0
"""

LEASE_ACQUIRE_LUA = """
-- KEYS[1] = lease key
-- ARGV[1] = holder identity
-- ARGV[2] = lease TTL seconds
-- Returns 1 if acquired, 0 if held by another

local holder = redis.call('get', KEYS[1])
if holder == false then
    redis.call('setex', KEYS[1], ARGV[2], ARGV[1])
    return 1
end
if holder == ARGV[1] then
    redis.call('expire', KEYS[1], ARGV[2])
    return 1
end
return 0
"""


def atomic_release_lease(redis_client, key: str, holder: str) -> bool:
    """Atomically release a lease using Lua. Returns True if released."""
    try:
        result = redis_client.eval(LEASE_RELEASE_LUA, 1, key, holder, str(time.time()))
        return bool(result)
    except Exception as exc:
        logger.warning("atomic_release_lease failed: %s", exc)
        return False


def atomic_acquire_lease(redis_client, key: str, holder: str, ttl: int = 60) -> LockAcquireResult:
    """Atomically acquire a lease using Lua."""
    try:
        result = redis_client.eval(LEASE_ACQUIRE_LUA, 1, key, holder, ttl, str(time.time()))
        if result:
            return LockAcquireResult.ACQUIRED
        return LockAcquireResult.HELD
    except Exception as exc:
        logger.warning("atomic_acquire_lease failed: %s", exc)
        return LockAcquireResult.BACKEND_UNAVAILABLE


async def atomic_release_lease_async(redis_client, key: str, holder: str) -> bool:
    """Async version of atomic lease release."""
    try:
        result = await redis_client.eval(LEASE_RELEASE_LUA, 1, key, holder, str(time.time()))
        return bool(result)
    except Exception as exc:
        logger.warning("atomic_release_lease_async failed: %s", exc)
        return False


async def atomic_acquire_lease_async(redis_client, key: str, holder: str, ttl: int = 60) -> LockAcquireResult:
    """Async version of atomic lease acquire."""
    try:
        result = await redis_client.eval(LEASE_ACQUIRE_LUA, 1, key, holder, ttl, str(time.time()))
        if result:
            return LockAcquireResult.ACQUIRED
        return LockAcquireResult.HELD
    except Exception as exc:
        logger.warning("atomic_acquire_lease_async failed: %s", exc)
        return LockAcquireResult.BACKEND_UNAVAILABLE
