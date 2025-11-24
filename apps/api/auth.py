import hashlib
import hmac
import secrets
import time
from typing import Any, Dict, Optional

import jwt
from fastapi import Depends, HTTPException, Request, Response, status
from sqlmodel import Session

from deps import get_session
from config import settings
from log_config import update_log_context
from models import User

COOKIE_NAME = settings.COOKIE_NAME
JWT_SECRET = settings.JWT_SECRET
if not JWT_SECRET:
    raise RuntimeError("JWT_SECRET must be set")
if JWT_SECRET == "change_me_in_prod":
    settings.reload()
    JWT_SECRET = settings.JWT_SECRET
if JWT_SECRET == "change_me_in_prod":
    raise RuntimeError("JWT_SECRET must be changed from default value")
JWT_ALGORITHM = "HS256"
JWT_TTL_SECONDS = settings.JWT_TTL_SECONDS
PBKDF2_ITERATIONS = settings.PASSWORD_ITERATIONS
COOKIE_SECURE = settings.COOKIE_SECURE
_SAMESITE_VALUE = settings.COOKIE_SAMESITE.strip().lower()
if _SAMESITE_VALUE not in {"lax", "strict", "none"}:
    _SAMESITE_VALUE = "lax"
COOKIE_SAMESITE = "None" if _SAMESITE_VALUE == "none" else _SAMESITE_VALUE.capitalize()
COOKIE_PATH = settings.COOKIE_PATH
ENABLE_CSRF = settings.ENABLE_CSRF
CSRF_COOKIE_NAME = settings.CSRF_COOKIE_NAME


def hash_password(password: str) -> str:
    salt = secrets.token_hex(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt.encode("utf-8"), PBKDF2_ITERATIONS)
    return f"pbkdf2_sha256${salt}${digest.hex()}"


def verify_password(password: str, password_hash: str) -> bool:
    try:
        _, salt, stored = password_hash.split("$")
    except ValueError:
        return False
    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt.encode("utf-8"), PBKDF2_ITERATIONS)
    return hmac.compare_digest(digest.hex(), stored)


def _build_claims(payload: Dict[str, Any], ttl_seconds: int | None = None) -> Dict[str, Any]:
    now = int(time.time())
    ttl = ttl_seconds or JWT_TTL_SECONDS
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
    token = jwt.encode(claims, JWT_SECRET, algorithm=JWT_ALGORITHM)
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
            JWT_SECRET,
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


def _resolve_user_from_token(token: Optional[str], session: Session) -> Optional[User]:
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
    token = request.cookies.get(COOKIE_NAME)
    return _resolve_user_from_token(token, session)


def get_current_user(
    request: Request,
    session: Session = Depends(get_session),
) -> User:
    user = get_optional_user(request=request, session=session)
    if not user:
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
        key=COOKIE_NAME,
        value=token,
        httponly=True,
        secure=COOKIE_SECURE,
        samesite=COOKIE_SAMESITE,
        max_age=JWT_TTL_SECONDS,
        path=COOKIE_PATH,
    )


def set_csrf_cookie(response: Response, token: str) -> None:
    response.set_cookie(
        key=CSRF_COOKIE_NAME,
        value=token,
        httponly=False,
        secure=COOKIE_SECURE,
        samesite=COOKIE_SAMESITE,
        max_age=JWT_TTL_SECONDS,
        path=COOKIE_PATH,
    )


def clear_auth_cookie(response: Response) -> None:
    response.delete_cookie(COOKIE_NAME, path=COOKIE_PATH)


def clear_csrf_cookie(response: Response) -> None:
    response.delete_cookie(CSRF_COOKIE_NAME, path=COOKIE_PATH)


def generate_csrf_token() -> str:
    return secrets.token_urlsafe(32)
