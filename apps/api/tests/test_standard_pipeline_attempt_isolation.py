from datetime import datetime, timedelta, timezone

import pytest


async def _cache_hit_checkpoint(
    _debate_id,
    _stage_key,
    _input_data,
    _run_fn,
    load_fn,
    **_kwargs,
):
    from database_async import async_session_scope

    async with async_session_scope() as session:
        return await load_fn(session)


@pytest.mark.anyio
async def test_retry_cache_hits_never_mix_attempt_rows(db_session, monkeypatch):
    from models import Debate, DebateAttempt, Message, Score, Vote
    from orchestration import checkpoints
    from orchestration.interfaces import DebateContext
    from orchestration.pipeline import StandardDebatePipeline
    from orchestration.state import DebateStateManager
    from schemas import AgentConfig, DebateConfig, JudgeConfig

    debate = Debate(id="attempt-isolation", prompt="test prompt long enough", status="running", mode="legacy", run_attempt=2)
    a1 = DebateAttempt(debate_id=debate.id, attempt_number=1, status="completed")
    a2 = DebateAttempt(debate_id=debate.id, attempt_number=2, status="running")
    db_session.add(debate)
    db_session.add(a1)
    db_session.add(a2)
    db_session.commit()

    now = datetime.now(timezone.utc)
    db_session.add_all(
        [
            Message(debate_id=debate.id, attempt_id=a1.id, round_index=1, role="candidate", persona="Old", content="old candidate"),
            Message(debate_id=debate.id, attempt_id=a2.id, round_index=1, role="candidate", persona="New", content="new candidate"),
            Message(debate_id=debate.id, attempt_id=a1.id, round_index=2, role="revised", persona="Old", content="old revised"),
            Message(debate_id=debate.id, attempt_id=a2.id, round_index=2, role="revised", persona="New", content="new revised"),
            Message(
                debate_id=debate.id,
                attempt_id=a1.id,
                round_index=4,
                role="synthesizer",
                persona="Synth",
                content="old attempt synthesis",
                created_at=now - timedelta(minutes=3),
            ),
            Message(
                debate_id=debate.id,
                attempt_id=a2.id,
                round_index=4,
                role="synthesizer",
                persona="Synth",
                content="earlier current synthesis",
                created_at=now - timedelta(minutes=2),
            ),
            Message(
                debate_id=debate.id,
                attempt_id=a2.id,
                round_index=4,
                role="synthesizer",
                persona="Synth",
                content="newest current synthesis",
                created_at=now - timedelta(minutes=1),
            ),
            Score(debate_id=debate.id, attempt_id=a1.id, persona="Old", judge="J", score=1.0, rationale="old"),
            Score(debate_id=debate.id, attempt_id=a2.id, persona="New", judge="J", score=9.0, rationale="new"),
            Vote(
                debate_id=debate.id,
                method="borda+condorcet",
                rankings={"order": ["Old"]},
                result={"_attempt_id": a1.id, "borda": {"Old": 1}},
            ),
            Vote(
                debate_id=debate.id,
                method="borda+condorcet",
                rankings={"order": ["New"]},
                result={"_attempt_id": a2.id, "borda": {"New": 1}},
            ),
        ]
    )
    db_session.commit()

    monkeypatch.setattr(checkpoints, "run_with_checkpoint", _cache_hit_checkpoint)

    manager = DebateStateManager(debate.id, attempt_id=a2.id)
    pipeline = StandardDebatePipeline(manager)
    context = DebateContext(
        debate_id=debate.id,
        prompt=debate.prompt,
        config=DebateConfig(
            agents=[AgentConfig(name="A", persona="p")],
            judges=[JudgeConfig(name="J")],
        ),
        channel_id=f"debate:{debate.id}",
        is_resume=True,
    )

    state = await pipeline.execute(context)

    assert [item["persona"] for item in state.candidates] == ["New"]
    assert [item["persona"] for item in state.revised_candidates] == ["New"]
    assert [item["persona"] for item in state.scores] == ["New"]
    assert state.ranking == ["New"]
    assert state.vote_details.get("_attempt_id") is None
    assert state.final_content == "newest current synthesis"


@pytest.mark.anyio
async def test_retry_cache_hit_reuses_one_prior_attempt_when_current_has_no_upstream_rows(
    db_session,
    monkeypatch,
):
    from models import Debate, DebateAttempt, Message
    from orchestration import checkpoints
    from orchestration.interfaces import DebateContext
    from orchestration.pipeline import StandardDebatePipeline
    from orchestration.state import DebateStateManager
    from schemas import AgentConfig, DebateConfig, JudgeConfig

    debate = Debate(id="attempt-reuse", prompt="test prompt long enough", status="running", mode="legacy", run_attempt=2)
    a1 = DebateAttempt(debate_id=debate.id, attempt_number=1, status="completed")
    a2 = DebateAttempt(debate_id=debate.id, attempt_number=2, status="running")
    db_session.add_all([debate, a1, a2])
    db_session.commit()
    db_session.add(
        Message(
            debate_id=debate.id,
            attempt_id=a1.id,
            round_index=1,
            role="candidate",
            persona="Source",
            content="reused source candidate",
        )
    )
    db_session.commit()

    async def selective_checkpoint(
        _debate_id,
        stage_key,
        _input_data,
        run_fn,
        load_fn,
        **_kwargs,
    ):
        if stage_key == "draft":
            from database_async import async_session_scope
            async with async_session_scope() as session:
                return await load_fn(session)
        raise RuntimeError("stop-after-draft")

    monkeypatch.setattr(checkpoints, "run_with_checkpoint", selective_checkpoint)

    manager = DebateStateManager(debate.id, attempt_id=a2.id)
    pipeline = StandardDebatePipeline(manager)
    context = DebateContext(
        debate_id=debate.id,
        prompt=debate.prompt,
        config=DebateConfig(
            agents=[AgentConfig(name="A", persona="p")],
            judges=[JudgeConfig(name="J")],
        ),
        channel_id=f"debate:{debate.id}",
        is_resume=True,
    )

    with pytest.raises(RuntimeError, match="stop-after-draft"):
        await pipeline.execute(context)
