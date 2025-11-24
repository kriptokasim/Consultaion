"""
Tests for provider health tracking and circuit breaker.

Patchset 28.0
"""

import pytest
from datetime import datetime, timedelta, timezone

from parliament.provider_health import (
    ProviderHealthState,
    get_health_state,
    record_call_result,
    reset_health_state,
    clear_all_health_states,
)
from exceptions import ProviderCircuitOpenError


@pytest.fixture(autouse=True)
def clean_health_registry():
    """Clear health registry before each test."""
    clear_all_health_states()
    yield
    clear_all_health_states()


def test_health_state_opens_on_threshold():
    """Circuit should open when error rate exceeds threshold."""
    state = ProviderHealthState(
        provider="openai",
        model="gpt-4o",
        window_seconds=300,
        error_threshold=0.5,
        min_calls=10,
        cooldown_seconds=60,
    )
    
    now = datetime.now(timezone.utc)
    
    # Record 10 calls: 6 errors (60% error rate > 50% threshold)
    for _ in range(4):
        state.record_success(now)
    for _ in range(6):
        state.record_error(now)
    
    assert state.should_open(now)
    assert state.last_opened is not None


def test_health_state_respects_min_calls():
    """Circuit should not open with fewer than min_calls."""
    state = ProviderHealthState(
        provider="openai",
        model="gpt-4o",
        window_seconds=300,
        error_threshold=0.5,
        min_calls=10,
        cooldown_seconds=60,
    )
    
    now = datetime.now(timezone.utc)
    
    # Only 5 calls, all errors (< min_calls)
    for _ in range(5):
        state.record_error(now)
    
    assert not state.should_open(now)


def test_circuit_closes_after_cooldown():
    """Circuit should close after cooldown period."""
    state = ProviderHealthState(
        provider="openai",
        model="gpt-4o",
        window_seconds=300,
        error_threshold=0.5,
        min_calls=10,
        cooldown_seconds=60,
    )
    
    now = datetime.now(timezone.utc)
    
    # Open the circuit
    for _ in range(10):
        state.record_error(now)
    
    assert state.is_open(now)
    
    # After cooldown, circuit should close
    future = now + timedelta(seconds=61)
    assert not state.is_open(future)


def test_get_health_state_creates_new():
    """get_health_state should create state if not exists."""
    state = get_health_state("anthropic", "claude-3-5-sonnet")
    
    assert state.provider == "anthropic"
    assert state.model == "claude-3-5-sonnet"
    assert state.total_calls == 0


def test_get_health_state_returns_existing():
    """get_health_state should return existing state."""
    state1 = get_health_state("openai", "gpt-4o")
    state1.total_calls = 5
    
    state2 = get_health_state("openai", "gpt-4o")
    assert state2.total_calls == 5
    assert state1 is state2


def test_record_call_result_success():
    """record_call_result should track successful calls."""
    now = datetime.now(timezone.utc)
    
    record_call_result("openai", "gpt-4o", success=True, now=now)
    
    state = get_health_state("openai", "gpt-4o")
    assert state.total_calls == 1
    assert state.error_calls == 0


def test_record_call_result_error():
    """record_call_result should track failed calls."""
    now = datetime.now(timezone.utc)
    
    record_call_result("openai", "gpt-4o", success=False, now=now)
    
    state = get_health_state("openai", "gpt-4o")
    assert state.total_calls == 1
    assert state.error_calls == 1


def test_reset_health_state():
    """reset_health_state should clear specific provider."""
    state = get_health_state("openai", "gpt-4o")
    state.total_calls = 10
    
    reset_health_state("openai", "gpt-4o")
    
    new_state = get_health_state("openai", "gpt-4o")
    assert new_state.total_calls == 0
