from unittest.mock import MagicMock

import pytest
from parliament.model_registry import ModelInfo
from parliament.router_v2 import RouteContext, choose_model


@pytest.fixture
def mock_registry(monkeypatch):
    models = [
        ModelInfo(
            id="fast-cheap",
            display_name="Fast Cheap",
            provider="openai",
            litellm_model="openai/fast",
            cost_tier="low",
            latency_class="fast",
            quality_tier="baseline",
            safety_profile="normal",
        ),
        ModelInfo(
            id="slow-expensive",
            display_name="Slow Expensive",
            provider="anthropic",
            litellm_model="anthropic/slow",
            cost_tier="high",
            latency_class="slow",
            quality_tier="flagship",
            safety_profile="strict",
        ),
        ModelInfo(
            id="router-smart",
            display_name="Router",
            provider="openrouter",
            litellm_model="router",
            cost_tier="medium",
            latency_class="normal",
            quality_tier="advanced",
            safety_profile="normal",
        )
    ]
    
    def mock_list():
        return models
        
    def mock_get(name):
        for m in models:
            if m.id == name:
                return m
        return None
        
    monkeypatch.setattr("parliament.router_v2.list_enabled_models", mock_list)
    monkeypatch.setattr("parliament.router_v2.get_model_info", mock_get)
    return models


@pytest.fixture
def mock_health(monkeypatch):
    mock_state = MagicMock()
    mock_state.is_open.return_value = False
    
    def get_state(provider, model):
        return mock_state
        
    monkeypatch.setattr("parliament.router_v2.get_health_state", get_state)
    return mock_state


def test_explicit_override(mock_registry, mock_health):
    ctx = RouteContext(requested_model="slow-expensive")
    selected, candidates = choose_model(ctx)
    
    assert selected == "slow-expensive"
    assert len(candidates) == 1
    assert candidates[0].details["reason"] == "explicit_override"


def test_router_smart_preference(mock_registry, mock_health):
    # Smart router weights: quality=0.4, cost=0.3, latency=0.2, safety=0.1
    # fast-cheap: 
    #   cost(low)=1.0 * 0.3 = 0.3
    #   latency(fast)=1.0 * 0.2 = 0.2
    #   quality(baseline)=0.1 * 0.4 = 0.04
    #   safety(normal)=0.8 * 0.1 = 0.08
    #   total = 0.62
    
    # slow-expensive:
    #   cost(high)=0.1 * 0.3 = 0.03
    #   latency(slow)=0.1 * 0.2 = 0.02
    #   quality(flagship)=1.0 * 0.4 = 0.4
    #   safety(strict)=1.0 * 0.1 = 0.1
    #   total = 0.55
    
    # So fast-cheap should win in smart mode (balanced)
    
    ctx = RouteContext(routing_policy="router-smart")
    selected, candidates = choose_model(ctx)
    
    assert selected == "fast-cheap"
    assert candidates[0].model == "fast-cheap"
    assert candidates[1].model == "slow-expensive"


def test_router_deep_preference(mock_registry, mock_health):
    # Deep router weights: quality=0.8, cost=0.1, latency=0.05, safety=0.05
    # fast-cheap:
    #   quality(baseline)=0.1 * 0.8 = 0.08
    #   cost(low)=1.0 * 0.1 = 0.1
    #   latency(fast)=1.0 * 0.05 = 0.05
    #   safety(normal)=0.8 * 0.05 = 0.04
    #   total = 0.27
    
    # slow-expensive:
    #   quality(flagship)=1.0 * 0.8 = 0.8
    #   cost(high)=0.1 * 0.1 = 0.01
    #   latency(slow)=0.1 * 0.05 = 0.005
    #   safety(strict)=1.0 * 0.05 = 0.05
    #   total = 0.865
    
    # So slow-expensive should win in deep mode
    
    ctx = RouteContext(routing_policy="router-deep")
    selected, candidates = choose_model(ctx)
    
    assert selected == "slow-expensive"


def test_unhealthy_penalty(mock_registry, monkeypatch):
    # Make fast-cheap unhealthy
    def get_health(provider, model):
        m = MagicMock()
        if model == "fast-cheap":
            m.is_open.return_value = True # Open circuit = unhealthy
        else:
            m.is_open.return_value = False
        return m
        
    monkeypatch.setattr("parliament.router_v2.get_health_state", get_health)
    
    # Even in smart mode, fast-cheap should lose due to penalty
    ctx = RouteContext(routing_policy="router-smart")
    selected, candidates = choose_model(ctx)
    
    # fast-cheap score was 0.62, with penalty * 0.1 = 0.062
    # slow-expensive score was 0.55
    
    assert selected == "slow-expensive"
    assert candidates[0].model == "slow-expensive"
    # Verify fast-cheap is present but low score
    found = False
    for c in candidates:
        if c.model == "fast-cheap":
            found = True
            assert c.total_score < 0.1
            assert not c.is_healthy
    assert found
