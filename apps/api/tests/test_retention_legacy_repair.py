from datetime import timedelta

from auth import hash_password
from maintenance.retention import purge_old_debates
from models import Debate, Message, Score, User, utcnow
from sqlmodel import Session, select

from config import settings


def test_retention_repairs_legacy_prompt_only_anonymization(
    db_session: Session,
    monkeypatch,
):
    monkeypatch.setattr(settings, "RETAIN_DEBATES_DAYS", 30)

    user = User(
        email="legacy-retention@example.com",
        password_hash=hash_password("StrongPass#LegacyRetention1"),
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)

    # Simulate the historical retention implementation: only prompt was
    # anonymized while user linkage and normalized content survived.
    debate = Debate(
        id="legacy-prompt-only-retention",
        prompt="[ANONYMIZED]",
        status="completed",
        user_id=user.id,
        config={"legacy": "still sensitive"},
        final_content="Sensitive final content left by old purge",
        created_at=utcnow() - timedelta(days=60),
        updated_at=utcnow() - timedelta(days=59),
    )
    db_session.add(debate)
    db_session.add(
        Message(
            debate_id=debate.id,
            round_index=0,
            role="arena_response",
            persona="Private persona",
            content="Sensitive normalized model output",
            meta={"private": "message metadata"},
        )
    )
    db_session.add(
        Score(
            debate_id=debate.id,
            persona="model-a",
            judge="judge-a",
            score=7.0,
            rationale="Sensitive normalized rationale",
            meta={"private": "score metadata"},
        )
    )
    db_session.commit()

    assert purge_old_debates(db_session) == 1
    db_session.expire_all()

    repaired = db_session.get(Debate, debate.id)
    assert repaired.prompt == "[ANONYMIZED]"
    assert repaired.user_id is None
    assert repaired.config is None
    assert repaired.final_content is None

    message = db_session.exec(select(Message).where(Message.debate_id == debate.id)).first()
    assert message is not None
    assert message.content == "[ANONYMIZED]"
    assert message.persona is None
    assert message.meta is None

    score = db_session.exec(select(Score).where(Score.debate_id == debate.id)).first()
    assert score is not None
    assert score.rationale == "[ANONYMIZED]"
    assert score.meta is None
