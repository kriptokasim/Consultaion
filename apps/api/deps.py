from typing import Callable, Optional

from fastapi import Depends, HTTPException, Request, status
from sqlmodel import Session, select

from auth import COOKIE_NAME, decode_access_token
from database import get_session as base_get_session
from models import User


def get_session() -> Session:
    yield from base_get_session()


def _resolve_user_from_token(token: Optional[str], session: Session) -> Optional[User]:
    if not token:
        return None
    try:
        payload = decode_access_token(token)
    except Exception:
        return None
    user_id = payload.get("sub")
    if not user_id:
        return None
    user = session.get(User, user_id)
    return user


def get_optional_user(
    request: Request,
    session: Session = Depends(get_session),
) -> Optional[User]:
    token = request.cookies.get(COOKIE_NAME)
    return _resolve_user_from_token(token, session)


def get_current_user(
    request: Request,
    session: Session = Depends(get_session),
) -> User:
    user = get_optional_user(request=request, session=session)
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="authentication required")
    return user


def require_admin(current_user: User = Depends(get_current_user)) -> User:
    if current_user.role != "admin":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="admin only")
    return current_user
