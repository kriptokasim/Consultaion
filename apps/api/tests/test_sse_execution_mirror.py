import pytest


class _Backend:
    def __init__(self):
        self.events = []

    async def publish(self, channel_id, event):
        self.events.append((channel_id, event))


@pytest.mark.anyio
async def test_hot_delta_mirror_mismatch_rejects_before_transport(monkeypatch):
    import orchestration.execution_lease_mirror as mirror
    from orchestration.execution_context import (
        ExecutionLease,
        bind_execution_lease,
        reset_execution_lease,
    )
    from orchestration.execution_lease import ExecutionSupersededError
    from sse_execution_guard import ExecutionFencedSSEBackend

    async def mismatch(_lease):
        return mirror.MirrorVerification.MISMATCH

    monkeypatch.setattr(mirror, "verify_execution_lease_mirror", mismatch)
    lease = ExecutionLease.create(
        "mirror-mismatch",
        owner_id="owner-a",
        lease_epoch=3,
        run_attempt=1,
    )
    token = bind_execution_lease(lease)
    backend = _Backend()
    try:
        with pytest.raises(ExecutionSupersededError):
            await ExecutionFencedSSEBackend(backend).publish(
                "debate:mirror-mismatch",
                {"type": "model_response_delta", "delta": "stale"},
            )
    finally:
        reset_execution_lease(token)

    assert lease.lease_lost_event.is_set()
    assert backend.events == []


@pytest.mark.anyio
async def test_hot_delta_missing_mirror_falls_back_to_database(monkeypatch):
    import orchestration.execution_lease_mirror as mirror
    import sse_execution_guard as guard
    from orchestration.execution_context import (
        ExecutionLease,
        bind_execution_lease,
        reset_execution_lease,
    )

    async def unknown(_lease):
        return mirror.MirrorVerification.UNKNOWN

    db_checks = 0

    async def db_owned(_lease):
        nonlocal db_checks
        db_checks += 1
        return None

    monkeypatch.setattr(mirror, "verify_execution_lease_mirror", unknown)
    monkeypatch.setattr(guard, "_assert_live_publish_ownership", db_owned)

    lease = ExecutionLease.create(
        "mirror-unknown",
        owner_id="owner-a",
        lease_epoch=1,
        run_attempt=1,
    )
    token = bind_execution_lease(lease)
    backend = _Backend()
    try:
        await guard.ExecutionFencedSSEBackend(backend).publish(
            "debate:mirror-unknown",
            {"type": "arena_synthesis_delta", "delta": "fresh"},
        )
    finally:
        reset_execution_lease(token)

    assert db_checks == 1
    assert len(backend.events) == 1


@pytest.mark.anyio
async def test_mirror_ttl_is_shorter_than_authoritative_database_lease(monkeypatch):
    import redis_pool
    from orchestration.execution_context import ExecutionLease
    from orchestration.execution_lease_mirror import publish_execution_lease_mirror

    class FakeRedis:
        def __init__(self):
            self.calls = []

        async def set(self, key, value, *, ex=None):
            self.calls.append((key, value, ex))
            return True

    redis = FakeRedis()
    monkeypatch.setattr(redis_pool, "get_async_redis_client", lambda: redis)
    lease = ExecutionLease.create(
        "mirror-ttl",
        owner_id="owner-a",
        lease_epoch=7,
        run_attempt=1,
    )

    assert await publish_execution_lease_mirror(lease, lease_seconds=30) is True
    assert redis.calls[0][2] == 28


@pytest.mark.anyio
async def test_explicit_release_sets_shared_lost_event(db_session):
    from models import Debate, DebateAttempt
    from orchestration.execution_lease import acquire_execution_lease, release_execution_lease

    debate = Debate(
        id="release-event",
        prompt="release event test",
        status="queued",
        run_attempt=0,
    )
    attempt = DebateAttempt(
        debate_id=debate.id,
        attempt_number=1,
        status="queued",
    )
    db_session.add_all([debate, attempt])
    db_session.commit()

    acquired = await acquire_execution_lease(debate.id, lease_seconds=30)
    assert acquired.acquired
    assert not acquired.lease.lease_lost_event.is_set()

    assert await release_execution_lease(acquired.lease) is True
    assert acquired.lease.lease_lost_event.is_set()
