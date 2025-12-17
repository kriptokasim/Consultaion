from unittest.mock import patch

import pytest
from sse_backend import MemoryChannelBackend, RedisChannelBackend, create_sse_backend, _is_strict


class TestSSEConfig:
    @patch("sse_backend.settings")
    def test_create_backend_memory_default(self, mock_settings):
        """Should default to MemoryChannelBackend."""
        mock_settings.SSE_BACKEND = "memory"
        mock_settings.IS_LOCAL_ENV = True
        mock_settings.SSE_CHANNEL_TTL_SECONDS = 900
        mock_settings.SSE_MEMORY_MAX_QUEUE_SIZE = 1000
        mock_settings.SSE_MEMORY_IDLE_TIMEOUT_SECONDS = 3600
        
        backend = create_sse_backend()
        assert isinstance(backend, MemoryChannelBackend)

    @patch("sse_backend.settings")
    def test_create_backend_redis_valid(self, mock_settings):
        """Should return RedisChannelBackend if valid URL."""
        mock_settings.SSE_BACKEND = "redis"
        mock_settings.SSE_REDIS_URL = "redis://localhost:6379"
        mock_settings.REDIS_URL = None
        mock_settings.SSE_CHANNEL_TTL_SECONDS = 900
        
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
        mock_settings.SSE_REDIS_STRICT = None  # Auto (strict in prod)
        
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
        mock_settings.SSE_REDIS_STRICT = None  # Auto (lenient in local)
        mock_settings.SSE_CHANNEL_TTL_SECONDS = 900
        mock_settings.SSE_MEMORY_MAX_QUEUE_SIZE = 1000
        mock_settings.SSE_MEMORY_IDLE_TIMEOUT_SECONDS = 3600
        
        backend = create_sse_backend()
        assert isinstance(backend, MemoryChannelBackend)
        mock_logger.warning.assert_called_with("SSE_BACKEND=redis but URL is invalid or missing. Falling back to memory.")


class TestSSEStrictMode:
    """Patchset 75: Tests for SSE_REDIS_STRICT explicit control."""
    
    @patch("sse_backend.settings")
    def test_strict_mode_explicit_true_fails_in_local(self, mock_settings):
        """SSE_REDIS_STRICT=1 should fail even in local env."""
        mock_settings.SSE_BACKEND = "redis"
        mock_settings.SSE_REDIS_URL = None
        mock_settings.REDIS_URL = None
        mock_settings.IS_LOCAL_ENV = True  # Local env
        mock_settings.SSE_REDIS_STRICT = True  # Explicit strict
        
        with pytest.raises(RuntimeError, match="SSE_BACKEND=redis but URL is invalid or missing"):
            create_sse_backend()
    
    @patch("sse_backend.logger")
    @patch("sse_backend.settings")
    def test_strict_mode_explicit_false_allows_fallback_in_prod(self, mock_settings, mock_logger):
        """SSE_REDIS_STRICT=0 should allow fallback even in production."""
        mock_settings.SSE_BACKEND = "redis"
        mock_settings.SSE_REDIS_URL = None
        mock_settings.REDIS_URL = None
        mock_settings.IS_LOCAL_ENV = False  # Production
        mock_settings.SSE_REDIS_STRICT = False  # Explicit lenient
        mock_settings.SSE_CHANNEL_TTL_SECONDS = 900
        mock_settings.SSE_MEMORY_MAX_QUEUE_SIZE = 1000
        mock_settings.SSE_MEMORY_IDLE_TIMEOUT_SECONDS = 3600
        
        backend = create_sse_backend()
        assert isinstance(backend, MemoryChannelBackend)
        mock_logger.warning.assert_called()

    @patch("sse_backend.settings")
    def test_is_strict_auto_prod(self, mock_settings):
        """_is_strict() should return True in production when SSE_REDIS_STRICT is None."""
        mock_settings.SSE_REDIS_STRICT = None
        mock_settings.IS_LOCAL_ENV = False
        assert _is_strict() is True
    
    @patch("sse_backend.settings")
    def test_is_strict_auto_local(self, mock_settings):
        """_is_strict() should return False in local when SSE_REDIS_STRICT is None."""
        mock_settings.SSE_REDIS_STRICT = None
        mock_settings.IS_LOCAL_ENV = True
        assert _is_strict() is False
    
    @patch("sse_backend.settings")
    def test_is_strict_explicit_overrides_env(self, mock_settings):
        """SSE_REDIS_STRICT explicit value should override IS_LOCAL_ENV."""
        mock_settings.SSE_REDIS_STRICT = True
        mock_settings.IS_LOCAL_ENV = True  # Should be overridden
        assert _is_strict() is True
        
        mock_settings.SSE_REDIS_STRICT = False
        mock_settings.IS_LOCAL_ENV = False  # Should be overridden
        assert _is_strict() is False

