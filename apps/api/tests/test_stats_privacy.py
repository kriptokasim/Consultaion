import uuid

import pytest
from models import Debate, Score, User
from routes.stats import get_hall_of_fame_stats, get_model_detail, get_model_leaderboard_stats


def _debate(session, *, owner: User | None, prompt: str, is_public: bool) -> Debate:
    debate = Debate(
        id=str(uuid.uuid4()),
        prompt=prompt,
        status="completed",
        user_id=owner.id if owner else None,
        config={"is_public": is_public},
        final_content=f"final:{prompt}",
    )
    session.add(debate)
    session.add(
        Score(
            debate_id=debate.id,
            persona="model-a",
            judge="judge-a",
            score=0.9,
            rationale="test",
        )
    )
    return debate


@pytest.mark.anyio
async def test_anonymous_stats_exclude_private_debates(db_session):
    owner = User(
        id=str(uuid.uuid4()),
        email=f"stats-owner-{uuid.uuid4().hex}@example.com",
        password_hash="hash",
    )
    db_session.add(owner)
    db_session.flush()
    private = _debate(db_session, owner=owner, prompt="private prompt", is_public=False)
    public = _debate(db_session, owner=owner, prompt="public prompt", is_public=True)
    ownerless = _debate(db_session, owner=None, prompt="ownerless prompt", is_public=False)
    db_session.commit()

    detail = await get_model_detail("model-a", limit=50, session=db_session, current_user=None)
    detail_ids = {item["debate_id"] for item in detail.recent_debates}
    assert private.id not in detail_ids
    assert ownerless.id not in detail_ids
    assert detail_ids == {public.id}

    hall = await get_hall_of_fame_stats(
        limit=50,
        sort="top",
        model=None,
        start_date=None,
        end_date=None,
        session=db_session,
        current_user=None,
    )
    assert {item.id for item in hall.items} == {public.id}
    assert all(item.prompt != "private prompt" for item in hall.items)

    leaderboard = await get_model_leaderboard_stats(session=db_session, current_user=None)
    assert leaderboard[0].total_debates == 1


@pytest.mark.anyio
async def test_owner_stats_include_owned_private_debate(db_session):
    owner = User(
        id=str(uuid.uuid4()),
        email=f"stats-owner-{uuid.uuid4().hex}@example.com",
        password_hash="hash",
    )
    db_session.add(owner)
    db_session.flush()
    private = _debate(db_session, owner=owner, prompt="private prompt", is_public=False)
    db_session.commit()

    detail = await get_model_detail("model-a", limit=50, session=db_session, current_user=owner)
    assert {item["debate_id"] for item in detail.recent_debates} == {private.id}
