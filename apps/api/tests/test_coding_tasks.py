import pytest
import asyncio
from unittest.mock import patch, AsyncMock

from models import CodingRun, CodingTurn, CodingLaneResult
from worker.coding_tasks import _async_execute_turn, compute_similarity, LANE_MODELS
from database import engine
from sqlmodel import Session

# Setup mock for gateway
@pytest.fixture
def mock_gateway():
    with patch("apps.api.worker.coding_tasks.call_model_via_gateway", new_callable=AsyncMock) as m:
        # Returns a tuple of (content, usage_mock)
        class MockUsage:
            prompt_tokens = 10
            completion_tokens = 20
            total_tokens = 30
        m.return_value = ("Success patch", MockUsage())
        yield m

def test_compute_similarity():
    # Exactly same
    assert compute_similarity("hello world", "hello world") == 1.0
    # Completely different
    assert compute_similarity("hello world", "foo bar") == 0.0
    # Partial
    assert compute_similarity("hello world foo", "hello foo baz") > 0.4

@pytest.mark.asyncio
async def test_execute_turn_early_exit(db_session, mock_gateway):
    """Test Tier 1 execution exits early when fast and thinking converge."""
    
    # Setup test data (long prompt to trigger Tier 1)
    run = CodingRun(user_id="u1", tier=1, file_paths=["main.py"])
    db_session.add(run)
    db_session.commit()
    
    long_prompt = "Fix bug " * 50
    turn = CodingTurn(coding_run_id=run.id, prompt=long_prompt)
    db_session.add(turn)
    db_session.commit()
    
    # Gateway always returns "Success patch"
    await _async_execute_turn(run.id, turn.id)
    
    # Fast and Thinking should have been executed
    db_session.refresh(run)
    db_session.refresh(turn)
    
    # Check results
    results = db_session.query(CodingLaneResult).filter_by(coding_turn_id=turn.id).all()
    assert len(results) == 2
    lanes = {r.lane_name for r in results}
    assert lanes == {"fast", "thinking"}
    
    # Convergence early exit means turn is completed
    assert turn.status == "completed"
    
@pytest.mark.asyncio
async def test_execute_turn_tier_2_judge(db_session, mock_gateway):
    """Test Tier 2 execution falls back to judge when divergent."""
    
    run = CodingRun(user_id="u1", tier=2, file_paths=["main.py"])
    db_session.add(run)
    db_session.commit()
    
    turn = CodingTurn(coding_run_id=run.id, prompt="Modify auth logic")
    db_session.add(turn)
    db_session.commit()
    
    # Make gateway return different content based on model
    async def mock_call(*args, **kwargs):
        model_id = kwargs.get("model_id")
        class MockUsage:
            prompt_tokens = 10; completion_tokens = 20; total_tokens = 30
        
        # fast, thinking, verifier divergent
        content = f"Patch from {model_id}"
        return (content, MockUsage())
        
    mock_gateway.side_effect = mock_call
    
    await _async_execute_turn(run.id, turn.id)
    
    results = db_session.query(CodingLaneResult).filter_by(coding_turn_id=turn.id).all()
    # fast, thinking, verifier, AND judge
    assert len(results) == 4
    lanes = {r.lane_name for r in results}
    assert "judge" in lanes
    
    # Make sure Judge explicitly used the JUDGE_LANE_MODEL from LANE_MODELS
    judge_res = next(r for r in results if r.lane_name == "judge")
    assert judge_res.model_key == LANE_MODELS["judge"]
