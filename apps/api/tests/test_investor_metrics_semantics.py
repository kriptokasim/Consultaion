from datetime import timedelta

from models import AuditLog, Debate, User, utcnow
from routes.admin.metrics import admin_metrics
from services.referrals import claim_referral, issue_referral_token, record_referral_visit
from sqlmodel import Session


def test_general_investor_metrics_use_token_attribution_not_ip(db_session: Session):
    now = utcnow()
    owner = User(email="metrics-ref-owner@example.com", password_hash="hashed", is_active=True)
    db_session.add(owner)
    db_session.commit()
    db_session.refresh(owner)

    debate = Debate(
        id="shared-artifact-token",
        prompt="Shared referral artifact",
        status="completed",
        config={"is_public": True},
        user_id=owner.id,
        created_at=now - timedelta(hours=3),
        updated_at=now - timedelta(hours=2),
    )
    db_session.add(debate)
    db_session.commit()

    token, _ = issue_referral_token(
        db_session,
        debate_id=debate.id,
        created_by_user_id=owner.id,
    )
    db_session.commit()
    assert record_referral_visit(db_session, token=token) is True

    # Claiming account must be newer than the issued token.
    visitor = User(email="metrics-ref-visitor@example.com", password_hash="hashed", is_active=True)
    db_session.add(visitor)
    db_session.commit()
    db_session.refresh(visitor)
    assert claim_referral(db_session, token=token, user_id=visitor.id) is True

    # Historical IP-shaped rows must not influence the canonical conversion.
    shared_ip = "203.0.113.44"
    db_session.add(
        AuditLog(
            action="view_shared_debate",
            target_type="debate",
            target_id="legacy-ip-artifact",
            meta={"ip_address": shared_ip},
            created_at=now - timedelta(hours=2),
        )
    )
    for minutes_ago in (60, 30):
        db_session.add(
            AuditLog(
                action="register",
                target_type="user",
                meta={"ip_address": shared_ip},
                created_at=now - timedelta(minutes=minutes_ago),
            )
        )
    db_session.commit()

    payload = admin_metrics(session=db_session, _=None)
    sharing = payload["plg_sharing"]

    assert sharing["referral_issued_links_30d"] == 1
    assert sharing["referral_visited_links_30d"] == 1
    assert sharing["referred_signups_30d"] == 1
    assert sharing["conversion_rate_30d"] == 100.0
    assert sharing["attribution_method"] == "sha256_referral_token"
    assert sharing["uses_visitor_ip"] is False
    assert sharing["stores_raw_token"] is False
    assert sharing["shared_view_ips_30d"] == 0
    assert sharing["referred_signup_ips_30d"] == 0


def test_active_debates_means_in_progress_not_every_run_created_today(db_session: Session):
    now = utcnow()
    db_session.add(
        Debate(
            id="completed-today",
            prompt="Completed today",
            status="completed",
            config={},
            created_at=now - timedelta(hours=1),
            updated_at=now - timedelta(minutes=30),
        )
    )
    db_session.add(
        Debate(
            id="running-older",
            prompt="Still running",
            status="running",
            config={},
            created_at=now - timedelta(days=2),
            updated_at=now - timedelta(minutes=5),
        )
    )
    db_session.commit()

    payload = admin_metrics(session=db_session, _=None)
    activation = payload["activation"]

    assert activation["runs_created_24h"] == 1
    assert activation["in_progress_runs"] == 1
    assert activation["active_debates"] == 1
