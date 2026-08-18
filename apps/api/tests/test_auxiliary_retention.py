from datetime import timedelta

from maintenance.retention import purge_old_auxiliary_ai_content
from models import (
    CodingRun,
    CodingTurn,
    Debate,
    OracleBranch,
    OracleSession,
    RedTeamSession,
    User,
    utcnow,
)
from sqlmodel import Session, select

from config import settings


def test_auxiliary_ai_content_uses_debate_retention_window(
    db_session: Session,
    monkeypatch,
):
    monkeypatch.setattr(settings, "RETAIN_DEBATES_DAYS", 30)
    now = utcnow()
    old = now - timedelta(days=60)

    user = User(email="aux-retention@example.com", password_hash="hashed")
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)

    old_coding = CodingRun(
        user_id=user.id,
        status="completed",
        diff_preview="sensitive diff",
        created_at=old,
        updated_at=old,
    )
    fresh_coding = CodingRun(
        user_id=user.id,
        status="completed",
        diff_preview="fresh diff",
        created_at=now,
        updated_at=now,
    )
    db_session.add(old_coding)
    db_session.add(fresh_coding)
    db_session.flush()
    db_session.add(
        CodingTurn(
            coding_run_id=old_coding.id,
            prompt="sensitive coding prompt",
            sequence=1,
            status="completed",
            created_at=old,
        )
    )

    old_oracle = OracleSession(
        user_id=user.id,
        prompt="sensitive oracle prompt",
        status="completed",
        created_at=old,
    )
    fresh_oracle = OracleSession(
        user_id=user.id,
        prompt="fresh oracle prompt",
        status="completed",
        created_at=now,
    )
    db_session.add(old_oracle)
    db_session.add(fresh_oracle)
    db_session.flush()
    db_session.add(
        OracleBranch(
            session_id=old_oracle.id,
            assumption_text="sensitive assumption",
            reasoning_nodes={"private": "reasoning"},
            created_at=old,
        )
    )

    debate = Debate(
        id="aux-retention-linked-debate",
        prompt="current debate",
        status="completed",
        user_id=user.id,
        created_at=now,
        updated_at=now,
    )
    db_session.add(debate)
    db_session.flush()

    standalone_old = RedTeamSession(
        user_id=user.id,
        debate_id=None,
        proposal_text="sensitive standalone proposal",
        created_at=old,
    )
    standalone_fresh = RedTeamSession(
        user_id=user.id,
        debate_id=None,
        proposal_text="fresh standalone proposal",
        created_at=now,
    )
    linked_old = RedTeamSession(
        user_id=user.id,
        debate_id=debate.id,
        proposal_text="debate-owned proposal",
        created_at=old,
    )
    db_session.add(standalone_old)
    db_session.add(standalone_fresh)
    db_session.add(linked_old)
    db_session.commit()

    result = purge_old_auxiliary_ai_content(db_session)
    db_session.expire_all()

    assert result == {
        "coding_runs_deleted": 1,
        "oracle_sessions_deleted": 1,
        "standalone_redteam_sessions_deleted": 1,
    }

    assert db_session.get(CodingRun, old_coding.id) is None
    assert db_session.exec(
        select(CodingTurn).where(CodingTurn.coding_run_id == old_coding.id)
    ).first() is None
    assert db_session.get(CodingRun, fresh_coding.id) is not None

    assert db_session.get(OracleSession, old_oracle.id) is None
    assert db_session.exec(
        select(OracleBranch).where(OracleBranch.session_id == old_oracle.id)
    ).first() is None
    assert db_session.get(OracleSession, fresh_oracle.id) is not None

    assert db_session.get(RedTeamSession, standalone_old.id) is None
    assert db_session.get(RedTeamSession, standalone_fresh.id) is not None
    # Debate-linked RedTeam content is owned by purge_old_debates, not the
    # standalone auxiliary purge.
    assert db_session.get(RedTeamSession, linked_old.id) is not None
