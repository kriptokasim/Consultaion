def test_task_lease_is_single_owner_and_compare_release(monkeypatch):
    import redis_pool
    from worker.task_leases import (
        TaskLeaseAcquireResult,
        acquire_task_lease,
        release_task_lease,
        renew_task_lease,
    )

    class FakeRedis:
        def __init__(self):
            self.values = {}

        def set(self, key, value, nx=False, ex=None):
            if nx and key in self.values:
                return False
            self.values[key] = value
            return True

        def eval(self, script, _numkeys, key, owner, *args):
            if "expire" in script:
                return 1 if self.values.get(key) == owner else 0
            if self.values.get(key) == owner:
                del self.values[key]
                return 1
            return 0

    redis = FakeRedis()
    monkeypatch.setattr(redis_pool, "get_sync_redis_client", lambda: redis)

    result, first = acquire_task_lease("divergence", "debate-a", ttl_seconds=60)
    assert result is TaskLeaseAcquireResult.ACQUIRED
    assert first is not None
    assert renew_task_lease(first) is True

    second_result, second = acquire_task_lease("divergence", "debate-a", ttl_seconds=60)
    assert second_result is TaskLeaseAcquireResult.HELD
    assert second is None

    # A stale owner token may never release a newer worker's lock.
    redis.values[first.key] = "new-owner"
    release_task_lease(first)
    assert redis.values[first.key] == "new-owner"


def test_task_lease_reports_backend_unavailable(monkeypatch):
    import redis_pool
    from worker.task_leases import TaskLeaseAcquireResult, acquire_task_lease

    monkeypatch.setattr(redis_pool, "get_sync_redis_client", lambda: None)
    result, lease = acquire_task_lease("divergence", "debate-a")
    assert result is TaskLeaseAcquireResult.BACKEND_UNAVAILABLE
    assert lease is None
