import os
from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException, Response
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
