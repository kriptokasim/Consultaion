from database import get_session as base_get_session
from sqlmodel import Session


def get_session() -> Session:
    yield from base_get_session()
