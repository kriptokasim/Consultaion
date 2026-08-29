import pytest


def _seed_retry(db_session, *, debate_id: str):
    from models import Debate, DebateAttempt

    debate = Debate(
        id=debate_id,
        prompt="retry presentation test",
        status="scheduled",
        run_attempt=1,
        final_content="old final",
        final_meta={"ranking": ["old"]},
    )
    a1 = DebateAttempt(
        debate_id=debate.id,
        attempt_number=1,
        status="completed",
    )
    a2 = DebateAttempt(
        debate_id=debate.id,
        attempt_number=2,
        status="queued",
    )
    db_session.add_all([debate, a1, a2])
    db_session.commit()
    return debate


@pytest.mark.anyio
async def test_full_retry_clears_prior_terminal_payload_before_dispatch(db_session, monkeypatch):
    import debate_dispatch
    import retry_presentation_guard as guard
    from models import Debate

    debate = _seed_retry(db_session, debate_id="retry-presentation-clear")
    observed = {}

    async def fake_dispatch(*_args, **_kwargs):
        db_session.expire_all()
        current = db_session.get(Debate, debate.id)
        observed["content"] = current.final_content
        observed["meta"] = current.final_meta

    monkeypatch.setattr(guard, "_installed", False)
    monkeypatch.setattr(debate_dispatch, "dispatch_debate_run", fake_dispatch)
    guard.install_retry_presentation_guard()

    await debate_dispatch.dispatch_debate_run(
        debate.id,
        debate.prompt,
        f"debate:{debate.id}",
        {},
        None,
        trace_id=None,
        resume=True,
    )

    assert observed == {"content": None, "meta": None}


@pytest.mark.anyio
async def test_failed_retry_dispatch_restores_prior_terminal_payload(db_session, monkeypatch):
    import debate_dispatch
    import retry_presentation_guard as guard
    from models import Debate

    debate = _seed_retry(db_session, debate_id="retry-presentation-restore")

    async def fail_dispatch(*_args, **_kwargs):
        raise RuntimeError("broker unavailable")

    monkeypatch.setattr(guard, "_installed", False)
    monkeypatch.setattr(debate_dispatch, "dispatch_debate_run", fail_dispatch)
    guard.install_retry_presentation_guard()

    with pytest.raises(RuntimeError, match="broker unavailable"):
        await debate_dispatch.dispatch_debate_run(
            debate.id,
            debate.prompt,
            f"debate:{debate.id}",
            {},
            None,
            trace_id=None,
            resume=True,
        )

    db_session.expire_all()
    restored = db_session.get(Debate, debate.id)
    assert restored.final_content == "old final"
    assert restored.final_meta == {"ranking": ["old"]}
