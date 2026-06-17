from uuid import uuid4
from models import Debate, User, DebateTurn
from sqlmodel import Session, select
import pytest
from orchestration.analysis import extract_debate_turn_analysis

def test_moderate_debate_endpoint(authenticated_client, db_session: Session):
    user = db_session.exec(select(User).where(User.email == 'normal@example.com')).first()
    debate = Debate(id=str(uuid4()), prompt='Test prompt for moderate', user_id=user.id, status='queued')
    db_session.add(debate)
    db_session.commit()

    payload = {
        "round_index": 1,
        "moderation_steering": "Focus purely on cost efficiency"
    }
    response = authenticated_client.post(f'/debates/{debate.id}/moderate', json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["round_index"] == 1
    assert data["moderation_steering"] == "Focus purely on cost efficiency"

    # Verify database state
    db_session.expire_all()
    stmt = select(DebateTurn).where(
        DebateTurn.debate_id == debate.id,
        DebateTurn.round_index == 1,
        DebateTurn.agent_id == "moderator"
    )
    turn = db_session.exec(stmt).first()
    assert turn is not None
    assert turn.moderation_steering == "Focus purely on cost efficiency"


def test_get_argument_tree_endpoint(authenticated_client, db_session: Session):
    user = db_session.exec(select(User).where(User.email == 'normal@example.com')).first()
    debate = Debate(id=str(uuid4()), prompt='Test prompt for tree', user_id=user.id, status='queued')
    db_session.add(debate)
    db_session.commit()

    turn1 = DebateTurn(
        debate_id=debate.id,
        round_index=1,
        agent_id="ModelA",
        claims_nodes=[
            {"id": "c1", "type": "pro", "claim": "Cost is low", "rebuts_target": None}
        ],
        position_drift={"stubbornness": 0.2, "cooperativeness": 0.8}
    )
    turn2 = DebateTurn(
        debate_id=debate.id,
        round_index=2,
        agent_id="ModelB",
        claims_nodes=[
            {"id": "c2", "type": "rebuttal", "claim": "Cost is high actually", "rebuts_target": "c1"}
        ],
        position_drift={"stubbornness": 0.5, "cooperativeness": 0.5}
    )
    db_session.add(turn1)
    db_session.add(turn2)
    db_session.commit()

    response = authenticated_client.get(f'/debates/{debate.id}/argument-tree')
    assert response.status_code == 200
    data = response.json()
    assert "nodes" in data
    nodes = data["nodes"]
    assert len(nodes) == 2
    
    # Check claim mapping
    c1_node = [n for n in nodes if n["raw_id"] == "c1"][0]
    c2_node = [n for n in nodes if n["raw_id"] == "c2"][0]
    
    assert c1_node["id"] == "ModelA_c1"
    assert c1_node["agent_id"] == "ModelA"
    assert c1_node["type"] == "pro"
    assert c1_node["position_drift"]["stubbornness"] == 0.2
    
    assert c2_node["id"] == "ModelB_c2"
    assert c2_node["rebuts_target"] == "ModelA_c1"


@pytest.mark.anyio
async def test_extract_debate_turn_analysis_helper(authenticated_client, db_session: Session):
    user = db_session.exec(select(User).where(User.email == 'normal@example.com')).first()
    debate = Debate(id=str(uuid4()), prompt='Test prompt for analysis helper', user_id=user.id, status='queued')
    db_session.add(debate)
    db_session.commit()

    messages = [
        {"persona": "AgentX", "text": "This is a direct response that says cost efficiency is critical."}
    ]

    # Run the extraction (this should not fail and mock_llm will handle model calls if needed)
    await extract_debate_turn_analysis(debate.id, 1, messages)

    db_session.expire_all()
    stmt = select(DebateTurn).where(
        DebateTurn.debate_id == debate.id,
        DebateTurn.round_index == 1,
        DebateTurn.agent_id == "AgentX"
    )
    turn = db_session.exec(stmt).first()
    assert turn is not None
    # Because USE_MOCK/pytest configuration might return mock or fallback values:
    assert turn.claims_nodes is not None
    assert turn.position_drift is not None
