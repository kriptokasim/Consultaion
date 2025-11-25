from fastapi import APIRouter, HTTPException, Request, status
from fastapi.responses import JSONResponse, RedirectResponse
from sqlmodel import Session, select
import uuid

from auth import (
    COOKIE_NAME,
    CSRF_COOKIE_NAME,
    create_access_token,
    decode_access_token,
    hash_password,
    verify_password,
    generate_csrf_token,
)
from routes.auth import sanitize_next_path, OAUTH_STATE_COOKIE, OAUTH_NEXT_COOKIE, _profile_payload, _clean_optional
from routes.common import serialize_user
from models import User
from schemas import UserProfile as UserProfileSchema, UserProfileUpdate, AuthRequest
from database import engine
from config import settings

test_router = APIRouter()

def _require_user_from_cookie(request: Request) -> User:
    token = request.cookies.get(COOKIE_NAME)
    if not token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="unauthenticated")
    payload = decode_access_token(token)
    user_id = payload.get("sub")
    if not user_id:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="unauthenticated")
    with Session(engine) as session:
        user = session.get(User, user_id)
        if not user or not getattr(user, "is_active", True):
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="unauthenticated")
        return user

def _set_auth_cookies(resp: JSONResponse, token: str):
    resp.set_cookie(
        key=COOKIE_NAME,
        value=token,
        httponly=True,
        secure=settings.COOKIE_SECURE,
        samesite=settings.COOKIE_SAMESITE.capitalize(),
        max_age=settings.JWT_TTL_SECONDS,
        path=settings.COOKIE_PATH,
    )
    resp.set_cookie(
        key=CSRF_COOKIE_NAME,
        value=generate_csrf_token(),
        httponly=False,
        secure=settings.COOKIE_SECURE,
        samesite=settings.COOKIE_SAMESITE.capitalize(),
        max_age=settings.JWT_TTL_SECONDS,
        path=settings.COOKIE_PATH,
    )

@test_router.post("/auth/register", status_code=status.HTTP_201_CREATED)
async def test_register(body: AuthRequest):
    with Session(engine) as session:
        email = body.email.strip().lower()
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
    resp = JSONResponse(serialize_user(user), status_code=status.HTTP_201_CREATED)
    _set_auth_cookies(resp, token)
    return resp

@test_router.post("/auth/login")
async def test_login(body: AuthRequest):
    with Session(engine) as session:
        email = body.email.strip().lower()
        user = session.exec(select(User).where(User.email == email)).first()
        if not user or not verify_password(body.password, user.password_hash):
            raise HTTPException(status_code=401, detail="invalid credentials")
    token = create_access_token(user_id=user.id, email=user.email, role=user.role)
    resp = JSONResponse(serialize_user(user), status_code=status.HTTP_200_OK)
    _set_auth_cookies(resp, token)
    return resp

@test_router.post("/auth/logout")
async def test_logout():
    resp = JSONResponse({"ok": True})
    resp.delete_cookie(COOKIE_NAME, path=settings.COOKIE_PATH)
    resp.delete_cookie(CSRF_COOKIE_NAME, path=settings.COOKIE_PATH)
    return resp

@test_router.get("/me")
async def test_me(request: Request):
    user = _require_user_from_cookie(request)
    return serialize_user(user)

@test_router.get("/me/profile", response_model=UserProfileSchema)
async def test_profile(request: Request):
    user = _require_user_from_cookie(request)
    return _profile_payload(user)

@test_router.put("/me/profile", response_model=UserProfileSchema)
async def test_profile_update(body: UserProfileUpdate, request: Request):
    user = _require_user_from_cookie(request)
    with Session(engine) as session:
        db_user = session.get(User, user.id)
        if body.display_name is not None:
            db_user.display_name = _clean_optional(body.display_name)
        if body.avatar_url is not None:
            db_user.avatar_url = _clean_optional(body.avatar_url)
        if body.bio is not None:
            db_user.bio = _clean_optional(body.bio)
        if body.timezone is not None:
            db_user.timezone = _clean_optional(body.timezone)
        session.add(db_user)
        session.commit()
        session.refresh(db_user)
        return _profile_payload(db_user)

@test_router.get("/auth/google/login")
async def test_google_login(next: str = "/dashboard"):
    state = str(uuid.uuid4())
    safe_next = sanitize_next_path(next)
    resp = RedirectResponse(
        url=f"https://accounts.google.com/o/oauth2/v2/auth?state={state}&redirect_uri=/auth/google/callback"
    )
    resp.set_cookie(OAUTH_STATE_COOKIE, state, path="/auth/google")
    resp.set_cookie(OAUTH_NEXT_COOKIE, safe_next, path="/auth/google")
    return resp

@test_router.get("/auth/google/callback")
async def test_google_callback(code: str, state: str, request: Request):
    expected = request.cookies.get(OAUTH_STATE_COOKIE)
    if not expected or expected.strip('\"') != state:
        raise HTTPException(status_code=400, detail="invalid state")
    # generate a user email per callback
    email = f"google-{uuid.uuid4().hex[:6]}@example.com"
    with Session(engine) as session:
        user = session.exec(select(User).where(User.email == email)).first()
        if not user:
            user = User(email=email, password_hash=hash_password("TempPass123!"))
            session.add(user)
            session.commit()
            session.refresh(user)
    token = create_access_token(user_id=user.id, email=user.email, role=user.role)
    resp = RedirectResponse(url=sanitize_next_path(request.cookies.get(OAUTH_NEXT_COOKIE) or "/"))
    resp.set_cookie(OAUTH_STATE_COOKIE, "", path="/auth/google")
    resp.set_cookie(OAUTH_NEXT_COOKIE, "", path="/auth/google")
    _set_auth_cookies(resp, token)
    return resp
