"""Tests for read operation rate limiting."""
import pytest
from middleware.weighted_rate_limit import _classify_endpoint, READ_ACTIONS


def test_health_check_classified():
    action = _classify_endpoint("GET", "/api/v1/health")
    assert action == "health_check"
    assert action in READ_ACTIONS


def test_search_classified():
    action = _classify_endpoint("GET", "/api/v1/search")
    assert action == "search"
    assert action in READ_ACTIONS


def test_read_run_classified():
    action = _classify_endpoint("GET", "/api/v1/debates/123")
    assert action == "read_run"
    assert action in READ_ACTIONS


def test_read_report_classified():
    action = _classify_endpoint("GET", "/api/v1/debates/123/report")
    assert action == "read_report"
    assert action in READ_ACTIONS


def test_events_classified():
    action = _classify_endpoint("GET", "/api/v1/debates/123/events")
    assert action == "get_events"
    assert action in READ_ACTIONS


def test_create_debate_not_a_read():
    action = _classify_endpoint("POST", "/api/v1/debates")
    assert action == "create_debate"
    assert action not in READ_ACTIONS


def test_sse_stream_not_a_read():
    action = _classify_endpoint("GET", "/api/v1/debates/123/stream")
    assert action == "sse_stream"
    assert action not in READ_ACTIONS
