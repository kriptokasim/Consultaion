"""
Patchset 53.0: Debug Routes

Debug endpoints for auth diagnostics. Only available when AUTH_DEBUG=True.
"""

import logging
from typing import Optional

from auth import COOKIE_NAME, get_optional_user
from config import settings
from fastapi import APIRouter, Depends, HTTPException, Request
from models import User

router = APIRouter(tags=["debug"])
logger = logging.getLogger(__name__)


@router.get("/debug/auth")
async def debug_auth(
    request: Request,
    current_user: Optional[User] = Depends(get_optional_user),
):
    """
    Debug endpoint to inspect auth state from API perspective.
    
    Only available when AUTH_DEBUG=True. Never exposes raw cookie values.
    
    In production/staging (not local), only minimal info is returned and
    a sanitized audit event is logged server-side.
    """
    if not settings.AUTH_DEBUG:
        raise HTTPException(status_code=404, detail="Not found")
    
    cookies = request.cookies
    has_auth_cookie = COOKIE_NAME in cookies
    
    # Redact cookie values for security
    cookie_keys = {k: "<present>" if v else "<empty>" for k, v in cookies.items()}
    
    # In production/staging (non-local), return only minimal info and audit server-side
    if not settings.IS_LOCAL_ENV:
        from audit import record_audit
        # Log sanitized audit event
        record_audit(
            "auth_debug_accessed",
            user_id=current_user.id if current_user else None,
            target_type="system",
            meta={
                "request_path": request.url.path,
                "auth_debug_accessed": True,
                "has_auth_cookie": has_auth_cookie,
            },
        )
        return {
            "user": None if current_user is None else {
                "id": current_user.id,
                "email": current_user.email,
                "role": current_user.role,
            },
            "auth_state": "authenticated" if current_user else "anonymous",
            "note": "Debug info available in server logs only",
        }
    
    return {
        "user": None if current_user is None else {
            "id": current_user.id,
            "email": current_user.email,
            "role": current_user.role,
        },
        "cookies_present": cookie_keys,
        "has_auth_cookie": has_auth_cookie,
        "cookie_name": COOKIE_NAME,
        "cookie_secure": settings.COOKIE_SECURE,
        "cookie_samesite": settings.COOKIE_SAMESITE,
        "cookie_domain": settings.COOKIE_DOMAIN,
        "cookie_path": settings.COOKIE_PATH,
        "cors_origins": settings.CORS_ORIGINS,
        "web_app_origin": settings.WEB_APP_ORIGIN,
        "enable_csrf": settings.ENABLE_CSRF,
        "env": settings.ENV,
        "is_local_env": settings.IS_LOCAL_ENV,
    }

@router.get("/sentry-debug")
async def trigger_error():
    """Debug endpoint to test Sentry integration. Fails in production."""
    if not (settings.IS_LOCAL_ENV or settings.AUTH_DEBUG):
        raise HTTPException(status_code=404, detail="Not found")
    division_by_zero = 1 / 0
