import logging
import secrets
import time
from datetime import datetime, timedelta, timezone
from typing import Any, Optional
from urllib.parse import urlencode, urlparse

import httpx
from audit import record_audit
from auth import (
    clear_auth_cookie,
    clear_csrf_cookie,
    create_access_token,
    generate_csrf_token,
    get_cookie_domain,
    get_cookie_name,
    get_cookie_samesite,
    get_cookie_secure,
    get_current_user,
    hash_password,
    is_csrf_enabled,
    set_auth_cookie,
    set_csrf_cookie,
    verify_password,
)
from deps import get_session
from fastapi import APIRouter, Depends, Request, Response, status
from fastapi.responses import RedirectResponse
from models import User, utcnow
from ratelimit import increment_ip_bucket, record_429
from schemas import AuthRequest, UserProfile as UserProfileSchema, UserProfileUpdate
from sqlmodel import Session, select

from config import settings
from routes.common import AUTH_MAX_CALLS, AUTH_WINDOW, serialize_user, user_team_role

router = APIRouter(tags=["auth"])
logger = logging.getLogger(__name__)


def csrf_exempt(func):
    """Mark a route as exempt from CSRF protection."""
    func.csrf_exempt = True
    return func


DUMMY_PASSWORD_HASH = hash_password("dummy-password-for-timing-guard")


GOOGLE_AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
GOOGLE_TOKEN_URL = "https://oauth2.googleapis.com/token"
GOOGLE_USERINFO_URL = "https://www.googleapis.com/oauth2/v3/userinfo"
OAUTH_STATE_COOKIE = "google_oauth_state"
OAUTH_NEXT_COOKIE = "google_oauth_next"
SAFE_NEXT_DEFAULT = "/dashboard"
SAFE_NEXT_PREFIXES = ("/dashboard", "/runs", "/live", "/leaderboard", "/")

def get_web_app_origin() -> str:
    """Runtime accessor for WEB_APP_ORIGIN — never stale."""
    from exceptions import ProviderCircuitOpenError
    origin = settings.WEB_APP_ORIGIN
    if not origin:
        raise ProviderCircuitOpenError(
            message="Web application origin is not configured",
            code="auth.configuration_error",
        )
    return origin.rstrip("/")


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
    return f"{get_web_app_origin()}{cleaned}"


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


def _validate_avatar_url(url: Optional[str]) -> Optional[str]:
    """Validate avatar URL using the shared hardened validator (Patchset 148 D1c).

    Allows http:// only in local/test environments; blocks SSRF-dangerous targets.
    """
    from utils.avatar_validator import validate_avatar_url

    from config import settings

    is_local = getattr(settings, "IS_LOCAL_ENV", False)
    try:
        return validate_avatar_url(url, allow_http=is_local)
    except ValueError as exc:
        raise ValidationError(
            message=str(exc),
            code="validation.invalid_avatar_url",
        ) from exc


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
        current_user.avatar_url = _validate_avatar_url(body.avatar_url)
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
    # Reject unverified Google emails
    if data.get("email_verified") is not True:
        raise AuthError(
            message="Google email is not verified. Please verify your email with Google.",
            code="auth.google_email_not_verified",
            status_code=400,
        )
    return data


