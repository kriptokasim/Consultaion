from datetime import timedelta

from models import AuditLog, Debate, utcnow
from routes.admin.metrics import admin_metrics
from sqlmodel import Session


def test_referral_proxy_uses_matched_ip_grain_and_cannot_exceed_100(db_session: Session):
    now = utcnow()
    shared_ip = "203.0.113.44"
    db_session.add(
        AuditLog(
            action="view_shared_debate",
            target_type="debate",
            target_id="shared-artifact",
            meta={"ip_address": shared_ip},
            created_at=now - timedelta(hours=2),
        )
    )
    # A shared/NAT IP can produce multiple signups from one observed view.
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

    assert sharing["shared_views_30d"] == 1
    assert sharing["referred_signups_30d"] == 2
    assert sharing["shared_view_ips_30d"] == 1
    assert sharing["referred_signup_ips_30d"] == 1
    assert sharing["conversion_rate_30d"] == 100.0
    assert sharing["conversion_rate_30d"] <= 100.0


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
