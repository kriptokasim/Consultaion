import logging
import secrets
from typing import Any, Optional
from urllib.parse import urlencode, urlparse, parse_qsl, urlunparse
import time

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


DUMMY_PASSWORD_HASH = hash_password("dummy-password-for-timing-guard")


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
        analytics_opt_out=getattr(user, "analytics_opt_out", False),
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
    allowed, retry_after = increment_ip_bucket(ip, AUTH_WINDOW, AUTH_MAX_CALLS) if request else (True, None)
    if not allowed:
        record_429(ip, request.url.path)
        raise RateLimitError(message="Rate limit exceeded", code="rate_limit.exceeded", retry_after_seconds=retry_after)
    client_id, _, redirect_url = _google_config()
    # Patchset 105: Use robust server-side state store
    from security.state_store import state_store
    
    next_param = request.query_params.get("next", "/dashboard")
    state_meta = {
        "next": next_param,
        "created_at": time.time(),
        "ip": ip,
    }
    state = state_store.create_state(state_meta, ttl=600)
    
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
    # No cookies needed for state!
    return RedirectResponse(url=f"{GOOGLE_AUTH_URL}?{query}", status_code=status.HTTP_307_TEMPORARY_REDIRECT)


@router.get("/auth/google/callback")
async def google_callback(
    request: Request,
    response: Response,
    code: Optional[str] = None,
    state: Optional[str] = None,
    session: Session = Depends(get_session),
):
    ip = request.client.host if request and request.client else "anonymous"
    allowed, retry_after = increment_ip_bucket(ip, AUTH_WINDOW, AUTH_MAX_CALLS) if request else (True, None)
    if not allowed:
        record_429(ip, request.url.path)
        raise RateLimitError(message="Rate limit exceeded", code="rate_limit.exceeded", retry_after_seconds=retry_after)

    if not code or not state:
        raise ValidationError(message="Missing code or state", code="auth.missing_params")
    
    # Patchset 105: Consume state from store
    from security.state_store import state_store
    state_meta = state_store.consume_state(state)
    
    if not state_meta:
        logger.warning(f"OAuth invalid state: {state[:8]}... IP={ip}")
        raise ValidationError(message="Invalid OAuth state (expired or mismatch)", code="auth.invalid_state")
        
    # Optional: Validate IP binding? strict binding can be tricky with mobile/proxies, let's skip strict IP check for now 
    # unless extreme security required.
    
    next_param = state_meta.get("next")

    client_id, client_secret, redirect_url = _google_config()
    try:
        token_data = await _exchange_code_for_token(code, client_id, client_secret, redirect_url)
        profile = await _fetch_google_profile(token_data["access_token"])
    except AuthError:
        raise  # re-raise our own errors as-is
    except Exception as exc:
        logger.warning(
            "Google OAuth network error",
            extra={"error": str(exc), "ip": ip},
            exc_info=True,
        )
        raise AuthError(
            message="Google authentication temporarily unavailable",
            code="auth.google_network_error",
            status_code=502,
        ) from exc
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
    redirect_target = sanitize_next_path(next_param)
    
    # Append token to redirect URL for fallback auth
    target_url = build_frontend_redirect(redirect_target)
    parsed_url = urlparse(target_url)
    query_params = dict(parse_qsl(parsed_url.query))
    query_params["token"] = token
    new_query = urlencode(query_params)
    final_url = urlunparse(parsed_url._replace(query=new_query))
    
    redirect_resp = RedirectResponse(url=final_url, status_code=status.HTTP_302_FOUND)
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
    
    # State cookie cleanup no longer needed as we didn't set it.
    
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
async def register_user(body: AuthRequest, request: Request, response: Response, session: Session = Depends(get_session)):
    ip = request.client.host if request and request.client else "anonymous"
    allowed, retry_after = increment_ip_bucket(ip, AUTH_WINDOW, AUTH_MAX_CALLS) if request else (True, None)
    if not allowed:
        record_429(ip, request.url.path)
        raise RateLimitError(message="Rate limit exceeded", code="rate_limit.exceeded", retry_after_seconds=retry_after)
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
async def login_user(body: AuthRequest, request: Request, response: Response, session: Session = Depends(get_session)):
    ip = request.client.host if request and request.client else "anonymous"
    allowed, retry_after = increment_ip_bucket(ip, AUTH_WINDOW, AUTH_MAX_CALLS) if request else (True, None)
    if not allowed:
        record_429(ip, request.url.path)
        raise RateLimitError(message="Rate limit exceeded", code="rate_limit.exceeded", retry_after_seconds=retry_after)
    email = body.email.strip().lower()
    user = session.exec(select(User).where(User.email == email)).first()
    
    # Patchset 63.2: Constant-time verification to prevent timing side-channels
    # Always hash/verify a password even if user is not found.
    # We use a module-level dummy hash (computed once) for the "user not found" case.
    # Note: DUMMY_PASSWORD_HASH should be defined at module level.
    password_hash = user.password_hash if user else DUMMY_PASSWORD_HASH
    password_valid = verify_password(body.password, password_hash)

    if not user or not password_valid:
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


# Patchset 58.0: Privacy Settings
from pydantic import BaseModel as PydanticBaseModel


class PrivacySettingsRequest(PydanticBaseModel):
    analytics_opt_out: bool


@router.post("/me/privacy")
async def update_privacy_settings(
    body: PrivacySettingsRequest,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    """
    Update user privacy preferences (analytics opt-out).
    """
    current_user.analytics_opt_out = body.analytics_opt_out
    session.add(current_user)
    session.commit()
    session.refresh(current_user)
    
    record_audit(
        "privacy_settings_update",
        user_id=current_user.id,
        target_type="user",
        target_id=current_user.id,
        meta={"analytics_opt_out": current_user.analytics_opt_out},
        session=session,
    )
    
    return {
        "analytics_opt_out": current_user.analytics_opt_out,
        "message": "Privacy settings updated",
    }


@router.post("/me/delete-account")
async def delete_my_account(
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    """
    Soft-delete user account and anonymize their data.
    
    - Sets deleted_at and is_active=False
    - Anonymizes debate content
    - User can no longer log in or create debates
    
    For production: consider making this a background job.
    """
    from models import Debate, utcnow
    
    # Mark account as deleted
    current_user.deleted_at = utcnow()
    current_user.is_active = False
    session.add(current_user)
    
    # Anonymize user's debates (remove PII but keep metadata)
    user_debates = session.exec(
        select(Debate).where(Debate.user_id == current_user.id)
    ).all()
    
    anonymized_count = 0
    for debate in user_debates:
        if debate.prompt != "[DELETED]":
            debate.prompt = "[DELETED]"
            if hasattr(debate, "messages") and debate.messages:
                debate.messages = None
            anonymized_count += 1
    
    session.commit()
    
    record_audit(
        "account_deleted",
        user_id=current_user.id,
        target_type="user",
        target_id=current_user.id,
        meta={"debates_anonymized": anonymized_count},
        session=session,
    )
    
    logger.info(f"User account deleted: {current_user.id}, debates anonymized: {anonymized_count}")
    
    return {
        "status": "ok",
        "message": "Your account has been deleted and your data has been anonymized.",
    }




def _user_team_role(session: Session, user_id: str, team_id: str) -> Optional[str]:
    return user_team_role(session, user_id, team_id)


# Alias for main import compatibility
auth_router = router
