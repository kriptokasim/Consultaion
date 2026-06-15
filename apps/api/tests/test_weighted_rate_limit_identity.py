"""Tests for rate limit identity resolution edge cases."""
import pytest
from unittest.mock import MagicMock
from middleware.rate_limit_identity import resolve_identity


def _make_request(user_id=None, auth_header=None, client_host="1.2.3.4", forwarded_for=None):
    request = MagicMock()
    request.state = MagicMock()
    request.state.user_id = user_id
    request.headers = {}
    if auth_header:
        request.headers["Authorization"] = auth_header
    if forwarded_for:
        request.headers["X-Forwarded-For"] = forwarded_for
    request.client = MagicMock()
    request.client.host = client_host
    return request


def test_user_identity_isolation():
    r1 = _make_request(user_id="user-x")
    r2 = _make_request(user_id="user-y")
    k1, t1 = resolve_identity(r1)
    k2, t2 = resolve_identity(r2)
    assert k1 != k2
    assert t1 == "user"
    assert t2 == "user"


def test_ip_identity_isolation():
    r1 = _make_request(client_host="10.0.0.1")
    r2 = _make_request(client_host="10.0.0.2")
    k1, t1 = resolve_identity(r1)
    k2, t2 = resolve_identity(r2)
    assert k1 != k2
    assert t1 == "ip"
    assert t2 == "ip"


def test_no_client_uses_unknown():
    request = MagicMock()
    request.state = MagicMock()
    request.state.user_id = None
    request.headers = {}
    request.client = None
    key, id_type = resolve_identity(request)
    assert "unknown" in key
    assert id_type == "ip"


def test_empty_bearer_falls_to_ip():
    request = _make_request(auth_header="Bearer ")
    key, id_type = resolve_identity(request)
    assert id_type == "ip"
