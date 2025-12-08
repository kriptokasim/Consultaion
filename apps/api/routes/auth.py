import logging
import secrets
from typing import Any, Optional
from urllib.parse import urlencode, urlparse

import httpx
from audit import record_audit
from auth import (
    COOKIE_DOMAIN,
    COOKIE_NAME,
    COOKIE_SAMESITE,
    COOKIE_SECURE,
    ENABLE_CSRF,
    clear_auth_cookie,
    clear_csrf_cookie,
    create_access_token,
    generate_csrf_token,
    get_current_user,
    hash_password,
    set_auth_cookie,
    set_csrf_cookie,
    verify_password,
)
from config import settings
from deps import get_session
from fastapi import APIRouter, Depends, Request, Response, status
from fastapi.responses import RedirectResponse
from models import User, utcnow
from ratelimit import increment_ip_bucket, record_429
from schemas import AuthRequest, UserProfile as UserProfileSchema, UserProfileUpdate
from sqlmodel import Session, select

from routes.common import AUTH_MAX_CALLS, AUTH_WINDOW, serialize_user, user_team_role

router = APIRouter(tags=["auth"])
logger = logging.getLogger(__name__)


GOOGLE_AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"


GOOGLE_AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
GOOGLE_TOKEN_URL = "https://oauth2.googleapis.com/token"
GOOGLE_USERINFO_URL = "https://www.googleapis.com/oauth2/v3/userinfo"
OAUTH_STATE_COOKIE = "google_oauth_state"
OAUTH_NEXT_COOKIE = "google_oauth_next"
SAFE_NEXT_DEFAULT = "/dashboard"
SAFE_NEXT_PREFIXES = ("/dashboard", "/runs", "/live", "/leaderboard", "/")

WEB_APP_ORIGIN = settings.WEB_APP_ORIGIN


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


def _profile_payload(user: User, debate_count: int = 0) -> UserProfileSchema:
    created = user.created_at.isoformat() if getattr(user, "created_at", None) else utcnow().isoformat()
    return UserProfileSchema(
        id=user.id,
        email=user.email,
        display_name=user.display_name,
        avatar_url=user.avatar_url,
        bio=user.bio,
        timezone=user.timezone,
        is_admin=bool(getattr(user, "is_admin", False) or user.role == "admin"),
        created_at=created,
        email_summaries_enabled=getattr(user, "email_summaries_enabled", False),
        debate_count=debate_count,
    )


def _clean_optional(value: Optional[str]) -> Optional[str]:
    if value is None:
        return None
    trimmed = value.strip()
    return trimmed or None


from exceptions import AuthError, ProviderCircuitOpenError, RateLimitError, ValidationError
from models import Debate
from sqlalchemy import func


def _google_config() -> tuple[str, str, str]:
    client_id = settings.GOOGLE_CLIENT_ID
    client_secret = settings.GOOGLE_CLIENT_SECRET
    redirect_url = settings.GOOGLE_REDIRECT_URL
    if not client_id or not client_secret or not redirect_url:
        raise ProviderCircuitOpenError(message="Google auth not configured", code="auth.google_not_configured")
    return client_id, client_secret, redirect_url


# ... (skipping unchanged parts)

@router.get("/me/profile", response_model=UserProfileSchema)
async def get_my_profile(
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
):
    count = session.exec(select(func.count()).select_from(Debate).where(Debate.user_id == current_user.id)).one()
    return _profile_payload(current_user, count)


