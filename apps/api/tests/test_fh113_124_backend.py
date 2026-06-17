import uuid
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient
from models import Debate, Message, User
from sqlmodel import Session, select
from auth import COOKIE_NAME, create_access_token, hash_password


def test_core_serializer_survives_checkpoint_failure(authenticated_client, db_session):
    """FH113: GET /debates/{id} returns 200 with query_failures when checkpoint query raises."""
    user = db_session.exec(select(User).where(User.email == "normal@example.com")).first()
    debate = Debate(
        id=str(uuid.uuid4()),
        prompt="Serializer fault tolerance test",
        user_id=user.id,
        status="completed",
    )
    db_session.add(debate)
    db_session.commit()

    with patch("serializers._get_debate_extra_fields") as mock_extra:
        mock_extra.return_value = {
            "current_stage": "completed",
            "stage_checkpoints": None,
            "continuation_id": None,
            "continuation_status": None,
            "perspectives_ready_at": None,
            "responses_received": 0,
            "models_expected": 4,
            "scores_received": 0,
            "verification_status": None,
            "_checkpoint_query_failed": True,
        }
        response = authenticated_client.get(f"/debates/{debate.id}")
        assert response.status_code == 200
        data = response.json()
        assert "query_failures" in data
        assert "checkpoints" in data["query_failures"]
        assert data["read_quality"] == "degraded"


def test_core_serializer_survives_continuation_failure(authenticated_client, db_session):
    """FH114: GET /debates/{id} returns 200 with query_failures when continuation query raises."""
    user = db_session.exec(select(User).where(User.email == "normal@example.com")).first()
    debate = Debate(
        id=str(uuid.uuid4()),
        prompt="Continuation failure tolerance test",
        user_id=user.id,
        status="completed",
    )
    db_session.add(debate)
    db_session.commit()

    with patch("serializers._get_debate_extra_fields") as mock_extra:
        mock_extra.return_value = {
            "current_stage": "completed",
            "stage_checkpoints": None,
            "continuation_id": None,
            "continuation_status": None,
            "perspectives_ready_at": None,
            "responses_received": 0,
            "models_expected": 4,
            "scores_received": 0,
            "verification_status": None,
            "_continuation_query_failed": True,
        }
        response = authenticated_client.get(f"/debates/{debate.id}")
        assert response.status_code == 200
        data = response.json()
        assert "query_failures" in data
        assert "continuations" in data["query_failures"]
        assert data["read_quality"] == "degraded"


def test_responses_route_returns_rows(authenticated_client, db_session):
    """FH115: GET /debates/{id}/responses returns persisted arena_response messages."""
    user = db_session.exec(select(User).where(User.email == "normal@example.com")).first()
    debate = Debate(
        id=str(uuid.uuid4()),
        prompt="Responses route test",
        user_id=user.id,
        status="completed",
        final_meta={"successful_count": 4, "total_count": 4},
    )
    db_session.add(debate)
    db_session.commit()

    mock_items = [
        {"id": i, "role": "arena_response", "display_name": n, "success": True, "content": f"Response from {n}"}
        for i, n in enumerate(["GPT-4o", "Claude 3.5", "Gemini Pro", "Llama 3.1"], 1)
    ]
    with patch("services.debate_responses.fetch_persisted_responses") as mock_fetch:
        mock_fetch.return_value = {
            "items": mock_items,
            "summary": {"expected": 4, "persisted": 4, "successful": 4, "failed": 0},
        }
        response = authenticated_client.get(f"/debates/{debate.id}/responses")
        assert response.status_code == 200
        data = response.json()
        assert len(data["items"]) == 4
        assert data["summary"]["persisted"] == 4
        assert data["summary"]["expected"] >= 4


def test_responses_query_failure_returns_non_2xx(authenticated_client, db_session):
    """FH116: GET /debates/{id}/responses returns non-200 when Message query fails."""
    user = db_session.exec(select(User).where(User.email == "normal@example.com")).first()
    debate = Debate(
        id=str(uuid.uuid4()),
        prompt="Responses failure test",
        user_id=user.id,
        status="completed",
    )
    db_session.add(debate)
    db_session.commit()

    with patch("services.debate_responses.fetch_persisted_responses") as mock_fetch:
        from services.debate_responses import ResponsesQueryError
        mock_fetch.side_effect = ResponsesQueryError("database connection lost")
        response = authenticated_client.get(f"/debates/{debate.id}/responses")
        assert response.status_code != 200


def test_private_run_authorization(authenticated_client, db_session):
    """FH117: Private debate returns 401/403 when requested without auth."""
    user = db_session.exec(select(User).where(User.email == "normal@example.com")).first()
    debate = Debate(
        id=str(uuid.uuid4()),
        prompt="Private authorization test",
        user_id=user.id,
        status="completed",
    )
    db_session.add(debate)
    db_session.commit()

    client_no_auth = TestClient(authenticated_client.app)
    response = client_no_auth.get(f"/debates/{debate.id}")
    assert response.status_code in (401, 403, 404)


def test_public_run_authorization(authenticated_client, db_session):
    """FH118: Public debate returns 200 when requested without auth."""
    user = db_session.exec(select(User).where(User.email == "normal@example.com")).first()
    debate = Debate(
        id=str(uuid.uuid4()),
        prompt="Public authorization test",
        user_id=user.id,
        status="completed",
        config={"is_public": True},
    )
    db_session.add(debate)
    db_session.commit()

    client_no_auth = TestClient(authenticated_client.app)
    response = client_no_auth.get(f"/debates/{debate.id}")
    assert response.status_code == 200


def test_runtime_contract_metadata(authenticated_client):
    """FH119: GET /meta/contracts returns git_sha and contracts.persisted_responses."""
    response = authenticated_client.get("/meta/contracts")
    assert response.status_code == 200
    data = response.json()
    assert "git_sha" in data
    assert "contracts" in data
    assert "persisted_responses" in data["contracts"]
    assert isinstance(data["contracts"]["persisted_responses"], int)


def test_build_sha_metadata(authenticated_client):
    """FH120: GET /healthz returns git_sha field."""
    response = authenticated_client.get("/healthz")
    assert response.status_code == 200
    data = response.json()
    assert "git_sha" in data
    assert isinstance(data["git_sha"], str)
    assert data["status"] == "ok"
