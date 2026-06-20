"""Tests for utils.redact module.

Validates the redact_sensitive() helper which redacts sensitive keys
from dictionaries for safe logging.
"""
from utils.redact import redact_sensitive


def test_top_level_key_redaction():
    """Sensitive keys at the top level are replaced with [REDACTED]."""
    data = {
        "username": "alice",
        "password": "s3cret",
        "token": "abc123",
        "api_key": "key-xyz",
    }
    result = redact_sensitive(data)
    assert result["username"] == "alice"
    assert result["password"] == "[REDACTED]"
    assert result["token"] == "[REDACTED]"
    assert result["api_key"] == "[REDACTED]"


def test_nested_dict_redaction():
    """Sensitive keys inside nested dicts are also redacted."""
    data = {
        "user": "bob",
        "credentials": {
            "access_token": "tok-999",
            "refresh_token": "ref-888",
            "scope": "read",
        },
    }
    result = redact_sensitive(data)
    assert result["user"] == "bob"
    assert result["credentials"]["access_token"] == "[REDACTED]"
    assert result["credentials"]["refresh_token"] == "[REDACTED]"
    assert result["credentials"]["scope"] == "read"


def test_list_of_dict_redaction():
    """Sensitive keys inside dicts within lists are redacted."""
    data = {
        "entries": [
            {"name": "svc1", "secret": "s1"},
            {"name": "svc2", "client_secret": "s2"},
        ]
    }
    result = redact_sensitive(data)
    assert result["entries"][0]["name"] == "svc1"
    assert result["entries"][0]["secret"] == "[REDACTED]"
    assert result["entries"][1]["client_secret"] == "[REDACTED]"


def test_case_insensitive_detection():
    """Key matching is case-insensitive and includes substring checks."""
    data = {
        "Authorization": "Bearer xyz",
        "X-Auth-Token": "tok-abc",
        "my_password_hash": "hashed",
    }
    result = redact_sensitive(data)
    assert result["Authorization"] == "[REDACTED]"
    assert result["X-Auth-Token"] == "[REDACTED]"
    assert result["my_password_hash"] == "[REDACTED]"


def test_non_dict_passthrough():
    """Non-dict input is returned unchanged."""
    assert redact_sensitive("hello") == "hello"
    assert redact_sensitive(42) == 42
    assert redact_sensitive(None) is None
    assert redact_sensitive([1, 2, 3]) == [1, 2, 3]


def test_empty_dict():
    """Empty dict returns empty dict."""
    assert redact_sensitive({}) == {}


def test_non_sensitive_keys_preserved():
    """Keys that don't match sensitive patterns are preserved as-is."""
    data = {
        "debate_id": "d-123",
        "status": "completed",
        "score": 0.85,
        "config": {"mode": "arena", "rounds": 3},
    }
    result = redact_sensitive(data)
    assert result == data
