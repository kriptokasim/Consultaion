"""Tests for beta access control."""
import pytest
from beta_access import is_beta_user, require_beta_access
from config import settings
from exceptions import PermissionError as AppPermissionError
from models import User


def test_beta_access_disabled_allows_all():
    """When ENABLE_BETA_ACCESS is False, all users have access."""
    settings.ENABLE_BETA_ACCESS = False
    
    user = User(id="1", email="user@example.com", password_hash="hash", role="user")
    assert is_beta_user(user) is True
    assert is_beta_user(None) is True  # Even unauthenticated


def test_beta_access_enabled_blocks_non_whitelist():
    """When ENABLE_BETA_ACCESS is True, non-whitelist users are blocked."""
    settings.ENABLE_BETA_ACCESS = True
    settings.BETA_WHITELIST = "beta@example.com"
    
    user = User(id="1", email="user@example.com", password_hash="hash", role="user")
    assert is_beta_user(user) is False


def test_beta_access_whitelist_allows_user():
    """Users in BETA_WHITELIST have access."""
    settings.ENABLE_BETA_ACCESS = True
    settings.BETA_WHITELIST = "beta1@example.com, beta2@example.com"
    
    beta_user = User(id="1", email="beta1@example.com", password_hash="hash", role="user")
    assert is_beta_user(beta_user) is True


def test_beta_access_admin_always_allowed():
    """Admins always have beta access."""
    settings.ENABLE_BETA_ACCESS = True
    settings.BETA_WHITELIST = ""
    
    admin = User(id="1", email="admin@example.com", password_hash="hash", role="admin")
    assert is_beta_user(admin) is True


def test_require_beta_access_raises_for_non_beta():
    """require_beta_access raises PermissionError for non-beta users."""
    settings.ENABLE_BETA_ACCESS = True
    settings.BETA_WHITELIST = ""
    
    user = User(id="1", email="user@example.com", password_hash="hash", role="user")
    
    with pytest.raises(AppPermissionError) as exc_info:
        require_beta_access(user, "test feature")
    
    assert "Beta access required" in str(exc_info.value)
    assert exc_info.value.code == "beta.access_required"


def test_require_beta_access_allows_beta_user():
    """require_beta_access allows beta users through."""
    settings.ENABLE_BETA_ACCESS = True
    settings.BETA_WHITELIST = "beta@example.com"
    
    beta_user = User(id="1", email="beta@example.com", password_hash="hash", role="user")
    
    # Should not raise
    require_beta_access(beta_user, "test feature")
