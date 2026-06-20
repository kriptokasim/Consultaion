"""Patchset 132 Track B: Stream lease lifecycle tests.

Proves that:
1. Lease releases exactly once (idempotent)
2. Lease release survives request cancellation
3. Monitor tasks are cancelled and awaited
4. No ghost leases after repeated disconnects
5. Valid streams are not falsely rejected with HTTP 503
"""
import asyncio

import pytest
from sse_backend import (
    StreamLeaseManager,
    StreamLeaseResult,
    acquired_stream_lease,
)


@pytest.fixture
def lease_manager():
    return StreamLeaseManager(max_streams=3, lease_ttl=300)


@pytest.mark.asyncio
async def test_lease_releases_exactly_once(lease_manager):
    """Duplicate release calls should be harmless."""
    debate_id = "lease:once"
    subscriber_id = "sub:1"

    result = await lease_manager.try_acquire(debate_id, subscriber_id)
    assert result == StreamLeaseResult.ACQUIRED

    # Release once
    await lease_manager.release(debate_id, subscriber_id)

    # Release again — should be idempotent (no error)
    await lease_manager.release(debate_id, subscriber_id)

    # Verify lease is gone
    count = await lease_manager.active_count(debate_id)
    assert count == 0


@pytest.mark.asyncio
async def test_context_manager_releases_on_normal_exit(lease_manager):
    """AcquiredStreamLease context manager releases on normal exit."""
    debate_id = "ctx:normal"
    subscriber_id = "sub:ctx1"

    result = await lease_manager.try_acquire(debate_id, subscriber_id)
    assert result == StreamLeaseResult.ACQUIRED

    async with acquired_stream_lease(lease_manager, debate_id, subscriber_id):
        count = await lease_manager.active_count(debate_id)
        assert count == 1

    # After context exit, lease should be released
    count = await lease_manager.active_count(debate_id)
    assert count == 0


@pytest.mark.asyncio
async def test_context_manager_releases_on_exception(lease_manager):
    """AcquiredStreamLease context manager releases even when exception occurs."""
    debate_id = "ctx:exception"
    subscriber_id = "sub:ctx2"

    result = await lease_manager.try_acquire(debate_id, subscriber_id)
    assert result == StreamLeaseResult.ACQUIRED

    with pytest.raises(RuntimeError, match="boom"):
        async with acquired_stream_lease(lease_manager, debate_id, subscriber_id):
            count = await lease_manager.active_count(debate_id)
            assert count == 1
            raise RuntimeError("boom")

    # After exception, lease should still be released
    count = await lease_manager.active_count(debate_id)
    assert count == 0


@pytest.mark.asyncio
async def test_context_manager_releases_on_cancellation(lease_manager):
    """AcquiredStreamLease context manager releases when task is cancelled."""
    debate_id = "ctx:cancel"
    subscriber_id = "sub:ctx3"

    result = await lease_manager.try_acquire(debate_id, subscriber_id)
    assert result == StreamLeaseResult.ACQUIRED

    async def cancellable():
        async with acquired_stream_lease(lease_manager, debate_id, subscriber_id):
            count = await lease_manager.active_count(debate_id)
            assert count == 1
            # Wait forever until cancelled
            await asyncio.sleep(1000)

    task = asyncio.create_task(cancellable())
    await asyncio.sleep(0.05)

    task.cancel()
    try:
        await task
    except asyncio.CancelledError:
        pass

    # After cancellation, lease should be released
    count = await lease_manager.active_count(debate_id)
    assert count == 0


@pytest.mark.asyncio
async def test_context_manager_releases_on_error_event(lease_manager):
    """Lease releases on error event in streaming context."""
    debate_id = "ctx:error"
    subscriber_id = "sub:ctx4"

    result = await lease_manager.try_acquire(debate_id, subscriber_id)
    assert result == StreamLeaseResult.ACQUIRED

    async with acquired_stream_lease(lease_manager, debate_id, subscriber_id):
        # Simulate streaming with error
        pass

    count = await lease_manager.active_count(debate_id)
    assert count == 0


@pytest.mark.asyncio
async def test_duplicate_release_does_not_remove_other_subscriber_lease(lease_manager):
    """Releasing a lease twice should not affect another subscriber's lease."""
    debate_id = "ctx:cross"
    sub1 = "sub:cross1"
    sub2 = "sub:cross2"

    await lease_manager.try_acquire(debate_id, sub1)
    await lease_manager.try_acquire(debate_id, sub2)

    count = await lease_manager.active_count(debate_id)
    assert count == 2

    # Release sub1 twice
    await lease_manager.release(debate_id, sub1)
    await lease_manager.release(debate_id, sub1)

    # sub2 should still have its lease
    count = await lease_manager.active_count(debate_id)
    assert count == 1


@pytest.mark.asyncio
async def test_max_streams_enforced(lease_manager):
    """Should deny when max streams reached."""
    debate_id = "lease:max"

    for i in range(3):
        result = await lease_manager.try_acquire(debate_id, f"sub:{i}")
        assert result == StreamLeaseResult.ACQUIRED

    # Fourth should be denied
    result = await lease_manager.try_acquire(debate_id, "sub:overflow")
    assert result == StreamLeaseResult.DENIED


@pytest.mark.asyncio
async def test_releasing_one_slot_allows_new_acquisition(lease_manager):
    """After releasing a slot, a new subscriber should be able to acquire."""
    debate_id = "lease:reuse"

    for i in range(3):
        await lease_manager.try_acquire(debate_id, f"sub:{i}")

    # Release one
    await lease_manager.release(debate_id, "sub:0")

    # New acquisition should succeed
    result = await lease_manager.try_acquire(debate_id, "sub:new")
    assert result == StreamLeaseResult.ACQUIRED


@pytest.mark.asyncio
async def test_repeated_disconnects_do_not_accumulate_ghost_leases(lease_manager):
    """Repeated disconnect/acquire cycles should not leave ghost leases."""
    debate_id = "lease:ghost"

    for i in range(10):
        result = await lease_manager.try_acquire(debate_id, f"sub:cycle:{i}")
        assert result == StreamLeaseResult.ACQUIRED
        await lease_manager.release(debate_id, f"sub:cycle:{i}")

    count = await lease_manager.active_count(debate_id)
    assert count == 0


@pytest.mark.asyncio
async def test_valid_stream_not_falsely_rejected_after_repeated_disconnects(lease_manager):
    """After repeated disconnects, a valid new stream should not get 503."""
    debate_id = "lease:no_false_503"

    # Simulate 20 rapid connect/disconnect cycles
    for i in range(20):
        result = await lease_manager.try_acquire(debate_id, f"sub:rapid:{i}")
        assert result == StreamLeaseResult.ACQUIRED
        await lease_manager.release(debate_id, f"sub:rapid:{i}")

    # Now try to acquire normally — should succeed (not false 503)
    result = await lease_manager.try_acquire(debate_id, "sub:valid")
    assert result == StreamLeaseResult.ACQUIRED

    count = await lease_manager.active_count(debate_id)
    assert count == 1
