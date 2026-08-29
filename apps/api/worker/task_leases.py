"""Small renewable Redis leases for idempotent Celery side-effect tasks.

Execution-lease fencing protects the main debate pipeline, but post-terminal
Celery work intentionally runs after that lease is released. Broker redelivery
must still not execute the same expensive LLM side effect concurrently. These
helpers provide one ownership primitive with compare-and-renew/release semantics.
"""

from __future__ import annotations

import logging
import threading
import uuid
from dataclasses import dataclass
from enum import Enum

logger = logging.getLogger(__name__)

_RELEASE_LUA = """
if redis.call('get', KEYS[1]) == ARGV[1] then
  return redis.call('del', KEYS[1])
end
return 0
"""

_RENEW_LUA = """
if redis.call('get', KEYS[1]) == ARGV[1] then
  return redis.call('expire', KEYS[1], ARGV[2])
end
return 0
"""


class TaskLeaseAcquireResult(Enum):
    ACQUIRED = "acquired"
    HELD = "held"
    BACKEND_UNAVAILABLE = "backend_unavailable"


@dataclass(frozen=True)
class TaskLease:
    client: object
    key: str
    owner: str
    ttl_seconds: int


def acquire_task_lease(
    namespace: str,
    identity: str,
    *,
    ttl_seconds: int = 300,
) -> tuple[TaskLeaseAcquireResult, TaskLease | None]:
    """Acquire one distributed task identity without stealing a live owner."""
    try:
        from redis_pool import get_sync_redis_client

        client = get_sync_redis_client()
        if client is None:
            return TaskLeaseAcquireResult.BACKEND_UNAVAILABLE, None
        key = f"lock:task:{namespace}:{identity}"
        owner = uuid.uuid4().hex
        acquired = client.set(key, owner, nx=True, ex=ttl_seconds)
        if not acquired:
            return TaskLeaseAcquireResult.HELD, None
        return (
            TaskLeaseAcquireResult.ACQUIRED,
            TaskLease(client=client, key=key, owner=owner, ttl_seconds=ttl_seconds),
        )
    except Exception:
        logger.warning(
            "task_lease.acquire_failed namespace=%s identity=%s",
            namespace,
            identity,
            exc_info=True,
        )
        return TaskLeaseAcquireResult.BACKEND_UNAVAILABLE, None


def renew_task_lease(lease: TaskLease) -> bool:
    """Refresh TTL only while this worker still owns the lease token."""
    try:
        result = lease.client.eval(
            _RENEW_LUA,
            1,
            lease.key,
            lease.owner,
            lease.ttl_seconds,
        )
        return bool(result)
    except Exception:
        logger.warning("task_lease.renew_failed key=%s", lease.key, exc_info=True)
        return False


def release_task_lease(lease: TaskLease | None) -> None:
    """Delete only our own lease; never clear a newer owner's token."""
    if lease is None:
        return
    try:
        lease.client.eval(_RELEASE_LUA, 1, lease.key, lease.owner)
    except Exception:
        # TTL remains the crash-recovery authority.
        logger.warning("task_lease.release_failed key=%s", lease.key, exc_info=True)


def start_task_lease_renewer(
    lease: TaskLease,
    *,
    interval_seconds: int | None = None,
) -> tuple[threading.Event, threading.Thread]:
    """Renew ownership in a daemon thread while synchronous Celery work runs."""
    stop = threading.Event()
    interval = interval_seconds or max(5, lease.ttl_seconds // 3)

    def _renew_loop() -> None:
        while not stop.wait(interval):
            if not renew_task_lease(lease):
                # Do not continue pretending ownership is healthy. The task
                # itself cannot be force-cancelled from this thread, but the
                # missing lease will prevent us from deleting a newer token and
                # will be visible in logs/metrics.
                logger.error("task_lease.ownership_lost key=%s", lease.key)
                return

    thread = threading.Thread(
        target=_renew_loop,
        name=f"task-lease-renew:{lease.key[-32:]}",
        daemon=True,
    )
    thread.start()
    return stop, thread
