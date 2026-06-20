"""Distributed lease / lock primitives with atomic Lua release.

Provides LockAcquireResult enum, Redis Lua lease scripts, and a
complement to the existing DB-based orchestrator lease mechanism.
"""

from __future__ import annotations

import enum
import logging
import time

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

# Sorted-set SSE lease Lua scripts
# KEYS[1] = lease key (sorted set)
# ARGV[1] = subscriber identity (user_id:subscriber_id)
# ARGV[2] = lease expiry (Unix timestamp)
# ARGV[3] = max concurrent streams
# ARGV[4] = current time (Unix timestamp)
SSE_LEASE_ACQUIRE_LUA = """
-- Remove expired members
redis.call('zremrangebyscore', KEYS[1], '-inf', ARGV[4])

-- Check if this subscriber already has a lease (refresh)
local existing_score = redis.call('zscore', KEYS[1], ARGV[1])
if existing_score ~= false then
    redis.call('zadd', KEYS[1], ARGV[2], ARGV[1])
    redis.call('expire', KEYS[1], tonumber(ARGV[2]) - tonumber(ARGV[4]) + 60)
    return 2
end

-- Count active members
local count = redis.call('zcard', KEYS[1])
if count >= tonumber(ARGV[3]) then
    return 0
end

-- Acquire new lease
redis.call('zadd', KEYS[1], ARGV[2], ARGV[1])
redis.call('expire', KEYS[1], tonumber(ARGV[2]) - tonumber(ARGV[4]) + 60)
return 1
"""

SSE_LEASE_RELEASE_LUA = """
-- Remove specific member
redis.call('zrem', KEYS[1], ARGV[1])
-- Set expiry on the key itself
redis.call('expire', KEYS[1], 300)
return 1
"""


def atomic_release_lease(redis_client, key: str, holder: str) -> bool:
    """Atomically release a lease using Lua. Returns True if released."""
    try:
        result = redis_client.eval(LEASE_RELEASE_LUA, 1, key, holder)
        return bool(result)
    except Exception as exc:
        logger.warning("atomic_release_lease failed: %s", exc)
        return False


def atomic_acquire_lease(redis_client, key: str, holder: str, ttl: int = 60) -> LockAcquireResult:
    """Atomically acquire a lease using Lua."""
    try:
        result = redis_client.eval(LEASE_ACQUIRE_LUA, 1, key, holder, ttl)
        if result:
            return LockAcquireResult.ACQUIRED
        return LockAcquireResult.HELD
    except Exception as exc:
        logger.warning("atomic_acquire_lease failed: %s", exc)
        return LockAcquireResult.BACKEND_UNAVAILABLE


async def atomic_release_lease_async(redis_client, key: str, holder: str) -> bool:
    """Async version of atomic lease release."""
    try:
        result = await redis_client.eval(LEASE_RELEASE_LUA, 1, key, holder)
        return bool(result)
    except Exception as exc:
        logger.warning("atomic_release_lease_async failed: %s", exc)
        return False


async def atomic_acquire_lease_async(redis_client, key: str, holder: str, ttl: int = 60) -> LockAcquireResult:
    """Async version of atomic lease acquire."""
    try:
        result = await redis_client.eval(LEASE_ACQUIRE_LUA, 1, key, holder, ttl)
        if result:
            return LockAcquireResult.ACQUIRED
        return LockAcquireResult.HELD
    except Exception as exc:
        logger.warning("atomic_acquire_lease_async failed: %s", exc)
        return LockAcquireResult.BACKEND_UNAVAILABLE


async def sse_acquire_lease_async(
    redis_client, key: str, identity: str, max_streams: int, ttl: int = 300
) -> int:
    """Acquire an SSE sorted-set lease atomically.

    Returns:
        1 = acquired
        2 = refreshed (existing connection)
        0 = limit reached
        -1 = backend error
    """
    try:
        now = time.time()
        expiry = now + ttl
        result = await redis_client.eval(
            SSE_LEASE_ACQUIRE_LUA, 1, key, identity, str(expiry),
            str(max_streams), str(now),
        )
        return int(result)
    except Exception as exc:
        logger.warning("sse_acquire_lease_async failed: %s", exc)
        return -1


async def sse_release_lease_async(redis_client, key: str, identity: str) -> bool:
    """Release an SSE sorted-set lease atomically."""
    try:
        await redis_client.eval(SSE_LEASE_RELEASE_LUA, 1, key, identity)
        return True
    except Exception as exc:
        logger.warning("sse_release_lease_async failed: %s", exc)
        return False
