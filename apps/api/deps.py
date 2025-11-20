from sqlmodel import Session

from database import get_session as base_get_session


def get_session() -> Session:
    yield from base_get_session()
