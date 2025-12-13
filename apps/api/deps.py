from database import get_session as base_get_session
from fastapi import Request
from sqlmodel import Session
from sse_backend import BaseSSEBackend


def get_session() -> Session:
    yield from base_get_session()


def get_sse_backend(request: Request) -> BaseSSEBackend:
    return request.app.state.sse_backend
