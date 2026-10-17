"""POST /debates: idempotent replays and refunds after a failed create."""

from uuid import uuid4

from models import Debate, UsageCounter, UsageLedgerEntry, User
from sqlmodel import Session, select

PAYLOAD = {"prompt": "Idempotency test", "mode": "debate"}


def _user(db_session: Session) -> User:
    return db_session.exec(select(User).where(User.email == "normal@example.com")).one()


def _hour_runs_used(db_session: Session, user_id: str) -> int:
    db_session.expire_all()
    counter = db_session.exec(
        select(UsageCounter).where(UsageCounter.user_id == user_id, UsageCounter.period == "hour")
    ).first()
    return counter.runs_used if counter else 0


def test_same_idempotency_key_returns_the_first_run(authenticated_client, db_session):
    key = f"run-{uuid4().hex}"
    headers = {"X-Idempotency-Key": key}

    first = authenticated_client.post("/debates", json=PAYLOAD, headers=headers)
    second = authenticated_client.post("/debates", json=PAYLOAD, headers=headers)

    assert first.status_code == 200, first.text
    assert second.status_code == 200, second.text
    assert second.json()["id"] == first.json()["id"]
    assert second.json().get("idempotent_replay") is True

    user = _user(db_session)
    debates = db_session.exec(select(Debate).where(Debate.user_id == user.id)).all()
    assert len(debates) == 1
    # The replay reserved no second run slot.
    assert _hour_runs_used(db_session, user.id) == 1


def test_different_keys_create_separate_runs(authenticated_client, db_session):
    a = authenticated_client.post("/debates", json=PAYLOAD, headers={"X-Idempotency-Key": f"a-{uuid4().hex}"})
    b = authenticated_client.post("/debates", json=PAYLOAD, headers={"X-Idempotency-Key": f"b-{uuid4().hex}"})
    assert a.status_code == 200 and b.status_code == 200
    assert a.json()["id"] != b.json()["id"]


def test_invalid_idempotency_key_is_rejected_before_reserving(authenticated_client, db_session):
    response = authenticated_client.post("/debates", json=PAYLOAD, headers={"X-Idempotency-Key": "bad key!"})
    assert response.status_code == 400
    assert response.json()["error"]["code"] == "debate.invalid_idempotency_key"
    assert _hour_runs_used(db_session, _user(db_session).id) == 0


def test_create_response_does_not_expose_provider_keys(authenticated_client):
    response = authenticated_client.post("/debates", json=PAYLOAD)
    assert response.status_code == 200
    assert "provider_keys_present" not in response.json()["diagnostics"]


def test_database_error_during_create_refunds_the_run_slot(authenticated_client, db_session):
    """A failed commit leaves the session needing a rollback.

    The old refund ran inside that failed transaction, so its commit raised and
    the already-committed hourly run slot was never returned.
    """
    user = _user(db_session)
    key = f"orphan-{uuid4().hex}"
    # A ledger row for this key whose debate no longer exists: replay finds
    # nothing, and the create's own ledger insert then violates the unique key.
    db_session.add(
        UsageLedgerEntry(
            user_id=user.id,
            kind="debate_create_request",
            status="settled",
            idempotency_key=f"debate_create:{user.id}:{key}",
            amount=0,
            debate_id="missing-debate",
        )
    )
    db_session.commit()

    from fastapi.testclient import TestClient
    from main import app

    client = TestClient(app, raise_server_exceptions=False)
    client.cookies = authenticated_client.cookies
    response = client.post("/debates", json=PAYLOAD, headers={"X-Idempotency-Key": key})

    assert response.status_code >= 500
    assert _hour_runs_used(db_session, user.id) == 0
    db_session.expire_all()
    assert db_session.exec(select(Debate).where(Debate.user_id == user.id)).all() == []
