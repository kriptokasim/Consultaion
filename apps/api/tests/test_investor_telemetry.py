from auth import COOKIE_NAME
from fastapi.testclient import TestClient
from models import AuditLog
from sqlmodel import Session, select


def _latest_audit(db_session: Session, action: str, target_id: str) -> AuditLog | None:
    db_session.expire_all()
    return db_session.exec(
        select(AuditLog)
        .where(AuditLog.action == action)
        .where(AuditLog.target_id == target_id)
        .order_by(AuditLog.id.desc())
    ).first()


def test_decision_creation_audit_persists_without_raw_prompt(
    authenticated_client: TestClient,
    db_session: Session,
):
    prompt = "Investor telemetry creation privacy test prompt"
    create_res = authenticated_client.post(
        "/debates",
        json={"prompt": prompt, "mode": "arena"},
    )
    assert create_res.status_code == 200
    debate_id = create_res.json()["id"]

    audit_log = _latest_audit(db_session, "debate_created", debate_id)
    assert audit_log is not None
    assert audit_log.meta is not None
    assert audit_log.meta.get("prompt_length") == len(prompt)
    assert "prompt" not in audit_log.meta
    assert prompt not in str(audit_log.meta)


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

    audit_log = _latest_audit(db_session, "debate_shared", debate_id)
    assert audit_log is not None
    assert audit_log.target_type == "debate"
    assert audit_log.meta is not None
    assert audit_log.meta.get("is_public") is True


def test_public_view_event_persists_after_anonymous_read(
    client: TestClient,
    authenticated_client: TestClient,
    db_session: Session,
):
    create_res = authenticated_client.post(
        "/debates",
        json={"prompt": "Investor telemetry public view test prompt", "mode": "arena"},
    )
    assert create_res.status_code == 200
    debate_id = create_res.json()["id"]

    share_res = authenticated_client.post(
        f"/debates/{debate_id}/share",
        json={"is_public": True},
    )
    assert share_res.status_code == 200

    client.cookies.delete(COOKIE_NAME)
    read_res = client.get(f"/debates/{debate_id}")
    assert read_res.status_code == 200

    audit_log = _latest_audit(db_session, "view_shared_debate", debate_id)
    assert audit_log is not None
    assert audit_log.user_id is None
    assert audit_log.meta is not None
    # Public-share acquisition is token based; visitor IP retention is
    # intentionally suppressed by the central audit privacy policy.
    assert "ip_address" not in audit_log.meta
    assert "client_ip" not in audit_log.meta
    assert "remote_addr" not in audit_log.meta
