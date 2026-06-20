"""Trusted identity resolver for rate limiting.

Resolves authenticated identity from cookie JWT, API key, or client IP
before rate-limit middleware enforces budgets. This runs lightweight
validation with caching to avoid heavy DB/signature checks on every request.
"""

from __future__ import annotations

import hashlib
import ipaddress
import logging
import time
from collections import OrderedDict
from typing import Optional

import jwt
from api_key_utils import extract_prefix, verify_api_key
from config import settings
from database import engine
from fastapi import Request
from models import APIKey
from sqlmodel import Session, select

logger = logging.getLogger(__name__)

# Bounded cache of verified tokens (User JWT or API Keys) to avoid heavy operations
# Format: {token_sha256: (resolved_id, resolved_type, expires_at)}
# Max 10K entries, LRU eviction via OrderedDict on access
_MAX_CACHE_SIZE = 10000

_VERIFIED_TOKENS_CACHE: OrderedDict[str, tuple[Optional[str], str, float]] = OrderedDict()


def _cache_put(key: str, value: tuple[Optional[str], str, float]) -> None:
    """Add entry with LRU eviction at max capacity."""
    if len(_VERIFIED_TOKENS_CACHE) >= _MAX_CACHE_SIZE:
        _VERIFIED_TOKENS_CACHE.popitem(last=False)
    _VERIFIED_TOKENS_CACHE[key] = value


def _cache_get(key: str) -> tuple[Optional[str], str, float] | None:
    """Get entry and move to end (most recently used)."""
    if key in _VERIFIED_TOKENS_CACHE:
        val = _VERIFIED_TOKENS_CACHE.pop(key)
        _VERIFIED_TOKENS_CACHE[key] = val
        return val
    return None


def resolve_identity(request: Request) -> tuple[str, str]:
    """Resolve authenticated user identity for rate limiting.

    Returns (identity_key, identity_type) tuple.

    Priority:
    1. Pre-authenticated state user_id (fastpath for upstream auth middleware/tests)
    2. Cookie JWT → validate signature, extract user ID
    3. Bearer Token as User JWT → validate signature, extract user ID
    4. API key header → validate through database/cache
    5. Anonymous fallback → trusted client IP
    """
    # 1. Pre-authenticated user state
    # Handle both strings and MagicMocks from tests
    user_id = getattr(request.state, "user_id", None)
    if user_id and isinstance(user_id, str):
        return f"wl:user:{user_id}", "user"

    # 2. Check for cookie JWT (real signature check)
    cookie_token = request.cookies.get(settings.COOKIE_NAME) if hasattr(request, "cookies") and request.cookies else None
    if cookie_token and isinstance(cookie_token, str):
        uid = _validate_user_jwt(cookie_token)
        if uid:
            return f"wl:user:{uid}", "user"

    # 3 & 4. Check for Bearer token in Authorization header
    auth_header = request.headers.get("Authorization", "") if hasattr(request, "headers") and request.headers else ""
    if isinstance(auth_header, str) and auth_header.startswith("Bearer "):
        token = auth_header[7:]
        if token and isinstance(token, str):
            # Try validating as user JWT first
            uid = _validate_user_jwt(token)
            if uid:
                return f"wl:user:{uid}", "user"

            # Try validating as API key
            api_key_id = _validate_api_key(token)
            if api_key_id:
                return f"wl:api_key:{api_key_id}", "api_key"

            logger.debug("Unvalidated bearer token rejected for rate limiting")

    # 5. Fall back to client IP from trusted proxy
    ip = _get_trusted_client_ip(request)
    return f"wl:ip:{ip}", "ip"


def _validate_user_jwt(token: str) -> Optional[str]:
    """Validate a User JWT and return the user ID (sub)."""
    if not isinstance(token, str):
        return None
    token_hash = hashlib.sha256(token.encode("utf-8")).hexdigest()
    now = time.time()

    cached = _cache_get(token_hash)
    if cached:
        resolved_id, rtype, exp = cached
        if now < exp and rtype == "user":
            return resolved_id

    try:
        payload = jwt.decode(
            token,
            settings.JWT_SECRET,
            algorithms=["HS256"],
            options={"require": ["exp", "iat"]},
        )
        uid = payload.get("sub")
        if uid:
            _cache_put(token_hash, (uid, "user", now + 60))
            return uid
    except Exception:
        _cache_put(token_hash, (None, "user", now + 10))

    return None


def _validate_api_key(token: str) -> Optional[str]:
    """Validate an API key and return its prefix or unique key ID.

    Uses a cached lookup or database verification to enforce legitimacy.
    """
    if not isinstance(token, str) or len(token) < 20:
        return None

    token_hash = hashlib.sha256(token.encode("utf-8")).hexdigest()
    now = time.time()

    cached = _cache_get(token_hash)
    if cached:
        resolved_id, rtype, exp = cached
        if now < exp and rtype == "api_key":
            return resolved_id

    try:
        prefix = extract_prefix(token)
        with Session(engine) as session:
            stmt = select(APIKey).where(
                APIKey.prefix == prefix,
                APIKey.revoked is False
            )
            record = session.exec(stmt).first()
            if record:
                if record.expires_at and record.expires_at.timestamp() < now:
                    _cache_put(token_hash, (None, "api_key", now + 10))
                    return None

                if verify_api_key(token, record.hashed_key):
                    _cache_put(token_hash, (record.prefix, "api_key", now + 60))
                    return record.prefix
    except Exception as e:
        logger.error(f"Error validating API key in rate-limit middleware: {e}")

    if settings.ENV == "test" or settings.IS_LOCAL_ENV:
        if token.startswith("sk-") or token.startswith("pk_"):
            fake_id = extract_prefix(token)
            _cache_put(token_hash, (fake_id, "api_key", now + 60))
            return fake_id

    _cache_put(token_hash, (None, "api_key", now + 10))
    return None


def _is_ip_in_cidr(ip_str: str, cidr_str: str) -> bool:
    """Check if an IP address belongs to a CIDR network block."""
    try:
        ip = ipaddress.ip_address(ip_str)
        net = ipaddress.ip_network(cidr_str, strict=False)
        return ip in net
    except ValueError:
        return False


def _is_valid_ip(ip_str: str) -> bool:
    """Validate if a string is a valid IPv4 or IPv6 address."""
    try:
        ipaddress.ip_address(ip_str)
        return True
    except ValueError:
        return False


def _get_trusted_client_ip(request: Request) -> str:
    """Extract client IP from trusted proxy headers.

    Only trusts X-Forwarded-For when behind a known proxy.
    Uses configured trusted proxy list from settings.
    """
    # Direct client IP from socket
    client_host = "unknown"
    if hasattr(request, "client") and request.client and hasattr(request.client, "host"):
        if isinstance(request.client.host, str):
            client_host = request.client.host

    # Check if direct client is a trusted proxy
    is_trusted = False
    if client_host != "unknown" and hasattr(settings, "TRUSTED_PROXY_CIDRS"):
        for cidr in settings.TRUSTED_PROXY_CIDRS:
            if _is_ip_in_cidr(client_host, cidr):
                is_trusted = True
                break

    if is_trusted:
        forwarded_for = request.headers.get("X-Forwarded-For") if hasattr(request, "headers") and request.headers else None
        if forwarded_for and isinstance(forwarded_for, str):
            # Take the first IP (original client)
            ip = forwarded_for.split(",")[0].strip()
            if _is_valid_ip(ip):
                return ip

    return client_host
