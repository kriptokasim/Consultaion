import os
import secrets
from typing import Any, Optional
from urllib.parse import urlencode, urlparse

import httpx
from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from fastapi.responses import RedirectResponse
from sqlmodel import Session, select

from pydantic import BaseModel

from audit import record_audit
from auth import (
    ENABLE_CSRF,
    clear_auth_cookie,
    clear_csrf_cookie,
    create_access_token,
    generate_csrf_token,
    hash_password,
    set_auth_cookie,
    set_csrf_cookie,
    verify_password,
    COOKIE_SECURE,
    COOKIE_SAMESITE,
)
from deps import get_current_user, get_session
from models import TeamMember, User
from ratelimit import increment_ip_bucket, record_429
from routes.common import AUTH_MAX_CALLS, AUTH_WINDOW, serialize_user, user_team_role

router = APIRouter(tags=["auth"])


class AuthRequest(BaseModel):
    email: str
    password: str


class UserProfile(BaseModel):
    id: str
    email: str
    role: str


GOOGLE_AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
GOOGLE_TOKEN_URL = "https://oauth2.googleapis.com/token"
GOOGLE_USERINFO_URL = "https://www.googleapis.com/oauth2/v3/userinfo"
OAUTH_STATE_COOKIE = "google_oauth_state"
OAUTH_NEXT_COOKIE = "google_oauth_next"
SAFE_NEXT_DEFAULT = "/dashboard"
SAFE_NEXT_PREFIXES = ("/dashboard", "/runs", "/live", "/leaderboard", "/")

_WEB_ORIGIN_ENV_KEYS = [
    "WEB_APP_ORIGIN",
    "NEXT_PUBLIC_WEB_URL",
    "NEXT_PUBLIC_APP_URL",
    "NEXT_PUBLIC_WEB_ORIGIN",
    "NEXT_PUBLIC_APP_ORIGIN",
    "NEXT_PUBLIC_SITE_URL",
]
for _env_key in _WEB_ORIGIN_ENV_KEYS:
    _candidate = os.getenv(_env_key)
    if _candidate:
        WEB_APP_ORIGIN = _candidate.rstrip("/")
        break
else:
    WEB_APP_ORIGIN = "http://localhost:3000"


def sanitize_next_path(raw_next: Optional[str]) -> str:
    candidate = (raw_next or "").strip()
    if not candidate:
        return SAFE_NEXT_DEFAULT
    parsed = urlparse(candidate)
    if parsed.scheme or parsed.netloc:
        return SAFE_NEXT_DEFAULT
    path = parsed.path or SAFE_NEXT_DEFAULT
    if not path.startswith("/"):
        path = f"/{path}"

    def _allowed(p: str) -> bool:
        allowed = False
        for prefix in SAFE_NEXT_PREFIXES:
            if prefix == "/":
                if p == "/":
                    allowed = True
                    break
            elif p.startswith(prefix):
                allowed = True
                break
        return allowed

    if not _allowed(path):
        return SAFE_NEXT_DEFAULT
    query = f"?{parsed.query}" if parsed.query else ""
    fragment = f"#{parsed.fragment}" if parsed.fragment else ""
    return f"{path}{query}{fragment}"


def build_frontend_redirect(path: str) -> str:
    cleaned = path if path.startswith("/") else f"/{path}"
    return f"{WEB_APP_ORIGIN}{cleaned}"


def _google_config() -> tuple[str, str, str]:
    client_id = os.getenv("GOOGLE_CLIENT_ID")
    client_secret = os.getenv("GOOGLE_CLIENT_SECRET")
    redirect_url = os.getenv("GOOGLE_REDIRECT_URL")
    if not client_id or not client_secret or not redirect_url:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Google auth not configured")
    return client_id, client_secret, redirect_url


async def _exchange_code_for_token(code: str, client_id: str, client_secret: str, redirect_url: str) -> dict[str, Any]:
    payload = {
        "code": code,
        "client_id": client_id,
        "client_secret": client_secret,
        "redirect_uri": redirect_url,
        "grant_type": "authorization_code",
    }
    async with httpx.AsyncClient(timeout=10) as client:
        resp = await client.post(GOOGLE_TOKEN_URL, data=payload, headers={"Content-Type": "application/x-www-form-urlencoded"})
    if resp.status_code != 200:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="google_oauth_exchange_failed")
    data = resp.json()
    if "access_token" not in data:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="google_oauth_missing_token")
    return data


async def _fetch_google_profile(access_token: str) -> dict[str, Any]:
    headers = {"Authorization": f"Bearer {access_token}"}
    async with httpx.AsyncClient(timeout=10) as client:
        resp = await client.get(GOOGLE_USERINFO_URL, headers=headers)
    if resp.status_code != 200:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="google_oauth_profile_failed")
    data = resp.json()
    if "email" not in data:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="google_oauth_missing_email")
    return data


@router.get("/auth/google/login")
async def google_login(request: Request, response: Response) -> Response:
    ip = request.client.host if request and request.client else "anonymous"
    if request and not increment_ip_bucket(ip, AUTH_WINDOW, AUTH_MAX_CALLS):
        record_429(ip, request.url.path)
        raise HTTPException(status_code=429, detail="rate limit exceeded")
    client_id, _, redirect_url = _google_config()
    state = secrets.token_urlsafe(16)
    next_param = sanitize_next_path(request.query_params.get("next"))
    query = urlencode(
        {
            "client_id": client_id,
            "redirect_uri": redirect_url,
            "response_type": "code",
            "scope": "openid email profile",
            "access_type": "online",
            "include_granted_scopes": "true",
            "prompt": "select_account",
            "state": state,
        }
    )
    redirect = RedirectResponse(url=f"{GOOGLE_AUTH_URL}?{query}", status_code=status.HTTP_307_TEMPORARY_REDIRECT)
    redirect.set_cookie(
        key=OAUTH_STATE_COOKIE,
        value=state,
        httponly=True,
        secure=COOKIE_SECURE,
        samesite=COOKIE_SAMESITE,
        max_age=600,
        path="/auth/google",
    )
    redirect.set_cookie(
        key=OAUTH_NEXT_COOKIE,
        value=next_param,
        httponly=True,
        secure=COOKIE_SECURE,
        samesite=COOKIE_SAMESITE,
        max_age=600,
        path="/auth/google",
    )
    return redirect


