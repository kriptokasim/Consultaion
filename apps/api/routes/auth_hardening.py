from __future__ import annotations

from typing import Optional

from auth import decode_access_token, get_cookie_name
from deps import get_session
from exceptions import AuthError
from fastapi import APIRouter, Depends, Request, Response
from models import User
from schemas import AuthRequest
from sqlmodel import Session, select

from routes.auth import (
    GoogleCallbackRequest,
    csrf_exempt,
    google_callback as _legacy_google_callback,
    google_callback_post as _legacy_google_callback_post,
    login_user as _legacy_login_user,
)

router = APIRouter(tags=["auth"])


def _reject_if_inactive(user: User | None) -> None:
    if user is not None and not user.is_active:
        raise AuthError(
            message="Account disabled",
            code="auth.account_disabled",
            status_code=403,
        )


def _verified_user_from_access_token(session: Session, token: str | None) -> User:
    if not token:
        raise AuthError(
            message="Authentication response could not be verified",
            code="auth.callback_verification_failed",
            status_code=500,
        )
    try:
        payload = decode_access_token(token)
    except Exception as exc:
        raise AuthError(
            message="Authentication response could not be verified",
            code="auth.callback_verification_failed",
            status_code=500,
        ) from exc
    user_id = payload.get("sub")
    user = session.get(User, user_id) if user_id else None
    if user is None:
        raise AuthError(
            message="Authentication response could not be verified",
            code="auth.callback_verification_failed",
            status_code=500,
        )
    _reject_if_inactive(user)
    return user


@router.post("/auth/login")
@csrf_exempt
async def login_user_hardened(
    body: AuthRequest,
    request: Request,
    response: Response,
    session: Session = Depends(get_session),
):
    email = body.email.strip().lower()
    _reject_if_inactive(session.exec(select(User).where(User.email == email)).first())
    return await _legacy_login_user(body=body, request=request, response=response, session=session)


@router.get("/auth/google/callback")
async def google_callback_hardened(
    request: Request,
    response: Response,
    code: Optional[str] = None,
    state: Optional[str] = None,
    session: Session = Depends(get_session),
):
    result = await _legacy_google_callback(
        request=request,
        response=response,
        code=code,
        state=state,
        session=session,
    )
    # The legacy handler creates the cookie on its RedirectResponse. Validate
    # the resolved principal before that response ever leaves this boundary.
    cookie_name = get_cookie_name()
    token = None
    prefix = f"{cookie_name}="
    for header_value in result.headers.getlist("set-cookie"):
        if prefix in header_value:
            token = header_value.split(prefix, 1)[1].split(";", 1)[0]
            break
    _verified_user_from_access_token(session, token)
    return result


@router.post("/auth/google/callback")
@csrf_exempt
async def google_callback_post_hardened(
    body: GoogleCallbackRequest,
    request: Request,
    response: Response,
    session: Session = Depends(get_session),
):
    result = await _legacy_google_callback_post(
        body=body,
        request=request,
        response=response,
        session=session,
    )
    token = result.get("access_token") if isinstance(result, dict) else None
    _verified_user_from_access_token(session, token)
    return result
