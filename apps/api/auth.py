import hashlib
import hmac
import logging
import secrets
import time
from typing import Any, Dict, Optional

import jwt
from config import settings
from deps import get_session
from fastapi import Depends, HTTPException, Request, Response, status
from log_config import update_log_context
from models import User
from sqlmodel import Session, select

logger = logging.getLogger(__name__)


def _safe_auth_log(request) -> dict:
    """Return a safe dict of auth indicators for debug logging.

    NEVER includes raw token/header values — only presence booleans and
    non-sensitive metadata.
    """
    return {
        "path": request.url.path,
        "has_session_cookie": settings.COOKIE_NAME in request.cookies,
        "has_auth_header": bool(request.headers.get("Authorization")),
        "cookie_names": sorted(request.cookies.keys()),
    }

# Helper properties to access settings dynamically (respecting reloads)
def _get_jwt_secret() -> str:
    secret = settings.JWT_SECRET
    if not secret:
        raise RuntimeError("JWT_SECRET must be set")
    if secret == "change_me_in_prod":
        settings.reload()
        secret = settings.JWT_SECRET
    if secret == "change_me_in_prod" and not settings.IS_LOCAL_ENV:
        raise RuntimeError("JWT_SECRET must be changed from default value")
    return secret

def _get_cookie_samesite() -> str:
    val = settings.COOKIE_SAMESITE.strip().lower()
    if val not in {"lax", "strict", "none"}:
        return "Lax"
    return "none" if val == "none" else val.capitalize()

# Re-export key settings for module-level imports in main.py and other routers
# Note: These values will not reflect settings.reload() unless they are re-imported.
# For dynamic behavior, use settings.X directly or the helper functions above.
COOKIE_NAME = settings.COOKIE_NAME
JWT_SECRET = settings.JWT_SECRET
JWT_TTL_SECONDS = settings.JWT_TTL_SECONDS
PBKDF2_ITERATIONS = settings.PASSWORD_ITERATIONS
COOKIE_SECURE = settings.COOKIE_SECURE
COOKIE_PATH = settings.COOKIE_PATH
COOKIE_DOMAIN = settings.COOKIE_DOMAIN
ENABLE_CSRF = settings.ENABLE_CSRF
CSRF_COOKIE_NAME = settings.CSRF_COOKIE_NAME

# Samesite needs normalization for export
_SAMESITE_RAW = settings.COOKIE_SAMESITE.strip().lower()
if _SAMESITE_RAW not in {"lax", "strict", "none"}:
    _SAMESITE_RAW = "lax"
COOKIE_SAMESITE = "none" if _SAMESITE_RAW == "none" else _SAMESITE_RAW.capitalize()

JWT_ALGORITHM = "HS256"


def hash_password(password: str) -> str:
    salt = secrets.token_hex(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt.encode("utf-8"), settings.PASSWORD_ITERATIONS)
    return f"pbkdf2_sha256${salt}${digest.hex()}"


def verify_password(password: str, password_hash: str) -> bool:
    try:
        _, salt, stored = password_hash.split("$")
    except ValueError:
        return False
    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt.encode("utf-8"), settings.PASSWORD_ITERATIONS)
    return hmac.compare_digest(digest.hex(), stored)


def _build_claims(payload: Dict[str, Any], ttl_seconds: int | None = None) -> Dict[str, Any]:
    now = int(time.time())
    ttl = ttl_seconds or settings.JWT_TTL_SECONDS
    return {
        **payload,
        "iat": now,
        "nbf": now,
        "exp": now + ttl,
    }


def create_access_token(*, user_id: str, email: str, role: str, ttl_seconds: int | None = None) -> str:
    claims = _build_claims(
        {
            "sub": user_id,
            "email": email,
            "role": role,
        },
        ttl_seconds=ttl_seconds,
    )
    token = jwt.encode(claims, _get_jwt_secret(), algorithm=JWT_ALGORITHM)
    return token


def decode_access_token(token: str) -> Dict[str, Any]:
    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing token",
        )
    try:
        return jwt.decode(
            token,
            _get_jwt_secret(),
            algorithms=[JWT_ALGORITHM],
            options={"require": ["exp", "iat"]},
        )
    except jwt.ExpiredSignatureError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token expired",
        ) from exc
    except jwt.InvalidTokenError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token",
        ) from exc


def resolve_user_from_token(token: Optional[str], session: Session) -> Optional[User]:
    """Resolve a user from a JWT token string.
    
    Used by cookie auth, Bearer header auth, and SSE query-param token auth.
    """
    if not token:
        return None
    try:
        payload = decode_access_token(token)
    except HTTPException:
        return None
    user_id = payload.get("sub")
    if not user_id:
        return None
    user = session.get(User, user_id)
    if user:
        update_log_context(user_id=user.id)
    return user