@router.get("/auth/google/login")
async def google_login(request: Request, response: Response) -> Response:
    ip = request.client.host if request and request.client else "anonymous"
    allowed, retry_after = increment_ip_bucket(ip, AUTH_WINDOW, AUTH_MAX_CALLS) if request else (True, None)
    if not allowed:
        record_429(ip, request.url.path)
        raise RateLimitError(message="Rate limit exceeded", code="rate_limit.exceeded", retry_after_seconds=retry_after)
    client_id, _, redirect_url = _google_config()
    # Use robust server-side state store
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
    
    # Consume state from store
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
        audit_action = "register_google"
    
    # Stage audit before commit so it persists atomically
    record_audit(
        audit_action,
        user_id=user.id,
        target_type="user",
        target_id=user.id,
        ip_address=ip,
        meta={"email": user.email, "provider": "google"},
        session=session,
    )
    session.commit()
    session.refresh(user)

    # Disabled accounts must never receive a fresh token (GET callback)
    if not user.is_active:
        raise AuthError(
            message="Account disabled",
            code="auth.account_disabled",
            status_code=403,
        )

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
    
    # Set auth as HttpOnly cookie only — never expose JWT in URL
    target_url = build_frontend_redirect(redirect_target)
    
    redirect_resp = RedirectResponse(url=target_url, status_code=status.HTTP_302_FOUND)
    set_auth_cookie(redirect_resp, token)
    
    # [AUTH_DEBUG] Patchset 53.0: Log after cookie set
    if settings.AUTH_DEBUG:
        logger.info(
            "[AUTH_DEBUG] Auth cookie set for Google login",
            extra={
                "user_id": user.id,
                "cookie_name": get_cookie_name(),
                "cookie_secure": get_cookie_secure(),
                "cookie_samesite": get_cookie_samesite(),
                "cookie_domain": get_cookie_domain() or "<not_set>",
                "redirect_target": redirect_target,
            },
        )
    
    if is_csrf_enabled():
        set_csrf_cookie(redirect_resp, generate_csrf_token())
    
    # State cookie cleanup no longer needed as we didn't set it.
    
    return redirect_resp


from pydantic import BaseModel


class GoogleCallbackRequest(BaseModel):
    code: str
    state: str


