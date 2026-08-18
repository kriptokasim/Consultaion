from datetime import timedelta

from auth import hash_password
from maintenance.retention import purge_old_debates
from models import (
    AdminEvent,
    AuditLog,
    ChallengeRound,
    ChallengeSession,
    ConversationVote,
    Debate,
    DebateAttempt,
    DebateCheckpoint,
    LLMUsageLog,
    Message,
    RedTeamSession,
    Score,
    TerminalTransition,
    User,
    Vote,
    utcnow,
)
from sqlmodel import Session, select

from config import settings


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
    db_session.add(
        Vote(
            debate_id=debate.id,
            method="ranked",
            rankings={"private": "ranking"},
            weights={"private": 1},
            result={"private": "result"},
        )
    )
    db_session.add(
        DebateCheckpoint(
            debate_id=debate.id,
            step="synthesis",
            context_meta={"private": "checkpoint context"},
            resume_token="secret-resume-token",
        )
    )
    db_session.add(
        DebateAttempt(
            debate_id=debate.id,
            attempt_number=1,
            status="failed",
            error_summary="Sensitive attempt error",
            meta={"private": "attempt metadata"},
        )
    )
    db_session.add(
        AdminEvent(
            level="error",
            message="Sensitive admin diagnostic",
            trace_id="trace-sensitive",
            debate_id=debate.id,
            meta={"private": "admin metadata"},
        )
    )
    db_session.add(
        TerminalTransition(
            debate_id=debate.id,
            transition_type="summary_email",
            status="completed",
            meta={"private": "transition metadata"},
        )
    )
    db_session.add(
        ConversationVote(
            conversation_id=debate.id,
            message_id="message-sensitive",
            user_id=user.id,
            vote=1,
            reason="Sensitive user feedback",
        )
    )
    db_session.add(
        RedTeamSession(
            debate_id=debate.id,
            user_id=user.id,
            proposal_text="Sensitive red-team proposal",
            lenses={"private": "lens"},
            critique_matrix={"private": "critique"},
        )
    )
    challenge = ChallengeSession(
        debate_id=debate.id,
        user_id=user.id,
        status="active",
    )
    db_session.add(challenge)
    db_session.flush()
    db_session.add(
        ChallengeRound(
            session_id=challenge.id,
            round_index=1,
            user_pushback="Sensitive pushback",
            model_response="Sensitive challenge response",
            action_taken="revise",
            revised_synthesis="Sensitive revised synthesis",
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

    assert db_session.exec(select(Vote).where(Vote.debate_id == debate.id)).first() is None
    assert db_session.exec(
        select(ConversationVote).where(ConversationVote.conversation_id == debate.id)
    ).first() is None
    assert db_session.exec(
        select(RedTeamSession).where(RedTeamSession.debate_id == debate.id)
    ).first() is None
    assert db_session.exec(
        select(ChallengeSession).where(ChallengeSession.debate_id == debate.id)
    ).first() is None
    assert db_session.exec(
        select(ChallengeRound).where(ChallengeRound.session_id == challenge.id)
    ).first() is None

    checkpoint = db_session.exec(
        select(DebateCheckpoint).where(DebateCheckpoint.debate_id == debate.id)
    ).first()
    assert checkpoint is not None
    assert checkpoint.context_meta is None
    assert checkpoint.resume_token is None

    attempt = db_session.exec(
        select(DebateAttempt).where(DebateAttempt.debate_id == debate.id)
    ).first()
    assert attempt is not None
    assert attempt.error_summary is None
    assert attempt.meta is None

    admin_event = db_session.exec(
        select(AdminEvent).where(AdminEvent.debate_id == debate.id)
    ).first()
    assert admin_event is not None
    assert admin_event.message == "[ANONYMIZED]"
    assert admin_event.trace_id is None
    assert admin_event.meta is None

    transition = db_session.exec(
        select(TerminalTransition).where(TerminalTransition.debate_id == debate.id)
    ).first()
    assert transition is not None
    assert transition.meta is None
