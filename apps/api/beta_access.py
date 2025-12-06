"""Beta access control utilities.

Provides functions to check beta access for features gated behind the beta program.
"""
from typing import Optional

from config import settings
from models import User


def is_beta_user(user: Optional[User]) -> bool:
    """
    Check if a user has beta access.
    
    Args:
        user: User to check, or None for unauthenticated
        
    Returns:
        True if user has beta access, False otherwise
        
    Rules:
        - If ENABLE_BETA_ACCESS is False, all users have access
        - Admins always have access
        - Users in BETA_WHITELIST have access
        - All other users are denied
    """
    # If beta access is not restricted, everyone has access
    if not settings.ENABLE_BETA_ACCESS:
        return True
    
    # Unauthenticated users never have beta access
    if not user:
        return False
    
    # Admins always have access
    if user.role == "admin":
        return True
    
    # Check if user is in whitelist
    whitelist_raw = settings.BETA_WHITELIST.strip()
    if not whitelist_raw:
        # No whitelist = no beta users (admins only)
        return False
    
    whitelist_emails = {email.strip().lower() for email in whitelist_raw.split(",") if email.strip()}
    return user.email.lower() in whitelist_emails


def require_beta_access(user: Optional[User], feature_name: str = "feature") -> None:
    """
    Require beta access for a feature.
    
    Args:
        user: User to check
        feature_name: Name of the feature for error message
        
    Raises:
        PermissionError: If user does not have beta access
    """
    if not is_beta_user(user):
        from exceptions import PermissionError as AppPermissionError
        raise AppPermissionError(
            message=f"Beta access required for {feature_name}",
            code="beta.access_required"
        )