@csrf_exempt
@router.post("/auth/google/callback")
async def google_callback_post(
    body: GoogleCallbackRequest,
    request: Request,
    response: Response,
    session: Session = Depends(get_session),
):
    ip = request.client.host if request and request.client else "anonymous"
    allowed, retry_after = increment_ip_bucket(ip, AUTH_WINDOW, AUTH_MAX_CALLS) if request else (True, None)
    if not allowed:
        record_429(ip, request.url.path)
        raise RateLimitError(message="Rate limit exceeded", code="rate_limit.exceeded", retry_after_seconds=retry_after)

    code = body.code
    state = body.state

    # Consume state from store (if it was initiated by the backend login endpoint).
    # Since the Next.js frontend generates its own state nonce on the client-side and validates
    # it in the Next.js callback route, it won't be in the backend's state_store.
    # Therefore, if state_store.consume_state(state) is None, we log a warning/info and proceed.
    from security.state_store import state_store
    state_meta = state_store.consume_state(state)
    
    if not state_meta:
        internal_secret = request.headers.get("x-internal-secret")
        if not internal_secret or not settings.INTERNAL_SECRET or not secrets.compare_digest(internal_secret, settings.INTERNAL_SECRET):
            if not settings.INTERNAL_SECRET:
                logger.error(
                    "Google OAuth failed: INTERNAL_SECRET is not set in backend environment. "
                    "Set INTERNAL_SECRET in Render env vars and match it in Vercel env vars. IP=%s", ip
                )
                raise ValidationError(
                    message="Google sign-in misconfigured: INTERNAL_SECRET is not set on the server. "
                            "An admin must set INTERNAL_SECRET in both backend and frontend environments.",
                    code="auth.configuration_error",
                    status_code=503,
                )
            elif not internal_secret:
                logger.warning(
                    "Google OAuth failed: frontend did not send x-internal-secret header. "
                    "Ensure INTERNAL_SECRET is set in the Vercel/Next.js environment. IP=%s", ip
                )
                raise ValidationError(
                    message="Google sign-in failed: frontend is not sending the required internal secret. "
                            "Ensure INTERNAL_SECRET is set in the frontend (Vercel) environment.",
                    code="auth.configuration_error",
                    status_code=503,
                )
            else:
                logger.warning(
                    "Google OAuth failed: x-internal-secret mismatch. "
                    "Frontend and backend INTERNAL_SECRET values do not match. IP=%s", ip
                )
                raise ValidationError(
                    message="Google sign-in failed: internal secret mismatch between frontend and backend.",
                    code="auth.configuration_error",
                    status_code=503,
                )

        # H-API-9: Even with valid internal secret, verify the request origin
        # to prevent abuse if the secret is leaked.
        from urllib.parse import urlsplit

        origin = request.headers.get("origin") or ""
        referer = request.headers.get("referer") or ""
        expected_origin = settings.WEB_APP_ORIGIN or ""

        def _same_origin(value: str, expected: str) -> bool:
            try:
                parsed = urlsplit(value)
                wanted = urlsplit(expected)
                return bool(
                    parsed.scheme
                    and parsed.scheme.lower() == wanted.scheme.lower()
                    and parsed.hostname == wanted.hostname
                    and parsed.port == wanted.port
                )
            except (TypeError, ValueError):
                return False

        if expected_origin and not _same_origin(origin, expected_origin) and not _same_origin(referer, expected_origin):
            logger.warning(
                "Google OAuth internal-secret bypass rejected: origin/referer mismatch. "
                "origin=%s referer=%s expected=%s IP=%s",
                origin[:50], referer[:50], expected_origin, ip,
            )
            raise ValidationError(
                message="Google sign-in rejected: request origin does not match expected frontend.",
                code="auth.origin_mismatch",
            )

        logger.info(
            f"Google OAuth state {state[:8]}... not found in backend state_store. "
            f"Proceeding as it was validated by the frontend server (trusted). IP={ip}"
        )
    
    client_id, client_secret, redirect_url = _google_config()
    try:
        token_data = await _exchange_code_for_token(code, client_id, client_secret, redirect_url)
        profile = await _fetch_google_profile(token_data["access_token"])
    except AuthError:
        raise
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
        audit_action = "register_google"
    
    record_audit(
        audit_action,
        user_id=user.id,
        target_type="user",
        target_id=user.id,
        ip_address=ip,
        meta={"email": user.email, "provider": "google"},
        session=session,
    )
    session.commit()
    session.refresh(user)

    # Disabled accounts must never receive a fresh token (POST callback)
    if not user.is_active:
        raise AuthError(
            message="Account disabled",
            code="auth.account_disabled",
            status_code=403,
        )

    if settings.AUTH_DEBUG:
        logger.info(
            "[AUTH_DEBUG] Google login (POST) success, creating token",
            extra={
                "user_id": user.id,
                "email": user.email,
                "provider": "google",
                "remote_addr": ip,
            },
        )
    
    token = create_access_token(user_id=user.id, email=user.email, role=user.role)
    # Vercel server-to-server callback owns the browser cookie.
    # Return the JWT in JSON so the Next.js route can set HttpOnly consultaion_token.
    # Do not Set-Cookie here — it would land on the Vercel server fetch, not the browser.
    return {
        "access_token": token,
        "token_type": "bearer",
        "expires_in": settings.JWT_TTL_SECONDS,
        "user": {
            "id": user.id,
            "email": user.email,
            "role": user.role,
        },
    }


@csrf_exempt
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
    token = create_access_token(user_id=user.id, email=user.email, role=user.role)
    set_auth_cookie(response, token)
    if is_csrf_enabled():
        set_csrf_cookie(response, generate_csrf_token())
    record_audit(
        "register",
        user_id=user.id,
        target_type="user",
        target_id=user.id,
        ip_address=ip,
        meta={"email": user.email},
        session=session,
    )
    session.commit()
    return serialize_user(user)


