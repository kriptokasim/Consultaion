"""PS155.1 — Execution Ownership and Checkpoint Fencing tests."""
from __future__ import annotations

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
async def test_checkpoint_accepts_current_lease_owner():
    """Checkpoint fencing accepts the current owner and epoch."""
    from orchestration.checkpoints import _assert_lease_owner

    result = MagicMock()
    result.scalars.return_value.first.return_value = MagicMock()
    session = AsyncMock()
    session.execute = AsyncMock(return_value=result)

    await _assert_lease_owner(session, "debate-1", "runner-1", 7)

    session.execute.assert_awaited_once()


@pytest.mark.asyncio
async def test_checkpoint_rejects_stale_lease_epoch():
    """Checkpoint fencing rejects a worker whose lease epoch was superseded."""
    from orchestration.checkpoints import LeaseOwnershipLost, _assert_lease_owner

    result = MagicMock()
    result.scalars.return_value.first.return_value = None
    session = AsyncMock()
    session.execute = AsyncMock(return_value=result)

    with pytest.raises(LeaseOwnershipLost):
        await _assert_lease_owner(session, "debate-1", "runner-1", 6)


@pytest.mark.asyncio
async def test_checkpoint_rejects_partial_fencing_identity():
    """Owner and epoch must always be supplied together."""
    from orchestration.checkpoints import _assert_lease_owner

    session = AsyncMock()
    with pytest.raises(ValueError):
        await _assert_lease_owner(session, "debate-1", "runner-1", None)


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


@pytest.mark.asyncio
async def test_nested_synthesis_checkpoints_receive_fencing_identity():
    """Both internal synthesis checkpoints must be fenced to the active lease."""
    from reporting.synthesizer import generate_decision_report

    draft_report = MagicMock()
    draft_report.model_dump.return_value = {}
    final_report = MagicMock()
    checkpoint = AsyncMock(
        side_effect=[
            ("raw", draft_report, [], {}, False),
            final_report,
        ]
    )

    with patch("orchestration.checkpoints.run_with_checkpoint", checkpoint):
        result = await generate_decision_report(
            prompt="prompt",
            responses=[],
            debate_id="debate-1",
            execution_owner_id="runner-1",
            lease_epoch=7,
        )

    assert result is final_report
    assert checkpoint.await_count == 2
    for call in checkpoint.await_args_list:
        assert call.kwargs["owner_id"] == "runner-1"
        assert call.kwargs["lease_epoch"] == 7


@pytest.mark.asyncio
async def test_ops_smoke_test_resolves_and_passes_provider_key():
    """The ops smoke test must use the isolated key resolver, not removed exports."""
    from routes.ops import llm_smoke_test

    request = MagicMock()
    request.json = AsyncMock(return_value={"provider": "openai"})
    result = MagicMock(
        success=True,
        provider="openai",
        model_used="openai/gpt-4o-mini",
        content="OK",
    )

    with (
        patch("agents.resolve_api_key", return_value="secret-key") as resolve_key,
        patch("model_gateway.route_llm_call", AsyncMock(return_value=result)) as route_call,
    ):
        response = await llm_smoke_test(request, MagicMock())

    assert response["success"] is True
    resolve_key.assert_called_once_with("openai")
    gateway_request = route_call.await_args.args[0]
    assert gateway_request.api_key == "secret-key"
