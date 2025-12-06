import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from worker.debate_tasks import _execute_debate_run, run_debate_task
from models import Debate

@pytest.mark.asyncio
async def test_execute_debate_run_success():
    debate_id = "test-debate-id"
    
    with patch("worker.debate_tasks.session_scope") as mock_scope, \
         patch("worker.debate_tasks.get_sse_backend") as mock_get_backend, \
         patch("worker.debate_tasks.run_debate", new_callable=AsyncMock) as mock_run_debate:
        
        mock_session = MagicMock()
        mock_scope.return_value.__enter__.return_value = mock_session
        
        mock_debate = MagicMock(spec=Debate)
        mock_debate.prompt = "Test prompt"
        mock_debate.config = {}
        mock_debate.model_id = "gpt-4"
        mock_session.get.return_value = mock_debate
        
        mock_backend = AsyncMock()
        mock_get_backend.return_value = mock_backend
        
        await _execute_debate_run(debate_id)
        
        mock_session.get.assert_called_with(Debate, debate_id)
        mock_backend.create_channel.assert_called()
        mock_run_debate.assert_called_with(debate_id, "Test prompt", f"debate:{debate_id}", {}, "gpt-4", trace_id=None)

@pytest.mark.asyncio
async def test_execute_debate_run_not_found():
    debate_id = "test-debate-id"
    
    with patch("worker.debate_tasks.session_scope") as mock_scope, \
         patch("worker.debate_tasks.module_logger") as mock_logger:
        
        mock_session = MagicMock()
        mock_scope.return_value.__enter__.return_value = mock_session
        mock_session.get.return_value = None
        
        await _execute_debate_run(debate_id)
        
        mock_logger.warning.assert_called()

def test_run_debate_task():
    debate_id = "test-debate-id"
    
    # Mock the task instance (self)
    mock_self = MagicMock()
    
    with patch("worker.debate_tasks.asyncio.run") as mock_run:
        # Call the function directly, bypassing Celery decorator wrapper if possible, 
        # but since it's decorated, we might need to invoke it differently or mock the decorator.
        # Actually, Celery tasks are callable.
        run_debate_task(debate_id)
        mock_run.assert_called()
