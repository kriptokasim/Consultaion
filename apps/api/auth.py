import hashlib
import hmac
import os
import secrets
import time
from typing import Any, Dict

import jwt
from fastapi import HTTPException, Response, status

COOKIE_NAME = os.getenv("COOKIE_NAME", "consultaion_token")
JWT_SECRET = os.getenv("JWT_SECRET")
if not JWT_SECRET:
    raise RuntimeError("JWT_SECRET must be set")
if JWT_SECRET == "change_me_in_prod":
    raise RuntimeError("JWT_SECRET must be changed from default value")
JWT_ALGORITHM = "HS256"
_expire_minutes_default = int(os.getenv("JWT_EXPIRE_MINUTES", "4320"))
JWT_TTL_SECONDS = int(os.getenv("JWT_TTL_SECONDS", str(_expire_minutes_default * 60)))
PBKDF2_ITERATIONS = int(os.getenv("PASSWORD_ITERATIONS", "20000"))
COOKIE_SECURE = os.getenv("COOKIE_SECURE", "1").strip().lower() not in {"0", "false", "no"}
_SAMESITE_VALUE = os.getenv("COOKIE_SAMESITE", "lax").strip().lower()
if _SAMESITE_VALUE not in {"lax", "strict", "none"}:
    _SAMESITE_VALUE = "lax"
COOKIE_SAMESITE = "None" if _SAMESITE_VALUE == "none" else _SAMESITE_VALUE.capitalize()
COOKIE_PATH = os.getenv("COOKIE_PATH", "/")
ENABLE_CSRF = os.getenv("ENABLE_CSRF", "0").strip().lower() in {"1", "true", "yes"}
CSRF_COOKIE_NAME = os.getenv("CSRF_COOKIE_NAME", "csrf_token")


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
