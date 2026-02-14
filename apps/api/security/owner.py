"""
Patchset 103: Owner Allowlist

Centralized helper to determine if a user is in the owner allowlist.
Owner users receive plan upgrades and quota bypasses.
"""

import logging
from typing import TYPE_CHECKING, Optional

if TYPE_CHECKING:
    from models import User

logger = logging.getLogger(__name__)


def is_owner(user: Optional["User"], settings=None) -> bool:
    """
    Check if user email is in the owner allowlist.

    Args:
        user: User object (None → False)
        settings: AppSettings instance (uses global if omitted)

    Returns:
        True if user's email is in OWNER_EMAIL_ALLOWLIST
    """
    if user is None:
        return False

    email = getattr(user, "email", None)
    if not email:
        return False

    if settings is None:
        from config import settings  # noqa: F811 — lazy import to avoid circular

    return email.strip().lower() in settings.owner_emails
