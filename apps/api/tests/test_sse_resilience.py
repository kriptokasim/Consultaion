from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# Mock redis module just enough to expose ConnectionError/TimeoutError classes for catching
import redis.asyncio as real_redis
from sse_backend import RedisChannelBackend


def _install_redis_lock_double(redis_mock):
    """Give a mocked Redis client a working ``lock()``.

    ``redis.asyncio.Redis.lock()`` is a *synchronous* method returning a Lock
    object that is used as an async context manager. On a bare ``AsyncMock``
    the call returns a coroutine instead, and ``async with`` raises
    ``TypeError: 'coroutine' object does not support the asynchronous context
    manager protocol`` (see ``RedisChannelBackend._publish_single``).
    """
    lock = MagicMock()
    lock.__aenter__ = AsyncMock(return_value=lock)
    lock.__aexit__ = AsyncMock(return_value=False)
    redis_mock.lock = MagicMock(return_value=lock)
    return lock


@pytest.mark.anyio
class TestSSEResilience:
    @patch("redis_pool.get_async_redis_client", return_value=None)
    @patch("sse_backend.redis.from_url")
    async def test_publish_retry_success(self, mock_from_url, mock_get_pool):
        """Should retry on connection error and eventually succeed."""
        mock_client = AsyncMock()
        _install_redis_lock_double(mock_client)
        mock_client.incr.return_value = 1
        mock_client.expire.return_value = True
        mock_from_url.return_value = mock_client

        # Setup: Fail twice, succeed third time
        mock_client.publish.side_effect = [
            real_redis.ConnectionError("fail 1"),
            real_redis.TimeoutError("fail 2"),
            None,
        ]

        backend = RedisChannelBackend(url="redis://test")
        await backend.publish("test-ch", {"msg": "hello"})

        assert mock_client.publish.call_count == 3

    @patch("redis_pool.get_async_redis_client", return_value=None)
    @patch("sse_backend.redis.from_url")
    @patch("sse_backend.logger")
    async def test_publish_retry_exhausted(self, mock_logger, mock_from_url, mock_get_pool):
        """Should log error after 3 failed attempts."""
        mock_client = AsyncMock()
        _install_redis_lock_double(mock_client)
        mock_client.incr.return_value = 1
        mock_client.expire.return_value = True
        mock_from_url.return_value = mock_client

        # Setup: Fail 3 times
        mock_client.publish.side_effect = [
            real_redis.ConnectionError("fail 1"),
            real_redis.ConnectionError("fail 2"),
            real_redis.ConnectionError("fail 3"),
        ]

        backend = RedisChannelBackend(url="redis://test")
        await backend.publish("test-ch", {"msg": "hello"})

        assert mock_client.publish.call_count == 3
        mock_logger.error.assert_called()
        assert "after 3 attempts" in mock_logger.error.call_args[0][0]

    @patch("redis_pool.get_async_redis_client", return_value=None)
    @patch("sse_backend.redis.from_url")
    async def test_publish_generic_error(self, mock_from_url, mock_get_pool):
        """Generic errors should not retry."""
        mock_client = AsyncMock()
        _install_redis_lock_double(mock_client)
        mock_client.incr.return_value = 1
        mock_client.expire.return_value = True
        mock_from_url.return_value = mock_client

        mock_client.publish.side_effect = ValueError("Fatal error")

        backend = RedisChannelBackend(url="redis://test")
        await backend.publish("test-ch", {"msg": "hello"})

        # Should only call once
        assert mock_client.publish.call_count == 1
