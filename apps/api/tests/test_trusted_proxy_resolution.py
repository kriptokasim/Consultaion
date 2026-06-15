"""Tests for rate limit identity resolution."""
import pytest
from unittest.mock import MagicMock
from middleware.rate_limit_identity import resolve_identity


def _make_request(
    user_id=None,
    auth_header=None,
    client_host="1.2.3.4",
    forwarded_for=None,
):
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


def test_authenticated_user_gets_user_identity():
    request = _make_request(user_id="user-123")
    key, id_type = resolve_identity(request)
    assert key == "wl:user:user-123"
    assert id_type == "user"


def test_valid_api_key_gets_key_identity():
    long_key = "sk-" + "a" * 40
    request = _make_request(auth_header=f"Bearer {long_key}")
    key, id_type = resolve_identity(request)
    assert key.startswith("wl:api_key:")
    assert id_type == "api_key"


def test_invalid_bearer_token_falls_to_ip():
    request = _make_request(auth_header="Bearer short")
    key, id_type = resolve_identity(request)
    assert key == "wl:ip:1.2.3.4"
    assert id_type == "ip"


def test_anonymous_request_uses_ip():
    request = _make_request()
    key, id_type = resolve_identity(request)
    assert key == "wl:ip:1.2.3.4"
    assert id_type == "ip"


def test_user_takes_precedence_over_api_key():
    long_key = "sk-" + "a" * 40
    request = _make_request(user_id="user-456", auth_header=f"Bearer {long_key}")
    key, id_type = resolve_identity(request)
    assert key == "wl:user:user-456"
    assert id_type == "user"


def test_two_different_users_get_different_buckets():
    r1 = _make_request(user_id="user-a")
    r2 = _make_request(user_id="user-b")
    k1, _ = resolve_identity(r1)
    k2, _ = resolve_identity(r2)
    assert k1 != k2


def test_two_different_ips_get_different_buckets():
    r1 = _make_request(client_host="1.1.1.1")
    r2 = _make_request(client_host="2.2.2.2")
    k1, _ = resolve_identity(r1)
    k2, _ = resolve_identity(r2)
    assert k1 != k2
