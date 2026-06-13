import json
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from models import Debate, Message
from orchestration.engine import DebateRunner
from orchestration.interfaces import DebateContext
from orchestration.pipeline import StandardDebatePipeline
from orchestration.state import DebateStateManager


@pytest.fixture
def mock_llm_responses():
    fixture_path = Path(__file__).parent / "fixtures" / "debate_simulation.json"
    with open(fixture_path) as f:
        return json.load(f)


@pytest.mark.anyio
async def test_staged_debate_pipeline_pause_and_resume(db_session, mock_llm_responses):
    debate_id = "test-staged-debate-id"
    user_id = "test-user-id"
    prompt = "Should we adopt AI?"
    
    # Create Debate record
    debate = Debate(id=debate_id, user_id=user_id, prompt=prompt, status="queued")
    db_session.add(debate)
    db_session.commit()
    
    # Context config
    config = {
        "agents": [MagicMock(name="Optimist"), MagicMock(name="Pessimist")],
        "judges": [MagicMock(name="Judge1")]
    }

    # First Pass: STAGED_DECISION_PIPELINE = True, is_resume = False
    with patch("orchestration.stages.produce_candidate") as mock_produce, \
         patch("orchestration.stages.criticize_and_revise") as mock_critique, \
         patch("orchestration.engine.get_sse_backend") as mock_get_backend, \
         patch("orchestration.stages.get_sse_backend") as mock_get_backend_stages, \
         patch("config.settings.STAGED_DECISION_PIPELINE", True):
        
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
        
        context = DebateContext(
            debate_id=debate_id,
            prompt=prompt,
            config=config,
            channel_id="test-channel",
            model_id="gpt-4",
            is_resume=False
        )
        
        state_manager = DebateStateManager(debate_id, user_id)
        pipeline = StandardDebatePipeline(state_manager)
        runner = DebateRunner(pipeline, state_manager)
        
        paused_state = await runner.run(context)
        
        # Verification
        assert paused_state.status == "perspectives_ready"
        db_session.refresh(debate)
        assert debate.status == "perspectives_ready"
        
        # Verify messages are saved
        from sqlmodel import select
        candidates_db = db_session.exec(
            select(Message).where(Message.debate_id == debate_id).where(Message.role == "candidate")
        ).all()
        assert len(candidates_db) == 2

    # Second Pass: STAGED_DECISION_PIPELINE = True, is_resume = True (continue execution)
    with patch("orchestration.stages.produce_candidate") as mock_produce_resume, \
         patch("orchestration.stages.criticize_and_revise") as mock_critique_resume, \
         patch("orchestration.stages.judge_scores") as mock_judge, \
         patch("orchestration.stages.synthesize") as mock_synthesize, \
         patch("orchestration.stages.generate_decision_report") as mock_generate_report, \
         patch("orchestration.engine.get_sse_backend") as mock_get_backend, \
         patch("orchestration.stages.get_sse_backend") as mock_get_backend_stages, \
         patch("config.settings.STAGED_DECISION_PIPELINE", True):
        
        mock_backend = AsyncMock()
        mock_get_backend.return_value = mock_backend
        mock_get_backend_stages.return_value = mock_backend
        
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
        # Synthesis Decision Report
        mock_report = MagicMock()
        mock_report.executive_summary = mock_llm_responses["synthesis"]["text"]
        mock_report.title = "Decision Report"
        mock_report.model_dump.return_value = {"mock": "report"}
        mock_generate_report.return_value = mock_report
        
        context_resume = DebateContext(
            debate_id=debate_id,
            prompt=prompt,
            config=config,
            channel_id="test-channel",
            model_id="gpt-4",
            is_resume=True
        )
        
        state_manager_resume = DebateStateManager(debate_id, user_id)
        pipeline_resume = StandardDebatePipeline(state_manager_resume)
        runner_resume = DebateRunner(pipeline_resume, state_manager_resume)
        
        final_state = await runner_resume.run(context_resume)
        
        # Verification
        assert final_state.status == "completed"
        # Ensure produce and critique were not called (resumed from saved messages)
        mock_produce_resume.assert_not_called()
        mock_critique_resume.assert_not_called()
        
        # Verify final database state
        db_session.refresh(debate)
        assert debate.status == "completed"
        assert debate.final_content == mock_llm_responses["synthesis"]["text"]
