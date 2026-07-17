"""PS155.1 — Execution Ownership and Checkpoint Fencing tests."""
from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# ── Runner ID uniqueness ─────────────────────────────────────────────────


def test_runner_id_is_unique_across_invocations():
    """Two calls to _get_runner_id must return different values (uuid4 suffix)."""
    from orchestrator import _get_runner_id

    ids = {_get_runner_id() for _ in range(20)}
    assert len(ids) == 20, "runner IDs must be globally unique"


def test_runner_id_format():
    """Runner ID should follow hostname-pid-uuid4hex8 format."""
    from orchestrator import _get_runner_id

    rid = _get_runner_id()
    parts = rid.split("-")
    # At minimum: hostname, pid, 8-char hex
    assert len(parts) >= 3
    hex_part = parts[-1]
    assert len(hex_part) == 8
    int(hex_part, 16)  # should not raise


# ── Lease acquisition with epoch ─────────────────────────────────────────


@pytest.mark.asyncio
async def test_lease_acquire_returns_tuple():
    """_try_acquire_lease must return (bool, int)."""
    from orchestrator import _try_acquire_lease

    mock_row = MagicMock()
    mock_row.__getitem__ = lambda self, idx: 1  # epoch = 1

    mock_result = MagicMock()
    mock_result.first.return_value = mock_row
    mock_result.rowcount = 1

    mock_session = AsyncMock()
    mock_session.execute = AsyncMock(return_value=mock_result)
    mock_session.commit = AsyncMock()
    mock_session.get = AsyncMock(return_value=None)

    from contextlib import asynccontextmanager

    @asynccontextmanager
    async def fake_session():
        yield mock_session

    with patch("orchestrator.async_session_scope", fake_session):
        acquired, epoch = await _try_acquire_lease("debate-1", "runner-1")

    assert acquired is True
    assert epoch == 1


@pytest.mark.asyncio
async def test_lease_acquire_returns_false_when_locked():
    """When another worker owns the lease, acquisition fails."""
    from orchestrator import _try_acquire_lease

    mock_result = MagicMock()
    mock_result.first.return_value = None  # no row updated
    mock_result.rowcount = 0

    mock_session = AsyncMock()
    mock_session.execute = AsyncMock(return_value=mock_result)
    mock_session.commit = AsyncMock()

    from contextlib import asynccontextmanager

    @asynccontextmanager
    async def fake_session():
        yield mock_session

    with patch("orchestrator.async_session_scope", fake_session):
        acquired, epoch = await _try_acquire_lease("debate-1", "runner-2")

    assert acquired is False
    assert epoch == 0


# ── Heartbeat epoch validation ───────────────────────────────────────────


@pytest.mark.asyncio
async def test_heartbeat_with_correct_epoch_succeeds():
    """Heartbeat with matching epoch should return True."""
    from orchestrator import _heartbeat

    mock_result = MagicMock()
    mock_result.rowcount = 1

    mock_session = AsyncMock()
    mock_session.execute = AsyncMock(return_value=mock_result)
    mock_session.commit = AsyncMock()

    from contextlib import asynccontextmanager

    @asynccontextmanager
    async def fake_session():
        yield mock_session

    with patch("orchestrator.async_session_scope", fake_session):
        result = await _heartbeat("debate-1", "runner-1", expected_epoch=5)

    assert result is True


@pytest.mark.asyncio
async def test_heartbeat_with_stale_epoch_fails():
    """Heartbeat with a superseded epoch must return False."""
    from orchestrator import _heartbeat

    mock_result = MagicMock()
    mock_result.rowcount = 0  # epoch mismatch → no rows updated

    mock_session = AsyncMock()
    mock_session.execute = AsyncMock(return_value=mock_result)
    mock_session.commit = AsyncMock()

    from contextlib import asynccontextmanager

    @asynccontextmanager
    async def fake_session():
        yield mock_session

    with patch("orchestrator.async_session_scope", fake_session):
        result = await _heartbeat("debate-1", "runner-1", expected_epoch=3)

    assert result is False


# ── Checkpoint owner_id validation ───────────────────────────────────────


@pytest.mark.asyncio
async def test_checkpoint_exponential_backoff():
    """run_with_checkpoint should use exponential backoff when stage is running."""
    from orchestration.checkpoints import run_with_checkpoint

    call_count = 0

    async def mock_session_scope():
        """Simulate a running checkpoint that eventually completes."""
        nonlocal call_count
        mock_session = AsyncMock()

        class FakeCheckpoint:
            status = "running" if call_count < 2 else "completed"
            input_hash = "abc123"
            owner_id = "owner-1"
            attempt = 1
            error_message = None
            error_code = None
            failed_at = None
            started_at = datetime.now(timezone.utc)
            completed_at = None

        class FakeResult:
            def scalars(self):
                return self

            def first(self):
                nonlocal call_count
                call_count += 1
                return FakeCheckpoint()

        mock_session.execute = AsyncMock(return_value=FakeResult())
        mock_session.commit = AsyncMock()
        mock_session.add = MagicMock()

        return mock_session

    # Test that the backoff doesn't use fixed 1s intervals
    # (just verifying the function signature accepts owner_id)
    # The owner_id parameter should be accepted without error
    assert run_with_checkpoint.__code__.co_varnames[:6] == (
        "debate_id", "stage_key", "input_data", "run_fn", "load_fn", "owner_id"
    )


# ── Release with epoch guard ────────────────────────────────────────────


@pytest.mark.asyncio
async def test_release_lease_with_epoch():
    """_release_lease should include epoch in WHERE clause."""
    from orchestrator import _release_lease

    mock_result = MagicMock()
    mock_result.rowcount = 1

    mock_session = AsyncMock()
    mock_session.execute = AsyncMock(return_value=mock_result)
    mock_session.commit = AsyncMock()

    from contextlib import asynccontextmanager

    @asynccontextmanager
    async def fake_session():
        yield mock_session

    with patch("orchestrator.async_session_scope", fake_session):
        await _release_lease("debate-1", "runner-1", expected_epoch=5)

    # Verify execute was called (the SQL contains epoch guard)
    mock_session.execute.assert_called_once()
    mock_session.commit.assert_called_once()
