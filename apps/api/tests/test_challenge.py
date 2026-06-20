from uuid import uuid4

from models import ChallengeRound, ChallengeSession, Debate, User
from sqlmodel import Session, select


def test_start_challenge_session_endpoint(authenticated_client, db_session: Session):
    user = db_session.exec(select(User).where(User.email == "normal@example.com")).first()
    
    # Create completed debate
    debate = Debate(
        id=str(uuid4()),
        prompt="Test debate prompt",
        status="completed",
        final_content="Initial synthesis of the debate.",
        user_id=user.id
    )
    db_session.add(debate)
    db_session.commit()

    payload = {"debate_id": debate.id}
    response = authenticated_client.post("/challenge", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert "id" in data
    assert data["debate_id"] == debate.id

    # Verify session is persisted
    db_session.expire_all()
    sess = db_session.get(ChallengeSession, data["id"])
    assert sess is not None


def test_get_challenge_session_endpoint(authenticated_client, db_session: Session):
    user = db_session.exec(select(User).where(User.email == "normal@example.com")).first()
    
    debate = Debate(
        id=str(uuid4()),
        prompt="Test debate prompt",
        status="completed",
        final_content="Initial synthesis of the debate.",
        user_id=user.id
    )
    db_session.add(debate)
    db_session.commit()

    sess = ChallengeSession(
        id=str(uuid4()),
        user_id=user.id,
        debate_id=debate.id
    )
    db_session.add(sess)
    db_session.commit()

    round_1 = ChallengeRound(
        id=str(uuid4()),
        session_id=sess.id,
        round_index=1,
        user_pushback="The synthesis misses local encryption.",
        action_taken="revise",
        model_response="Good point, adding detail.",
        revised_synthesis="Initial synthesis. Revision: Use TLS."
    )
    db_session.add(round_1)
    db_session.commit()

    response = authenticated_client.get(f"/challenge/{sess.id}")
    assert response.status_code == 200
    data = response.json()
    assert data["id"] == sess.id
    assert data["original_prompt"] == "Test debate prompt"
    assert data["original_synthesis"] == "Initial synthesis of the debate."
    assert len(data["rounds"]) == 1
    assert data["rounds"][0]["pushback_text"] == "The synthesis misses local encryption."
    assert data["rounds"][0]["decision"] == "revise"


def test_submit_challenge_round_endpoint(authenticated_client, db_session: Session):
    user = db_session.exec(select(User).where(User.email == "normal@example.com")).first()
    
    debate = Debate(
        id=str(uuid4()),
        prompt="Test debate prompt",
        status="completed",
        final_content="Initial synthesis.",
        user_id=user.id
    )
    db_session.add(debate)
    db_session.commit()

    sess = ChallengeSession(
        id=str(uuid4()),
        user_id=user.id,
        debate_id=debate.id
    )
    db_session.add(sess)
    db_session.commit()

    # Submit pushback to trigger evaluation
    payload = {"pushback_text": "This synthesis contains a major error in its scaling logic."}
    response = authenticated_client.post(f"/challenge/{sess.id}/round", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert "round_number" in data
    assert data["round_number"] == 1
    assert data["decision"] in ["defend", "concede", "revise"]
    assert "response_reasoning" in data
    assert "revised_synthesis" in data

    # Verify round is persisted
    db_session.expire_all()
    rounds = db_session.exec(select(ChallengeRound).where(ChallengeRound.session_id == sess.id)).all()
    assert len(rounds) == 1
    assert rounds[0].user_pushback == "This synthesis contains a major error in its scaling logic."
