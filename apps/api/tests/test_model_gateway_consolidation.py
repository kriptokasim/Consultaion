import pytest

from config import settings
from model_gateway.model_map import (
    MODEL_MAP,
    MODEL_ALIASES,
    ModelKeyError,
    resolve_model_key,
    is_free_model,
    get_model_cost_class
)
from model_gateway import route_llm_call
from model_gateway.types import GatewayRequest, GatewayModelRestrictedError

def test_resolve_canonical_key():
    """Canonical keys resolve to themselves."""
    assert resolve_model_key("openai_fast") == "openai_fast"
    assert resolve_model_key("gemini_general") == "gemini_general"

def test_resolve_alias():
    """Aliases resolve to their canonical key."""
    assert resolve_model_key("gpt4o-mini") == "openai_fast"
    assert resolve_model_key("gemini-2-flash") == "gemini_general"

def test_resolve_unknown_key_raises_error():
    """Unknown keys raise ModelKeyError."""
    with pytest.raises(ModelKeyError) as exc_info:
        resolve_model_key("some_fake_model")
    assert "Unknown model key" in str(exc_info.value)

def test_is_free_model():
    """Only explicit 'free' cost_class returns True."""
    assert is_free_model("groq_fast") is True
    assert is_free_model("openai_fast") is False  # cheap
    assert is_free_model("openai_premium") is False  # paid
    assert is_free_model("openrouter_fallback") is False  # unknown

@pytest.mark.asyncio
async def test_route_llm_call_free_only_guard():
    """FREE_ONLY_MODE blocks non-free models at the gateway."""
    # Temporarily set FREE_ONLY_MODE to True
    original = settings.FREE_ONLY_MODE
    settings.FREE_ONLY_MODE = True
    
    try:
        # 1. Paid model should be blocked
        req_paid = GatewayRequest(
            messages=[{"role": "user", "content": "hi"}],
            model_id="openai_premium",
            role="user"
        )
        with pytest.raises(GatewayModelRestrictedError) as exc_info:
            await route_llm_call(req_paid)
        assert "not available in free-only mode" in str(exc_info.value)
        
        # 2. Free model should pass (at least pass the guard)
        req_free = GatewayRequest(
            messages=[{"role": "user", "content": "hi"}],
            model_id="groq_fast",
            role="user"
        )
        # It might fail later in mock/routing due to lack of DB, but it shouldn't fail the free-only guard
        try:
            await route_llm_call(req_free)
        except GatewayModelRestrictedError:
            pytest.fail("Free model was incorrectly blocked by FREE_ONLY_MODE")
        except Exception:
            pass # Other errors (like mock routing) are fine for this test
            
    finally:
        settings.FREE_ONLY_MODE = original
