import pytest
from config import AppSettings, settings
from sse_backend import create_sse_backend, MemoryChannelBackend, RedisChannelBackend
from unittest.mock import patch, MagicMock

class TestSSEConfig:
    @patch("sse_backend.settings")
    def test_create_backend_memory_default(self, mock_settings):
        """Should default to MemoryChannelBackend."""
        mock_settings.SSE_BACKEND = "memory"
        mock_settings.IS_LOCAL_ENV = True
        
        backend = create_sse_backend()
        assert isinstance(backend, MemoryChannelBackend)

    @patch("sse_backend.settings")
    def test_create_backend_redis_valid(self, mock_settings):
        """Should return RedisChannelBackend if valid URL."""
        mock_settings.SSE_BACKEND = "redis"
        mock_settings.SSE_REDIS_URL = "redis://localhost:6379"
        mock_settings.REDIS_URL = None
        mock_settings.SSE_CHANNEL_TTL_SECONDS = 900
        
        # We must mock redis.from_url to verify it's instantiated without error
        with patch("sse_backend.redis.from_url") as mock_from_url:
            backend = create_sse_backend()
            assert isinstance(backend, RedisChannelBackend)
            mock_from_url.assert_called()

    @patch("sse_backend.settings")
    def test_create_backend_redis_fail_fast_prod(self, mock_settings):
        """Should raise RuntimeError in production if URL invalid."""
        mock_settings.SSE_BACKEND = "redis"
        mock_settings.SSE_REDIS_URL = None
        mock_settings.REDIS_URL = None
        mock_settings.IS_LOCAL_ENV = False  # Production
        
        with pytest.raises(RuntimeError, match="SSE_BACKEND=redis but URL is invalid or missing"):
            create_sse_backend()

    @patch("sse_backend.logger")
    @patch("sse_backend.settings")
    def test_create_backend_redis_fallback_local(self, mock_settings, mock_logger):
        """Should warn and fallback to Memory in local env."""
        mock_settings.SSE_BACKEND = "redis"
        mock_settings.SSE_REDIS_URL = ""
        mock_settings.REDIS_URL = None
        mock_settings.IS_LOCAL_ENV = True
        mock_settings.SSE_CHANNEL_TTL_SECONDS = 900
        
        backend = create_sse_backend()
        assert isinstance(backend, MemoryChannelBackend)
        mock_logger.warning.assert_called_with("SSE_BACKEND=redis but URL is invalid or missing. Falling back to memory.")
