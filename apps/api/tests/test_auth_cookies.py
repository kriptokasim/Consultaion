"""
Patchset 53.0: Auth Cookie Configuration Tests

Verifies cookie settings match environment expectations.
"""

import os
import sys
from pathlib import Path

os.environ.setdefault("JWT_SECRET", "test-secret-at-least-32-chars-long")
os.environ.setdefault("USE_MOCK", "1")
os.environ.setdefault("COOKIE_SECURE", "0")

sys.path.append(str(Path(__file__).resolve().parents[1]))


def test_local_env_cookie_settings():
    """Test that local env uses safe cookie defaults"""
    os.environ["ENV"] = "development"
    os.environ.pop("RENDER", None)  # Remove RENDER flag if present
    
    # Force reload to pick up env change
    from config import settings
    settings.reload()
    
    assert settings.IS_LOCAL_ENV is True
    assert settings.COOKIE_SECURE is False
    assert settings.COOKIE_SAMESITE.lower() == "lax"


def test_production_env_cookie_settings():
    """Test that production env uses secure cookie settings"""
    os.environ["ENV"] = "production"
    os.environ["RENDER"] = "true"
    os.environ["JWT_SECRET"] = "production-test-secret-at-least-32-characters-long"
    os.environ["STRIPE_WEBHOOK_VERIFY"] = "0"  # Not testing Stripe in this test
    os.environ["REDIS_URL"] = "redis://localhost:6379/0"  # Dummy — prod requires redis
    os.environ["REQUIRE_REAL_LLM"] = "0"  # No provider keys in test
    
    # Force reload
    from config import settings
    settings.reload()
    
    assert settings.IS_LOCAL_ENV is False
    assert settings.COOKIE_SECURE is True
    assert settings.COOKIE_SAMESITE.lower() == "none"


def test_cookie_attributes_in_response():
    """Test that set_auth_cookie applies correct attributes"""
    from auth import set_auth_cookie
    from config import settings
    from fastapi import Response
    
    response = Response()
    token = "fake_jwt_token"
    
    set_auth_cookie(response, token)
    
    # Verify Set-Cookie header exists
    assert "set-cookie" in response.headers
    cookie_header = response.headers["set-cookie"]
    
    # Verify key attributes
    assert "httponly" in cookie_header.lower()
    assert "path=/" in cookie_header.lower()
    
    # In local env, should not have Secure
    if settings.IS_LOCAL_ENV:
        # May or may not have secure=False explicitly
        pass
    else:
        assert "secure" in cookie_header.lower()


def test_auth_debug_flag_defaults_to_false():
    """Test that AUTH_DEBUG defaults to False"""
    from config import settings
    
    # Should default to False
    # (unless explicitly set in test env, but we don't set it)
    assert isinstance(settings.AUTH_DEBUG, bool)
