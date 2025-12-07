"""
Patchset 53.0: Debug Routes

Debug endpoints for auth diagnostics. Only available when AUTH_DEBUG=True.
"""

import logging
from typing import Optional

from auth import COOKIE_NAME, get_optional_user
from config import settings
from deps import get_session
from fastapi import APIRouter, Depends, HTTPException, Request
from models import User
from sqlmodel import Session

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
    
    Returns:
        - user: Current authenticated user (if any)
        - cookies_present: List of cookie names (values redacted)
        - has_auth_cookie: Whether auth cookie is present
        - cookie_name: Expected auth cookie name
        - cookie_*: Cookie configuration values
        - cors_origins: Configured CORS origins
        - web_app_origin: Expected frontend origin
        - enable_csrf: Whether CSRF is enabled
    """
    if not settings.AUTH_DEBUG:
        raise HTTPException(status_code=404, detail="Not found")
    
    cookies = request.cookies
    has_auth_cookie = COOKIE_NAME in cookies
    
    # Redact cookie values for security
    cookie_keys = {k: "<present>" if v else "<empty>" for k, v in cookies.items()}
    
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