def get_optional_user(
    request: Request,
    session: Session = Depends(get_session),
) -> Optional[User]:
    token = request.cookies.get(settings.COOKIE_NAME)
    if not token:
        auth_header = request.headers.get("Authorization")
        if auth_header and auth_header.startswith("Bearer "):
            token = auth_header[7:]
    return resolve_user_from_token(token, session)


def get_current_user(
    request: Request,
    session: Session = Depends(get_session),
) -> User:
    user = get_optional_user(request=request, session=session)
    if not user:
        # [AUTH_DEBUG] Patchset 53.0: Log unauthorized access attempt
        if settings.AUTH_DEBUG:
            ctx = _safe_auth_log(request)
            logger.warning(
                "[AUTH_DEBUG] Unauthorized: path=%s has_session_cookie=%s "
                "has_auth_header=%s cookie_names=%s",
                ctx["path"],
                ctx["has_session_cookie"],
                ctx["has_auth_header"],
                ctx["cookie_names"],
            )

        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="authentication required")
    if hasattr(user, "is_active") and not user.is_active:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Account disabled")
    return user


def get_current_admin(user: User = Depends(get_current_user)) -> User:
    is_admin = getattr(user, "is_admin", False) or user.role == "admin"
    if not is_admin:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin access required")
    return user


def set_auth_cookie(response: Response, token: str) -> None:
    # TODO: For browser auth in production, add CSRF tokens for state-changing routes when using cookies.
    response.set_cookie(
        key=settings.COOKIE_NAME,
        value=token,
        httponly=True,
        secure=settings.COOKIE_SECURE,
        samesite=_get_cookie_samesite(),
        max_age=settings.JWT_TTL_SECONDS,
        path=settings.COOKIE_PATH,
        domain=settings.COOKIE_DOMAIN,
    )


def set_csrf_cookie(response: Response, token: str) -> None:
    response.set_cookie(
        key=settings.CSRF_COOKIE_NAME,
        value=token,
        httponly=False,
        secure=settings.COOKIE_SECURE,
        samesite=_get_cookie_samesite(),
        max_age=settings.JWT_TTL_SECONDS,
        path=settings.COOKIE_PATH,
        domain=settings.COOKIE_DOMAIN,
    )


def clear_auth_cookie(response: Response) -> None:
    response.delete_cookie(settings.COOKIE_NAME, path=settings.COOKIE_PATH, domain=settings.COOKIE_DOMAIN)


def clear_csrf_cookie(response: Response) -> None:
    response.delete_cookie(settings.CSRF_COOKIE_NAME, path=settings.COOKIE_PATH, domain=settings.COOKIE_DOMAIN)


def generate_csrf_token() -> str:
    return secrets.token_urlsafe(32)


# Patchset 37.0: API Key Authentication

def get_user_from_api_key(
    request: Request,
    session: Session = Depends(get_session),
) -> Optional[User]:
    """
    Authenticate user via API key from headers.
    
    Checks both Authorization: Bearer and X-API-Key headers.
    Returns None if no valid API key is found.
    """
    from datetime import datetime, timezone

    from api_key_utils import extract_prefix, verify_api_key
    from models import APIKey
    
    # Check Authorization: Bearer header
    auth_header = request.headers.get("Authorization", "")
    api_key_value = None
    
    if auth_header.startswith("Bearer "):
        api_key_value = auth_header[7:]  # Remove "Bearer " prefix
    else:
        # Check X-API-Key header
        api_key_value = request.headers.get("X-API-Key")
    
    if not api_key_value:
        return None
    
    # Extract prefix and look up key
    prefix = extract_prefix(api_key_value)
    
    stmt = select(APIKey).where(APIKey.prefix == prefix)
    api_key_record = session.exec(stmt).first()
    
    if not api_key_record:
        return None
    
    # Verify key is not revoked
    if api_key_record.revoked:
        return None
    
    # Verify the full key matches the hash
    if not verify_api_key(api_key_value, api_key_record.hashed_key):
        return None
    
    # Update last_used_at
    api_key_record.last_used_at = datetime.now(timezone.utc)
    session.add(api_key_record)
    session.commit()
    
    # Get the user
    user = session.get(User, api_key_record.user_id)
    if user:
        update_log_context(user_id=user.id, api_key_id=api_key_record.id)
    
    return user


def get_user_flexible(
    request: Request,
    session: Session = Depends(get_session),
) -> Optional[User]:
    """
    Get user from either cookie (JWT) or API key.
    
    Tries API key first, then falls back to cookie auth.
    """
    # Try API key first
    user = get_user_from_api_key(request, session)
    if user:
        return user
    
    # Fall back to cookie auth
    return get_optional_user(request, session)


def get_current_user_flexible(
    request: Request,
    session: Session = Depends(get_session),
) -> User:
    """
    Get current user from either cookie or API key, requiring authentication.
    """
    user = get_user_flexible(request, session)
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="authentication required")
    if hasattr(user, "is_active") and not user.is_active:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Account disabled")
    return user
