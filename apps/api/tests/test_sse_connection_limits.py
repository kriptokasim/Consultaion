"""Tests for SSE connection rate limiting."""
from middleware.weighted_rate_limit import _is_sse_request


def test_sse_detection():
    assert _is_sse_request("/api/v1/debates/123/stream", "GET") is True
    assert _is_sse_request("/api/v1/debates/123/events", "GET") is False
    assert _is_sse_request("/api/v1/debates/123/stream", "POST") is False
    assert _is_sse_request("/api/v1/debates/123", "GET") is False


def test_read_actions_are_classified():
    from middleware.weighted_rate_limit import READ_ACTIONS
    assert "read_run" in READ_ACTIONS
    assert "search" in READ_ACTIONS
    assert "health_check" in READ_ACTIONS
    assert "create_debate" not in READ_ACTIONS
