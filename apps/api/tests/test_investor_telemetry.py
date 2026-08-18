from fastapi.testclient import TestClient
from models import AuditLog
from sqlmodel import Session, select


def test_share_event_persists_after_request(
    authenticated_client: TestClient,
    db_session: Session,
):
    create_res = authenticated_client.post(
        "/debates",
        json={"prompt": "Investor telemetry share test prompt", "mode": "arena"},
    )
    assert create_res.status_code == 200
    debate_id = create_res.json()["id"]

    share_res = authenticated_client.post(
        f"/debates/{debate_id}/share",
        json={"is_public": True},
    )
    assert share_res.status_code == 200

    # share_debate records telemetry after committing the primary mutation.
    # The request-scoped session does not commit on teardown, so this verifies
    # the audit helper is invoked through a committed standalone transaction.
    db_session.expire_all()
    audit_log = db_session.exec(
        select(AuditLog)
        .where(AuditLog.action == "debate_shared")
        .where(AuditLog.target_id == debate_id)
        .order_by(AuditLog.id.desc())
    ).first()

    assert audit_log is not None
    assert audit_log.target_type == "debate"
    assert audit_log.meta is not None
    assert audit_log.meta.get("is_public") is True
