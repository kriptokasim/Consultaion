import asyncio
from unittest.mock import patch, MagicMock

import sys
sys.path.append('.')

async def test():
    # Setup minimal mock config
    import config
    config.settings.USE_MOCK = True
    
    # Mock database session
    from database_async import async_session_scope
    
    class MockDebate:
        def __init__(self):
            self.prompt = "What is Rust?"
            self.config = {}
            self.user_id = "test-user"
            
    # Mock async session
    class MockSession:
        async def __aenter__(self):
            return self
        async def __aexit__(self, exc_type, exc_val, exc_tb):
            pass
        async def get(self, *args, **kwargs):
            return MockDebate()
        def add(self, *args, **kwargs):
            pass
        async def commit(self):
            pass
            
    # Mock sse backend
    from sse_backend import BaseSSEBackend
    class MockSSE(BaseSSEBackend):
        async def publish(self, *args, **kwargs):
            print(f"SSE Publish: {args}")
            
    # Patch dependencies
    with patch('arena.engine.async_session_scope', return_value=MockSession()), \
         patch('arena.engine.get_sse_backend', return_value=MockSSE()), \
         patch('arena.engine.call_llm_for_role', new_callable=MagicMock) as mock_llm:
         
        class MockUsage:
            def __init__(self, t):
                self.prompt_tokens = 10
                self.completion_tokens = t - 10
                self.total_tokens = t
                self.cost_usd = 0.0
                self.provider = "mock"
                self.model = "mock-model"
            def to_dict(self):
                return {"total_tokens": self.total_tokens}

        # Mock LLM returns a tuple (content, usage)
        async def mock_call(*args, **kwargs):
            role = kwargs.get('role', '')
            if 'Synthesizer' in role:
                return f"Synthesized answer.", MockUsage(50)
            return f"Mock answer from {role}.", MockUsage(100)
            
        mock_llm.side_effect = mock_call
        
        from arena.engine import run_arena
        result = await run_arena("test-debate-id")
        
        print(f"\nFinal Status: {result.status}")
        print(f"Final Answer: {result.final_answer}")
        print(f"Models Count: {len(result.model_responses)}")
        print(f"Successful: {result.final_meta['successful_count']}")

if __name__ == "__main__":
    asyncio.run(test())
