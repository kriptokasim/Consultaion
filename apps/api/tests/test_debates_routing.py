
from unittest.mock import MagicMock, patch

import pytest
from models import Debate
from parliament.router_v2 import CandidateDecision
from sqlmodel import Session


@pytest.fixture
def mock_choose_model():
    with patch("routes.debates.choose_model") as mock:
        yield mock

def test_create_debate_uses_routing(authenticated_client, db_session: Session, mock_choose_model):
    # Setup mock return
    mock_choose_model.return_value = ("routed-model-id", [
        CandidateDecision(
            model="routed-model-id",
            total_score=0.9,
            cost_score=0.1,
            latency_score=0.1,
            quality_score=0.7,
            safety_score=0.0,
            is_healthy=True,
            details={"reason": "test"}
        )
    ])
    
    payload = {
        "prompt": "Test routing prompt",
        "routing_policy": "router-deep"
    }
    
    # Patchset 49.2: Validation requires checking model tier, so we must mock enabled models
    with patch("routes.debates.list_enabled_models") as mock_list:
        mock_model = MagicMock()
        mock_model.id = "routed-model-id"
        mock_model.tier = "standard"
        mock_list.return_value = [mock_model]
        
        response = authenticated_client.post("/debates", json=payload)
    assert response.status_code == 200
    data = response.json()
    debate_id = data["id"]
    
    # Verify mock call
    assert mock_choose_model.called
    ctx = mock_choose_model.call_args[0][0]
    assert ctx.routing_policy == "router-deep"
    assert ctx.requested_model is None
    
    # Verify DB
    debate = db_session.get(Debate, debate_id)
    assert debate.model_id == "routed-model-id"
    assert debate.routed_model == "routed-model-id"
    assert debate.routing_policy == "router-deep"
    assert debate.routing_meta["candidates"][0]["model"] == "routed-model-id"

def test_create_debate_explicit_model_routing(authenticated_client, db_session: Session, mock_choose_model):
    # Setup mock return
    mock_choose_model.return_value = ("gpt-4o", [
        CandidateDecision(
            model="gpt-4o",
            total_score=1.0,
            cost_score=0.0,
            latency_score=0.0,
            quality_score=0.0,
            safety_score=0.0,
            is_healthy=True,
            details={"reason": "explicit_override"}
        )
    ])
    
    payload = {
        "prompt": "Test explicit model",
        "model_id": "gpt-4o"
    }
    
    # We need to ensure gpt-4o is enabled in registry for validation to pass
    # The validation happens BEFORE choose_model in debates.py
    # So we might need to mock list_enabled_models too if gpt-4o is not in default registry
    # But gpt-4o is likely in default registry.
    
    with patch("routes.debates.list_enabled_models") as mock_list:
        mock_model = MagicMock()
        mock_model.id = "gpt-4o"
        mock_model.tier = "standard"  # Patchset 49.2: Required for validation
        mock_list.return_value = [mock_model]
        
        response = authenticated_client.post("/debates", json=payload)
        assert response.status_code == 200
        
    # Verify mock call
    assert mock_choose_model.called
    ctx = mock_choose_model.call_args[0][0]
    assert ctx.requested_model == "gpt-4o"
    
    debate_id = response.json()["id"]
    debate = db_session.get(Debate, debate_id)
    assert debate.model_id == "gpt-4o"
    assert debate.routed_model == "gpt-4o"