@router.get("/auth/google/callback")
async def google_callback(
    request: Request,
    response: Response,
    code: Optional[str] = None,
    state: Optional[str] = None,
    session: Session = Depends(get_session),
):
    ip = request.client.host if request and request.client else "anonymous"
    if request and not increment_ip_bucket(ip, AUTH_WINDOW, AUTH_MAX_CALLS):
        record_429(ip, request.url.path)
        raise HTTPException(status_code=429, detail="rate limit exceeded")

    if not code or not state:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="missing_code_or_state")
    state_cookie = request.cookies.get(OAUTH_STATE_COOKIE)
    if not state_cookie or state_cookie != state:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="invalid_oauth_state")

    client_id, client_secret, redirect_url = _google_config()
    token_data = await _exchange_code_for_token(code, client_id, client_secret, redirect_url)
    profile = await _fetch_google_profile(token_data["access_token"])
    email = profile.get("email", "").strip().lower()
    if not email:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="missing_email")

    user = session.exec(select(User).where(User.email == email)).first()
    audit_action = "login_google"
    if not user:
        random_pwd = secrets.token_urlsafe(12)
        user = User(email=email, password_hash=hash_password(random_pwd))
        session.add(user)
        session.commit()
        session.refresh(user)
        audit_action = "register_google"
    token = create_access_token(user_id=user.id, email=user.email, role=user.role)
    redirect_target = sanitize_next_path(request.cookies.get(OAUTH_NEXT_COOKIE))
    redirect_resp = RedirectResponse(url=build_frontend_redirect(redirect_target), status_code=status.HTTP_302_FOUND)
    set_auth_cookie(redirect_resp, token)
    if ENABLE_CSRF:
        set_csrf_cookie(redirect_resp, generate_csrf_token())
    redirect_resp.delete_cookie(OAUTH_STATE_COOKIE, path="/auth/google")
    redirect_resp.delete_cookie(OAUTH_NEXT_COOKIE, path="/auth/google")
    record_audit(
        audit_action,
        user_id=user.id,
        target_type="user",
        target_id=user.id,
        meta={"email": user.email, "provider": "google"},
    )
    return redirect_resp


@router.post("/auth/register")
async def register_user(body: AuthRequest, response: Response, session: Session = Depends(get_session), request: Any = None):
    ip = request.client.host if request and request.client else "anonymous"
    if request and not increment_ip_bucket(ip, AUTH_WINDOW, AUTH_MAX_CALLS):
        record_429(ip, request.url.path)
        raise HTTPException(status_code=429, detail="rate limit exceeded")
    email = body.email.strip().lower()
    if "@" not in email:
        raise HTTPException(status_code=400, detail="invalid email")
    existing = session.exec(select(User).where(User.email == email)).first()
    if existing:
        raise HTTPException(status_code=400, detail="email already registered")
    if len(body.password or "") < 8:
        raise HTTPException(status_code=400, detail="password too short; minimum 8 characters")
    user = User(email=email, password_hash=hash_password(body.password))
    session.add(user)
    session.commit()
    session.refresh(user)
    token = create_access_token(user_id=user.id, email=user.email, role=user.role)
    set_auth_cookie(response, token)
    if ENABLE_CSRF:
        set_csrf_cookie(response, generate_csrf_token())
    record_audit(
        "register",
        user_id=user.id,
        target_type="user",
        target_id=user.id,
        meta={"email": user.email},
    )
    return serialize_user(user)


@router.post("/auth/login")
async def login_user(body: AuthRequest, response: Response, session: Session = Depends(get_session), request: Any = None):
    ip = request.client.host if request and request.client else "anonymous"
    if request and not increment_ip_bucket(ip, AUTH_WINDOW, AUTH_MAX_CALLS):
        record_429(ip, request.url.path)
        raise HTTPException(status_code=429, detail="rate limit exceeded")
    email = body.email.strip().lower()
    user = session.exec(select(User).where(User.email == email)).first()
    if not user or not verify_password(body.password, user.password_hash):
        raise HTTPException(status_code=401, detail="invalid credentials")
    token = create_access_token(user_id=user.id, email=user.email, role=user.role)
    set_auth_cookie(response, token)
    if ENABLE_CSRF:
        set_csrf_cookie(response, generate_csrf_token())
    record_audit(
        "login",
        user_id=user.id,
        target_type="user",
        target_id=user.id,
        meta={"email": user.email},
    )
    return serialize_user(user)


@router.post("/auth/logout")
async def logout_user(response: Response):
    clear_auth_cookie(response)
    if ENABLE_CSRF:
        clear_csrf_cookie(response)
    return {"ok": True}


@router.get("/me")
async def get_me(current_user: User = Depends(get_current_user)):
    return serialize_user(current_user)


def _user_team_role(session: Session, user_id: str, team_id: str) -> Optional[str]:
    return user_team_role(session, user_id, team_id)


# Alias for main import compatibility
auth_router = router
