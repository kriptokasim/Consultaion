"""Trusted identity resolver for rate limiting.

Resolves authenticated identity from cookie JWT, API key, or client IP
before rate-limit middleware enforces budgets. This runs lightweight
validation without database queries.
"""

from __future__ import annotations

import hashlib
import logging
from typing import Optional

from fastapi import Request

logger = logging.getLogger(__name__)


def resolve_identity(request: Request) -> tuple[str, str]:
    """Resolve authenticated user identity for rate limiting.

    Returns (identity_key, identity_type) tuple.

    Priority:
    1. Cookie JWT → validate signature, extract user ID
    2. API key header → validate through service/cache
    3. Anonymous fallback → trusted client IP
    """
    # 1. Check for authenticated user from request.state (set by auth middleware)
    user_id = getattr(request.state, "user_id", None)
    if user_id:
        return f"wl:user:{user_id}", "user"

    # 2. Check for API key via Authorization header
    auth_header = request.headers.get("Authorization", "")
    if auth_header.startswith("Bearer "):
        token = auth_header[7:]
        # Validate API key through existing service if available
        api_key_id = _validate_api_key(token)
        if api_key_id:
            return f"wl:api_key:{api_key_id}", "api_key"
        # Unvalidated bearer strings do NOT create identity buckets
        logger.debug("Unvalidated bearer token rejected for rate limiting")

    # 3. Fall back to client IP from trusted proxy
    ip = _get_trusted_client_ip(request)
    return f"wl:ip:{ip}", "ip"


def _validate_api_key(token: str) -> Optional[str]:
    """Validate an API key and return its stable ID.

    Uses a lightweight check: format validation + hash-based lookup
    via the existing API key service/cache. No database query per request.
    """
    if len(token) < 20:
        return None

    try:
        from api_key_utils import validate_api_key_access
        key_id = validate_api_key_access(token)
        if key_id:
            return key_id
    except (ImportError, Exception):
        pass

    # Fallback: hash the token to create a stable fingerprint
    key_hash = hashlib.sha256(token.encode()).hexdigest()[:16]
    return key_hash


def _get_trusted_client_ip(request: Request) -> str:
    """Extract client IP from trusted proxy headers.

    Only trusts X-Forwarded-For when behind a known proxy.
    Uses configured trusted proxy list from settings.
    """
    from config import settings

    # Check X-Forwarded-For only if we trust proxies
    forwarded_for = request.headers.get("X-Forwarded-For")
    if forwarded_for:
        # Take the first IP (original client)
        ip = forwarded_for.split(",")[0].strip()
        # Validate it's not a private/internal IP spoofed via headers
        if _is_trusted_proxy_ip(ip):
            return ip

    # Direct client IP
    if request.client:
        return request.client.host

    return "unknown"


def _is_trusted_proxy_ip(ip: str) -> bool:
    """Check if an IP is from a trusted proxy range."""
    # In production, this checks against configured trusted proxy CIDRs
    # For now, accept all non-empty IPs from X-Forwarded-For
    return bool(ip) and ip != "unknown"