@router.put("/me/profile", response_model=UserProfileSchema)
async def update_my_profile(
    body: UserProfileUpdate,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    updated = False

    if body.display_name is not None:
        current_user.display_name = _clean_optional(body.display_name)
        updated = True
    if body.avatar_url is not None:
        current_user.avatar_url = _clean_optional(body.avatar_url)
        updated = True
    if body.bio is not None:
        current_user.bio = _clean_optional(body.bio)
        updated = True
    if body.timezone is not None:
        current_user.timezone = _clean_optional(body.timezone)
        updated = True
    if body.email_summaries_enabled is not None:
        current_user.email_summaries_enabled = body.email_summaries_enabled
        updated = True

    if updated:
        session.add(current_user)
        session.commit()
        session.refresh(current_user)

    # For update, we can fetch count again or just pass 0 if we don't want extra query, but let's be correct
    count = session.exec(select(func.count()).select_from(Debate).where(Debate.user_id == current_user.id)).one()
    return _profile_payload(current_user, count)


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
        raise AuthError(message="Google OAuth exchange failed", code="auth.google_exchange_failed", status_code=400)
    data = resp.json()
    if "access_token" not in data:
        raise AuthError(message="Google OAuth missing token", code="auth.google_missing_token", status_code=400)
    return data


async def _fetch_google_profile(access_token: str) -> dict[str, Any]:
    headers = {"Authorization": f"Bearer {access_token}"}
    async with httpx.AsyncClient(timeout=10) as client:
        resp = await client.get(GOOGLE_USERINFO_URL, headers=headers)
    if resp.status_code != 200:
        raise AuthError(message="Google OAuth profile fetch failed", code="auth.google_profile_failed", status_code=400)
    data = resp.json()
    if "email" not in data:
        raise AuthError(message="Google OAuth missing email", code="auth.google_missing_email", status_code=400)
    return data


@router.get("/auth/google/login")
async def google_login(request: Request, response: Response) -> Response:
    ip = request.client.host if request and request.client else "anonymous"
    if request and not increment_ip_bucket(ip, AUTH_WINDOW, AUTH_MAX_CALLS):
        record_429(ip, request.url.path)
        raise RateLimitError(message="Rate limit exceeded", code="rate_limit.exceeded")
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
        raise RateLimitError(message="Rate limit exceeded", code="rate_limit.exceeded")

    if not code or not state:
        raise ValidationError(message="Missing code or state", code="auth.missing_params")
    state_cookie = request.cookies.get(OAUTH_STATE_COOKIE)
    if not state_cookie or state_cookie != state:
        raise ValidationError(message="Invalid OAuth state", code="auth.invalid_state")

    client_id, client_secret, redirect_url = _google_config()
    token_data = await _exchange_code_for_token(code, client_id, client_secret, redirect_url)
    profile = await _fetch_google_profile(token_data["access_token"])
    email = profile.get("email", "").strip().lower()
    if not email:
        raise ValidationError(message="Missing email from Google profile", code="auth.missing_email")

    user = session.exec(select(User).where(User.email == email)).first()
    audit_action = "login_google"
    if not user:
        random_pwd = secrets.token_urlsafe(12)
        user = User(email=email, password_hash=hash_password(random_pwd))
        session.add(user)
        session.commit()
        session.refresh(user)
        audit_action = "register_google"
    
    # [AUTH_DEBUG] Patchset 53.0: Log before token creation
    if settings.AUTH_DEBUG:
        logger.info(
            "[AUTH_DEBUG] Google login success, creating token",
            extra={
                "user_id": user.id,
                "email": user.email,
                "provider": "google",
                "remote_addr": request.client.host if request.client else None,
            },
        )
    
    token = create_access_token(user_id=user.id, email=user.email, role=user.role)
    redirect_target = sanitize_next_path(request.cookies.get(OAUTH_NEXT_COOKIE))
    redirect_resp = RedirectResponse(url=build_frontend_redirect(redirect_target), status_code=status.HTTP_302_FOUND)
    set_auth_cookie(redirect_resp, token)
    
    # [AUTH_DEBUG] Patchset 53.0: Log after cookie set
    if settings.AUTH_DEBUG:
        logger.info(
            "[AUTH_DEBUG] Auth cookie set for Google login",
            extra={
                "user_id": user.id,
                "cookie_name": COOKIE_NAME,
                "cookie_secure": COOKIE_SECURE,
                "cookie_samesite": COOKIE_SAMESITE,
                "cookie_domain": COOKIE_DOMAIN or "<not_set>",
                "redirect_target": redirect_target,
            },
        )
    
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
        session=session,
    )
    return redirect_resp


