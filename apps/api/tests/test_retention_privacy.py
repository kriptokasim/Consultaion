from datetime import timedelta

from auth import hash_password
from config import settings
from maintenance.retention import purge_old_debates
from models import AuditLog, Debate, LLMUsageLog, Message, Score, User, utcnow
from sqlmodel import Session, select


def test_retention_scrubs_normalized_debate_content(
    db_session: Session,
    monkeypatch,
):
    monkeypatch.setattr(settings, "RETAIN_DEBATES_DAYS", 30)

    user = User(
        email="retention@example.com",
        password_hash=hash_password("StrongPass#Retention1"),
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)

    debate = Debate(
        id="retention-old-debate",
        prompt="Sensitive customer acquisition strategy",
        status="completed",
        config={"is_public": True, "custom": "sensitive config"},
        panel_config={"custom": "sensitive panel"},
        routing_meta={"debug": "sensitive route metadata"},
        final_content="Sensitive final decision",
        final_meta={"reasoning": "sensitive synthesis metadata"},
        user_id=user.id,
        created_at=utcnow() - timedelta(days=60),
        updated_at=utcnow() - timedelta(days=59),
    )
    db_session.add(debate)
    db_session.add(
        Message(
            debate_id=debate.id,
            round_index=0,
            role="arena_response",
            persona="Customer-specific persona",
            content="Sensitive model response",
            meta={"synthesis_report": {"summary": "Sensitive summary"}},
        )
    )
    db_session.add(
        Score(
            debate_id=debate.id,
            persona="model-a",
            judge="judge-a",
            score=8.0,
            rationale="Sensitive scoring rationale",
            meta={"detail": "Sensitive score metadata"},
        )
    )
    db_session.add(
        LLMUsageLog(
            debate_id=debate.id,
            user_id=user.id,
            provider="openai",
            model="gpt-test",
            total_tokens=100,
            cost_usd=0.01,
            error_message="Sensitive provider error context",
        )
    )
    db_session.add(
        AuditLog(
            user_id=user.id,
            action="view_shared_debate",
            target_type="debate",
            target_id=debate.id,
            meta={"ip_address": "203.0.113.7", "email": user.email},
        )
    )
    db_session.commit()

    assert purge_old_debates(db_session) == 1
    db_session.expire_all()

    scrubbed_debate = db_session.get(Debate, debate.id)
    assert scrubbed_debate is not None
    assert scrubbed_debate.prompt == "[ANONYMIZED]"
    assert scrubbed_debate.final_content is None
    assert scrubbed_debate.final_meta is None
    assert scrubbed_debate.config is None
    assert scrubbed_debate.panel_config is None
    assert scrubbed_debate.routing_meta is None
    assert scrubbed_debate.user_id is None
    assert scrubbed_debate.team_id is None

    message = db_session.exec(select(Message).where(Message.debate_id == debate.id)).first()
    assert message is not None
    assert message.content == "[ANONYMIZED]"
    assert message.persona is None
    assert message.meta is None

    score = db_session.exec(select(Score).where(Score.debate_id == debate.id)).first()
    assert score is not None
    assert score.score == 8.0
    assert score.rationale == "[ANONYMIZED]"
    assert score.meta is None

    usage = db_session.exec(
        select(LLMUsageLog).where(LLMUsageLog.debate_id == debate.id)
    ).first()
    assert usage is not None
    assert usage.user_id is None
    assert usage.error_message is None
    assert usage.cost_usd == 0.01

    audit = db_session.exec(
        select(AuditLog)
        .where(AuditLog.target_type == "debate")
        .where(AuditLog.target_id == debate.id)
    ).first()
    assert audit is not None
    assert audit.user_id is None
    assert audit.meta == {}
