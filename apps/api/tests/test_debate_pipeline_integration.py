import json
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from orchestration.interfaces import DebateContext
from orchestration.pipeline import StandardDebatePipeline
from orchestration.engine import DebateRunner
from orchestration.state import DebateStateManager
from models import Debate

@pytest.fixture
def mock_llm_responses():
    with open("apps/api/tests/fixtures/debate_simulation.json") as f:
        return json.load(f)

@pytest.mark.anyio
async def test_standard_debate_pipeline_integration(db_session, mock_llm_responses):
    # Setup
    debate_id = "test-debate-id"
    user_id = "test-user-id"
    prompt = "Should we adopt AI?"
    
    # Create Debate record
    debate = Debate(id=debate_id, user_id=user_id, prompt=prompt, status="queued")
    db_session.add(debate)
    db_session.commit()
    
    # Mock LLM calls
    with patch("orchestration.stages.produce_candidate") as mock_produce, \
         patch("orchestration.stages.criticize_and_revise") as mock_critique, \
         patch("orchestration.stages.judge_scores") as mock_judge, \
         patch("orchestration.stages.synthesize") as mock_synthesize, \
         patch("orchestration.engine.get_sse_backend") as mock_get_backend, \
         patch("orchestration.stages.get_sse_backend") as mock_get_backend_stages:
        
        # Configure mocks
        mock_backend = AsyncMock()
        mock_get_backend.return_value = mock_backend
        mock_get_backend_stages.return_value = mock_backend
        
        # Draft
        mock_produce.side_effect = [
            (mock_llm_responses["draft"][0], MagicMock(total_tokens=100)),
            (mock_llm_responses["draft"][1], MagicMock(total_tokens=100))
        ]
        
        # Critique
        mock_critique.return_value = (mock_llm_responses["critique"], MagicMock(total_tokens=300))
        
        # Judge
        mock_judge.return_value = (
            mock_llm_responses["judge"]["scores"],
            mock_llm_responses["judge"]["details"],
            MagicMock(total_tokens=200)
        )
        
        # Synthesis
        mock_synthesize.return_value = (
            mock_llm_responses["synthesis"]["text"],
            MagicMock(total_tokens=300)
        )
        
        # Context
        config = {
            "agents": [MagicMock(name="Optimist"), MagicMock(name="Pessimist")],
            "judges": [MagicMock(name="Judge1")]
        }
        context = DebateContext(
            debate_id=debate_id,
            prompt=prompt,
            config=config,
            channel_id="test-channel",
            model_id="gpt-4"
        )
        
        # Execution
        state_manager = DebateStateManager(debate_id, user_id)
        pipeline = StandardDebatePipeline(state_manager)
        runner = DebateRunner(pipeline, state_manager)
        
        final_state = await runner.run(context)
        
        # Verification
        assert final_state.status == "completed"
        assert len(final_state.candidates) == 2
        assert len(final_state.revised_candidates) == 2
        assert len(final_state.scores) == 2
        assert final_state.final_content == mock_llm_responses["synthesis"]["text"]
        
        # Verify DB updates
        db_session.refresh(debate)
        assert debate.status == "completed"
        assert debate.final_content == mock_llm_responses["synthesis"]["text"]
        
        # Verify SSE events
        assert mock_backend.publish.call_count >= 4 # At least one per stage + final
