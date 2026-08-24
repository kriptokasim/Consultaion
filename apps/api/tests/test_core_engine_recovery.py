from __future__ import annotations

from pathlib import Path


API_ROOT = Path(__file__).resolve().parents[1]


def _source(relative: str) -> str:
    return (API_ROOT / relative).read_text(encoding="utf-8")


def test_arena_quorum_never_synthesizes_fake_model_failures():
    source = _source("arena/engine.py")
    assert "quorum_finalized" not in source
    assert "for completed_task in asyncio.as_completed(tasks):" in source


def test_arena_terminal_publish_is_owned_by_orchestrator():
    engine = _source("arena/engine.py")
    orchestrator = _source("orchestrator.py")
    assert '"type": "arena_synthesis_finalized"' not in engine
    assert '"type": "arena_synthesis_finalized"' in orchestrator
    assert '"debate_completed"' in orchestrator


def test_synthesis_finalization_does_not_close_sse_transport():
    streaming = _source("routes/debates/streaming.py")
    terminal_line = next(
        line for line in streaming.splitlines() if "terminal_types =" in line
    )
    assert "arena_synthesis_finalized" not in terminal_line
    assert "debate_completed" in terminal_line
    assert "debate_failed" in terminal_line


def test_structured_debate_routing_is_explicit_and_realtime():
    orchestrator = _source("orchestrator.py")
    parliament = _source("parliament/engine.py")
    assert 'is_parliament = debate_mode == "debate"' in orchestrator
    assert "asyncio.as_completed(tasks)" in parliament
    assert 'await backend.publish(f"debate:{debate_id}", event)' in parliament
    assert "turns.sort(key=lambda turn: panel_order.get(turn.seat_id, 999))" in parliament


def test_structured_debate_terminal_failure_is_orchestrator_owned():
    parliament = _source("parliament/engine.py")
    orchestrator = _source("orchestrator.py")
    assert '"type": "debate_failed"' not in parliament
    assert '"type": "debate_failed"' in orchestrator


def test_structured_debate_failure_ratio_uses_executed_seats_only():
    parliament = _source("parliament/engine.py")
    assert "executed_seat_count = len(participants) + len(critics)" in parliament
    assert "total_seats = len(panel.seats)" not in parliament


def test_structured_debate_does_not_publish_raw_provider_errors():
    parliament = _source("parliament/engine.py")
    assert "safe_failure = classify_provider_exception(err)" in parliament
    assert '"error": safe_failure.message' in parliament
    assert '"error": str(err)[:200]' not in parliament


def test_structured_debate_uses_all_configured_judges():
    parliament = _source("parliament/engine.py")
    assert "*[_evaluate(judge) for judge in judges]" in parliament
    assert '"judge": "aggregate"' in parliament


def test_debate_panel_normalization_preserves_role_seats():
    crud = _source("routes/debates/crud.py")
    debate_block = crud.split('elif body.mode == "debate":', 1)[1].split(
        "# Routing decision", 1
    )[0]
    assert "seen_model_ids" not in debate_block
    assert '"seat_id": model_info.id' not in debate_block
    assert '"model": model_info.id' in debate_block


def test_arena_checkpoint_identity_includes_logical_attempt():
    arena = _source("arena/engine.py")
    assert '"run_attempt": run_attempt' in arena.split("perspectives_input =", 1)[1].split(
        "async def load_perspectives_fn", 1
    )[0]


def test_continuation_does_not_invent_new_logical_attempt():
    execution = _source("routes/debates/execution.py")
    continuation_block = execution.split("async def continue_debate_run", 1)[1].split(
        '@router.get("/debates/{debate_id}/continuations/', 1
    )[0]
    assert 'run_attempt=(getattr(debate, "run_attempt", 0) or 0) + 1' not in continuation_block


def test_retry_does_not_increment_debates_created_counter():
    execution = _source("routes/debates/execution.py")
    retry_helpers = execution.split("def _retry_needs_hosted_credit", 1)[1].split(
        '@router.post("/debates/{debate_id}/start")', 1
    )[0]
    assert "increment_debate_usage" not in retry_helpers
    assert "reserve_run_slot" in retry_helpers
