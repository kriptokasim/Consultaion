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
async def test_newer_attempt_scores_never_pair_with_unmarked_legacy_vote(db_session, monkeypatch):
    from models import Debate, DebateAttempt, Message, Score, Vote
    from orchestration import checkpoints
    from orchestration.interfaces import DebateContext
    from orchestration.pipeline import StandardDebatePipeline
    from orchestration.state import DebateStateManager
    from schemas import AgentConfig, DebateConfig, JudgeConfig

    debate = Debate(
        id="vote-isolation-newer",
        prompt="vote isolation prompt long enough",
        status="running",
        mode="legacy",
        run_attempt=2,
    )
    a1 = DebateAttempt(debate_id=debate.id, attempt_number=1, status="completed")
    a2 = DebateAttempt(debate_id=debate.id, attempt_number=2, status="running")
    db_session.add_all([debate, a1, a2])
    db_session.commit()

    db_session.add_all(
        [
            Message(
                debate_id=debate.id,
                attempt_id=a2.id,
                round_index=1,
                role="candidate",
                persona="Current",
                content="current candidate",
            ),
            Message(
                debate_id=debate.id,
                attempt_id=a2.id,
                round_index=2,
                role="revised",
                persona="Current",
                content="current revised",
            ),
            Score(
                debate_id=debate.id,
                attempt_id=a2.id,
                persona="Current",
                judge="J",
                score=9.0,
                rationale="current score",
            ),
            # Pre-attempt-marker legacy vote from attempt 1. This must not be
            # paired with attempt 2 scores merely because no current vote row
            # exists yet.
            Vote(
                debate_id=debate.id,
                method="borda+condorcet",
                rankings={"order": ["LegacyWinner"]},
                result={"borda": {"LegacyWinner": 99}},
            ),
            Message(
                debate_id=debate.id,
                attempt_id=a2.id,
                round_index=4,
                role="synthesizer",
                persona="Synth",
                content="current synthesis",
            ),
        ]
    )
    db_session.commit()

    monkeypatch.setattr(checkpoints, "run_with_checkpoint", _cache_hit_checkpoint)

    pipeline = StandardDebatePipeline(DebateStateManager(debate.id, attempt_id=a2.id))
    state = await pipeline.execute(
        DebateContext(
            debate_id=debate.id,
            prompt=debate.prompt,
            config=DebateConfig(
                agents=[AgentConfig(name="A", persona="p")],
                judges=[JudgeConfig(name="J")],
            ),
            channel_id=f"debate:{debate.id}",
            is_resume=True,
        )
    )

    assert [item["persona"] for item in state.scores] == ["Current"]
    assert state.ranking == []
    assert state.vote_details == {}
    assert state.final_content == "current synthesis"