@router.post("/auth/register", status_code=status.HTTP_201_CREATED)
async def register_user(body: AuthRequest, response: Response, session: Session = Depends(get_session), request: Any = None):
    ip = request.client.host if request and request.client else "anonymous"
    if request and not increment_ip_bucket(ip, AUTH_WINDOW, AUTH_MAX_CALLS):
        record_429(ip, request.url.path)
        raise RateLimitError(message="Rate limit exceeded", code="rate_limit.exceeded")
    email = body.email.strip().lower()
    if "@" not in email:
        raise ValidationError(message="Invalid email address", code="auth.invalid_email")
    existing = session.exec(select(User).where(User.email == email)).first()
    if existing:
        raise ValidationError(message="Email already registered", code="auth.email_exists")
    if len(body.password or "") < 8:
        raise ValidationError(message="Password too short; minimum 8 characters", code="auth.password_too_short")
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
        session=session,
    )
    return serialize_user(user)


@router.post("/auth/login")
async def login_user(body: AuthRequest, response: Response, session: Session = Depends(get_session), request: Any = None):
    ip = request.client.host if request and request.client else "anonymous"
    if request and not increment_ip_bucket(ip, AUTH_WINDOW, AUTH_MAX_CALLS):
        record_429(ip, request.url.path)
        raise RateLimitError(message="Rate limit exceeded", code="rate_limit.exceeded")
    email = body.email.strip().lower()
    user = session.exec(select(User).where(User.email == email)).first()
    if not user or not verify_password(body.password, user.password_hash):
        raise AuthError(message="Invalid credentials", code="auth.invalid_credentials")
    
    # [AUTH_DEBUG] Patchset 53.0: Log before token creation
    if settings.AUTH_DEBUG:
        logger.info(
            "[AUTH_DEBUG] Email login success, creating token",
            extra={
                "user_id": user.id,
                "email": user.email,
                "provider": "password",
                "remote_addr": request.client.host if request and request.client else None,
            },
        )
    
    token = create_access_token(user_id=user.id, email=user.email, role=user.role)
    set_auth_cookie(response, token)
    
    # [AUTH_DEBUG] Patchset 53.0: Log after cookie set
    if settings.AUTH_DEBUG:
        logger.info(
            "[AUTH_DEBUG] Auth cookie set for email login",
            extra={
                "user_id": user.id,
                "cookie_name": COOKIE_NAME,
                "cookie_secure": COOKIE_SECURE,
                "cookie_samesite": COOKIE_SAMESITE,
                "cookie_domain": COOKIE_DOMAIN or "<not_set>",
            },
        )
    
    if ENABLE_CSRF:
        set_csrf_cookie(response, generate_csrf_token())
    record_audit(
        "login",
        user_id=user.id,
        target_type="user",
        target_id=user.id,
        meta={"email": user.email},
        session=session,
    )
    return serialize_user(user)


@router.post("/auth/logout")
async def logout_user(response: Response):
    clear_auth_cookie(response)
    if ENABLE_CSRF:
        clear_csrf_cookie(response)
    return {"ok": True}


@router.get("/me")
async def get_me(
    request: Request,
    current_user: User = Depends(get_current_user),
):
    # [AUTH_DEBUG] Patchset 53.0: Log successful /me call
    if settings.AUTH_DEBUG:
        logger.info(
            "[AUTH_DEBUG] /me success",
            extra={"user_id": current_user.id, "email": current_user.email},
        )
    
    return serialize_user(current_user)





def _user_team_role(session: Session, user_id: str, team_id: str) -> Optional[str]:
    return user_team_role(session, user_id, team_id)


# Alias for main import compatibility
auth_router = router
