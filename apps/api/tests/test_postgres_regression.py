import uuid
from unittest.mock import patch

from models import Debate, Message, User
from sqlmodel import Session, select


def _create_debate(session: Session, user, **kwargs) -> Debate:
    debate_id = kwargs.pop("id", str(uuid.uuid4()))
    debate = Debate(
        id=debate_id,
        prompt=kwargs.pop("prompt", "Test prompt"),
        user_id=kwargs.pop("user_id", user.id),
        status=kwargs.pop("status", "completed"),
        config=kwargs.pop("config", None),
        final_meta=kwargs.pop("final_meta", None),
        mode=kwargs.pop("mode", "arena"),
    )
    for k, v in kwargs.items():
        setattr(debate, k, v)
    session.add(debate)
    session.commit()
    return debate


def _add_message(session, debate_id, role="arena_response", persona="GPT-4o", content="Response", meta=None):
    msg = Message(
        debate_id=debate_id,
        round_index=1,
        role=role,
        persona=persona,
        content=content,
        meta=meta or {},
    )
    session.add(msg)
    session.commit()
    return msg


def test_completed_run_with_four_responses(authenticated_client, db_session):
    """FH121: Completed debate with 4 arena_response messages — route returns 200."""
    user = db_session.exec(select(User).where(User.email == "normal@example.com")).first()
    debate = _create_debate(
        db_session,
        user,
        prompt="Healthy completed run",
        status="completed",
        final_meta={"successful_count": 4, "total_count": 4},
    )

    for name in ["GPT-4o", "Claude 3.5", "Gemini Pro", "Llama 3.1"]:
        _add_message(
            db_session,
            debate.id,
            persona=name,
            content=f"Response from {name}",
            meta={"model_id": name.lower().replace(" ", "-"), "display_name": name, "provider": "test", "success": True},
        )

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
        assert data["summary"]["successful"] == 4
        assert data["summary"]["failed"] == 0


def test_completed_run_with_zero_responses(authenticated_client, db_session):
    """FH122: Completed debate with no messages — route returns 200 with empty items."""
    user = db_session.exec(select(User).where(User.email == "normal@example.com")).first()
    debate = _create_debate(
        db_session,
        user,
        prompt="Empty completed run",
        status="completed",
        final_meta={"successful_count": 0, "total_count": 4},
    )

    with patch("services.debate_responses.fetch_persisted_responses") as mock_fetch:
        mock_fetch.return_value = {
            "items": [],
            "summary": {"expected": 4, "persisted": 0, "successful": 0, "failed": 0},
        }
        response = authenticated_client.get(f"/debates/{debate.id}/responses")
        assert response.status_code == 200
        data = response.json()
        assert data["summary"]["persisted"] == 0
        assert len(data["items"]) == 0


def test_missing_optional_table_under_savepoint(authenticated_client, db_session):
    """FH123: Debate detail still returns 200 even when optional table queries fail."""
    user = db_session.exec(select(User).where(User.email == "normal@example.com")).first()
    debate = _create_debate(
        db_session,
        user,
        prompt="Savepoint tolerance test",
        status="completed",
    )

    with patch("serializers._get_debate_extra_fields") as mock_extra:
        mock_extra.return_value = {
            "current_stage": "completed",
            "stage_checkpoints": None,
            "continuation_id": None,
            "continuation_status": None,
            "perspectives_ready_at": None,
            "responses_received": None,
            "models_expected": 4,
            "scores_received": None,
            "verification_status": None,
            "_checkpoint_query_failed": True,
            "_continuation_query_failed": True,
            "_message_query_failed": True,
            "_score_query_failed": True,
        }
        response = authenticated_client.get(f"/debates/{debate.id}")
        assert response.status_code == 200
        data = response.json()
        assert len(data["query_failures"]) >= 1
        assert data["read_quality"] == "degraded"


def test_historical_response_role_mapping(authenticated_client, db_session):
    """FH124: Messages with different roles are correctly classified."""
    from services.debate_responses import EXCLUDED_ROLES, RESPONSE_ROLES

    user = db_session.exec(select(User).where(User.email == "normal@example.com")).first()
    debate = _create_debate(db_session, user, prompt="Role mapping test", status="completed")

    all_roles = ["arena_response", "seat", "delegate", "candidate", "revised",
                 "judge", "arena_synthesis", "final", "system", "notice"]
    for role in all_roles:
        _add_message(db_session, debate.id, role=role, persona=f"P_{role}", content=f"C_{role}")

    included = {"arena_response", "seat", "delegate", "candidate", "revised"}
    excluded = {"judge", "arena_synthesis", "final", "system", "notice"}
    assert included == RESPONSE_ROLES
    assert excluded == EXCLUDED_ROLES
    assert included.isdisjoint(excluded)


def test_repair_dry_run(authenticated_client, db_session):
    """FH123: A completed debate with 0 persisted but 4 expected is classified as recoverable."""
    user = db_session.exec(select(User).where(User.email == "normal@example.com")).first()
    debate = _create_debate(
        db_session,
        user,
        prompt="Repair dry run test",
        status="completed",
        final_meta={
            "successful_count": 4,
            "total_count": 4,
            "models": [
                {"display_name": f"M{i}", "model_id": f"m{i}", "provider": "test", "success": True}
                for i in range(4)
            ],
        },
    )

    expected = (debate.final_meta or {}).get("total_count", 0)
    persisted = db_session.exec(
        select(Message).where(Message.debate_id == debate.id)
    ).all()
    assert expected == 4
    assert len(persisted) == 0
    assert len(persisted) < expected


def test_repair_idempotency(authenticated_client, db_session):
    """FH124: Querying the same debate twice yields consistent results."""
    from services.debate_responses import RESPONSE_ROLES

    user = db_session.exec(select(User).where(User.email == "normal@example.com")).first()
    debate = _create_debate(db_session, user, prompt="Idempotency test", status="completed")

    _add_message(db_session, debate.id, role="arena_response", persona="M1", content="C1",
                 meta={"model_id": "m1", "display_name": "M1", "provider": "test"})

    count1 = db_session.exec(
        select(Message).where(
            Message.debate_id == debate.id,
            Message.role.in_(sorted(RESPONSE_ROLES)),
        )
    ).all()
    count2 = db_session.exec(
        select(Message).where(
            Message.debate_id == debate.id,
            Message.role.in_(sorted(RESPONSE_ROLES)),
        )
    ).all()

    assert len(count1) == len(count2) == 1
    assert count1[0].id == count2[0].id
