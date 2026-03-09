"""
Patchset 112: Tests for centralized Redis connection pooling.
"""
import pytest
from unittest.mock import patch, MagicMock


class TestRedisPool:
    """Tests for redis_pool module."""

    def test_get_sync_redis_client_returns_none_without_url(self):
        """Without REDIS_URL configured, returns None."""
        with patch("redis_pool.settings") as mock_settings:
            mock_settings.REDIS_URL = None

            # Reset global state
            import redis_pool
            redis_pool.reset_pools_for_tests()

            client = redis_pool.get_sync_redis_client()
            assert client is None

    def test_get_sync_redis_client_creates_pooled_connection(self):
        """With REDIS_URL, creates a pooled Redis connection."""
        with patch("redis_pool.settings") as mock_settings:
            mock_settings.REDIS_URL = "redis://localhost:6379"

            with patch("redis_pool.redis") as mock_redis:
                mock_pool = MagicMock()
                mock_client = MagicMock()
                mock_redis.ConnectionPool.from_url.return_value = mock_pool
                mock_redis.Redis.return_value = mock_client
                mock_client.ping.return_value = True

                import redis_pool
                redis_pool.reset_pools_for_tests()

                client = redis_pool.get_sync_redis_client()

                assert client == mock_client
                mock_redis.ConnectionPool.from_url.assert_called_once()
                mock_client.ping.assert_called_once()

    def test_get_sync_redis_client_returns_cached_client(self):
        """Subsequent calls return the cached client."""
        with patch("redis_pool.settings") as mock_settings:
            mock_settings.REDIS_URL = "redis://localhost:6379"

            with patch("redis_pool.redis") as mock_redis:
                mock_pool = MagicMock()
                mock_client = MagicMock()
                mock_redis.ConnectionPool.from_url.return_value = mock_pool
                mock_redis.Redis.return_value = mock_client
                mock_client.ping.return_value = True

                import redis_pool
                redis_pool.reset_pools_for_tests()

                client1 = redis_pool.get_sync_redis_client()
                client2 = redis_pool.get_sync_redis_client()

                assert client1 is client2
                # Pool created only once
                assert mock_redis.ConnectionPool.from_url.call_count == 1

    def test_get_sync_redis_client_handles_connection_failure(self):
        """Gracefully handles Redis connection failures."""
        with patch("redis_pool.settings") as mock_settings:
            mock_settings.REDIS_URL = "redis://localhost:6379"

            with patch("redis_pool.redis") as mock_redis:
                mock_redis.ConnectionPool.from_url.side_effect = Exception("Connection refused")

                import redis_pool
                redis_pool.reset_pools_for_tests()

                client = redis_pool.get_sync_redis_client()
                assert client is None

    def test_get_async_redis_client_returns_none_without_url(self):
        """Without SSE_REDIS_URL or REDIS_URL, returns None."""
        with patch("redis_pool.settings") as mock_settings:
            mock_settings.SSE_REDIS_URL = None
            mock_settings.REDIS_URL = None

            import redis_pool
            redis_pool.reset_pools_for_tests()

            client = redis_pool.get_async_redis_client()
            assert client is None

    def test_reset_pools_clears_state(self):
        """reset_pools_for_tests clears all cached clients."""
        import redis_pool

        # Set some state
        redis_pool._sync_client = MagicMock()
        redis_pool._async_client = MagicMock()
        redis_pool._sync_pool = MagicMock()
        redis_pool._async_pool = MagicMock()

        redis_pool.reset_pools_for_tests()

        assert redis_pool._sync_client is None
        assert redis_pool._async_client is None
        assert redis_pool._sync_pool is None
        assert redis_pool._async_pool is None


class TestRateLimiterWithPool:
    """Tests that rate limiter uses the shared pool."""

    def test_rate_limiter_uses_shared_pool(self):
        """RedisRateLimiterBackend should attempt to use shared pool."""
        with patch("redis_pool.settings") as mock_settings:
            mock_settings.REDIS_URL = "redis://localhost:6379"

            with patch("redis_pool.get_sync_redis_client") as mock_get_client:
                mock_client = MagicMock()
                mock_get_client.return_value = mock_client

                # Import after patching
                from ratelimit import RedisRateLimiterBackend

                backend = RedisRateLimiterBackend("redis://localhost:6379")

                # Should use the pooled client
                mock_get_client.assert_called()
