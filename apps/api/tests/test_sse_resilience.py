import asyncio
import json
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from sse_backend import RedisChannelBackend

# Mock redis module just enough to expose ConnectionError/TimeoutError classes for catching
import redis.asyncio as real_redis

@pytest.mark.asyncio
class TestSSEResilience:
    @patch("sse_backend.redis.from_url")
    async def test_publish_retry_success(self, mock_from_url):
        """Should retry on connection error and eventually succeed."""
        mock_client = AsyncMock()
        mock_from_url.return_value = mock_client
        
        # Setup: Fail twice, succeed third time
        mock_client.publish.side_effect = [
            real_redis.ConnectionError("fail 1"),
            real_redis.TimeoutError("fail 2"),
            None
        ]
        
        backend = RedisChannelBackend(url="redis://test")
        await backend.publish("test-ch", {"msg": "hello"})
        
        assert mock_client.publish.call_count == 3
        
    @patch("sse_backend.redis.from_url")
    @patch("sse_backend.logger")
    async def test_publish_retry_exhausted(self, mock_logger, mock_from_url):
        """Should log error after 3 failed attempts."""
        mock_client = AsyncMock()
        mock_from_url.return_value = mock_client
        
        # Setup: Fail 3 times
        mock_client.publish.side_effect = [
            real_redis.ConnectionError("fail 1"),
            real_redis.ConnectionError("fail 2"),
            real_redis.ConnectionError("fail 3")
        ]
        
        backend = RedisChannelBackend(url="redis://test")
        await backend.publish("test-ch", {"msg": "hello"})
        
        assert mock_client.publish.call_count == 3
        mock_logger.error.assert_called()
        assert "after 3 attempts" in mock_logger.error.call_args[0][0]

    @patch("sse_backend.redis.from_url")
    async def test_publish_generic_error(self, mock_from_url):
        """Generic errors should not retry."""
        mock_client = AsyncMock()
        mock_from_url.return_value = mock_client
        
        mock_client.publish.side_effect = ValueError("Fatal error")
        
        backend = RedisChannelBackend(url="redis://test")
        await backend.publish("test-ch", {"msg": "hello"})
        
        # Should only call once
        assert mock_client.publish.call_count == 1
