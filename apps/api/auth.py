import base64
import hashlib
import hmac
import json
import os
import secrets
from datetime import datetime, timedelta, timezone
from typing import Any, Dict

from fastapi import Response

COOKIE_NAME = os.getenv("COOKIE_NAME", "consultaion_token")
JWT_SECRET = os.getenv("JWT_SECRET")
if not JWT_SECRET:
    raise RuntimeError("JWT_SECRET must be set")
if JWT_SECRET == "change_me_in_prod":
    raise RuntimeError("JWT_SECRET must be changed from default value")
JWT_EXPIRES_MINUTES = int(os.getenv("JWT_EXPIRE_MINUTES", "4320"))
PBKDF2_ITERATIONS = int(os.getenv("PASSWORD_ITERATIONS", "20000"))
COOKIE_SECURE = os.getenv("COOKIE_SECURE", "1").strip().lower() not in {"0", "false", "no"}
_SAMESITE_VALUE = os.getenv("COOKIE_SAMESITE", "lax").strip().lower()
if _SAMESITE_VALUE not in {"lax", "strict", "none"}:
    _SAMESITE_VALUE = "lax"
COOKIE_SAMESITE = "None" if _SAMESITE_VALUE == "none" else _SAMESITE_VALUE.capitalize()
COOKIE_PATH = os.getenv("COOKIE_PATH", "/")


def _b64encode(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode("utf-8")


def _b64decode(data: str) -> bytes:
    padding = "=" * ((4 - len(data) % 4) % 4)
    return base64.urlsafe_b64decode(data + padding)


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


def create_access_token(*, user_id: str, email: str, role: str) -> str:
    header = {"alg": "HS256", "typ": "JWT"}
    expires = datetime.now(timezone.utc) + timedelta(minutes=JWT_EXPIRES_MINUTES)
    payload = {
        "sub": user_id,
        "email": email,
        "role": role,
        "exp": int(expires.timestamp()),
    }
    header_b64 = _b64encode(json.dumps(header, separators=(",", ":")).encode("utf-8"))
    payload_b64 = _b64encode(json.dumps(payload, separators=(",", ":")).encode("utf-8"))
    signing_input = f"{header_b64}.{payload_b64}".encode("utf-8")
    signature = hmac.new(JWT_SECRET.encode("utf-8"), signing_input, hashlib.sha256).digest()
    token = f"{header_b64}.{payload_b64}.{_b64encode(signature)}"
    return token


def decode_access_token(token: str) -> Dict[str, Any]:
    try:
        header_b64, payload_b64, signature_b64 = token.split(".")
    except ValueError as exc:
        raise ValueError("invalid token") from exc
    signing_input = f"{header_b64}.{payload_b64}".encode("utf-8")
    expected_sig = hmac.new(JWT_SECRET.encode("utf-8"), signing_input, hashlib.sha256).digest()
    actual_sig = _b64decode(signature_b64)
    if not hmac.compare_digest(expected_sig, actual_sig):
        raise ValueError("invalid signature")
    payload = json.loads(_b64decode(payload_b64))
    exp = payload.get("exp")
    if exp and datetime.now(timezone.utc).timestamp() > float(exp):
        raise ValueError("token expired")
    return payload


def set_auth_cookie(response: Response, token: str) -> None:
    response.set_cookie(
        key=COOKIE_NAME,
        value=token,
        httponly=True,
        secure=COOKIE_SECURE,
        samesite=COOKIE_SAMESITE,
        max_age=JWT_EXPIRES_MINUTES * 60,
        path=COOKIE_PATH,
    )


def clear_auth_cookie(response: Response) -> None:
    response.delete_cookie(COOKIE_NAME, path=COOKIE_PATH)