@csrf_exempt
@router.post("/auth/login")
async def login_user(body: AuthRequest, request: Request, response: Response, session: Session = Depends(get_session)):
    # Set correlation context for this request
    from correlation import create_child_context, get_correlation_context
    ctx = get_correlation_context()
    if ctx:
        ctx = create_child_context(user_id=None)

    ip = request.client.host if request and request.client else "anonymous"
    allowed, retry_after = increment_ip_bucket(ip, AUTH_WINDOW, AUTH_MAX_CALLS) if request else (True, None)
    if not allowed:
        record_429(ip, request.url.path)
        raise RateLimitError(message="Rate limit exceeded", code="rate_limit.exceeded", retry_after_seconds=retry_after)
    email = body.email.strip().lower()
    user = session.exec(select(User).where(User.email == email)).first()

    # FH125 C-5: Account lockout check
    if user and user.locked_until:
        if datetime.now(timezone.utc) < user.locked_until:
            raise AuthError(
                message="Account temporarily locked due to too many failed attempts",
                code="auth.account_locked",
                status_code=429,
            )
        # Lock expired — reset
        user.failed_login_attempts = 0
        user.locked_until = None
        session.add(user)
        session.commit()

    # Patchset 63.2: Constant-time verification to prevent timing side-channels
    password_hash = user.password_hash if user else DUMMY_PASSWORD_HASH
    password_valid = verify_password(body.password, password_hash)

    if not user or not password_valid:
        # FH125 C-5: Progressive lockout on failed login
        if user:
            user.failed_login_attempts = (user.failed_login_attempts or 0) + 1
            user.last_failed_login_at = datetime.now(timezone.utc)
            attempts = user.failed_login_attempts
            if attempts >= 20:
                user.locked_until = datetime.now(timezone.utc) + timedelta(hours=24)
            elif attempts >= 10:
                user.locked_until = datetime.now(timezone.utc) + timedelta(hours=1)
            elif attempts >= 5:
                user.locked_until = datetime.now(timezone.utc) + timedelta(minutes=15)
            session.add(user)
            session.commit()
        raise AuthError(message="Invalid credentials", code="auth.invalid_credentials")

    # Disabled accounts must never receive a fresh token
    if not user.is_active:
        raise AuthError(
            message="Account disabled",
            code="auth.account_disabled",
            status_code=403,
        )

    # Successful login — reset lockout state
    if user.failed_login_attempts or user.locked_until:
        user.failed_login_attempts = 0
        user.locked_until = None
        user.last_failed_login_at = None
        session.add(user)
        session.commit()
    
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
                "cookie_name": get_cookie_name(),
                "cookie_secure": get_cookie_secure(),
                "cookie_samesite": get_cookie_samesite(),
                "cookie_domain": get_cookie_domain() or "<not_set>",
            },
        )
    
    if is_csrf_enabled():
        set_csrf_cookie(response, generate_csrf_token())
    # Login is read-only — use standalone audit session
    record_audit(
        "login",
        user_id=user.id,
        target_type="user",
        target_id=user.id,
        ip_address=ip,
        meta={"email": user.email},
    )
    return serialize_user(user)


@router.post("/auth/logout")
async def logout_user(response: Response):
    clear_auth_cookie(response)
    if is_csrf_enabled():
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
    response: Response,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    """
    Soft-delete user account and anonymize their data (FH125 H-1).

    Uses the shared AccountErasureService for consistent behavior
    with scheduled GDPR deletion.
    """
    from services.account_erasure import erase_user_account

    user_id = current_user.id

    result = erase_user_account(session, current_user, reason="user_request")

    record_audit(
        "account_deleted",
        user_id=user_id,
        target_type="user",
        target_id=user_id,
        meta={
            "debates_anonymized": result.debates_anonymized,
            "api_keys_deleted": result.api_keys_deleted,
            "provider_keys_deleted": result.provider_keys_deleted,
        },
        session=session,
    )

    session.commit()

    logger.info("User account deleted: %s, debates anonymized: %d", user_id, result.debates_anonymized)

    # Clear auth cookies
    clear_auth_cookie(response)
    clear_csrf_cookie(response)

    return {
        "status": "ok",
        "message": "Your account has been deleted and your data has been anonymized.",
    }




def _user_team_role(session: Session, user_id: str, team_id: str) -> Optional[str]:
    return user_team_role(session, user_id, team_id)


# Alias for main import compatibility
auth_router = router
