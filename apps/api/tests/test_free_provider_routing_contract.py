import pytest

from model_gateway.model_map import MODEL_MAP, is_free_model


def test_current_free_fallback_targets_are_explicit():
    assert MODEL_MAP["openrouter_fallback"]["provider_model_id"] == "openrouter/free"
    assert MODEL_MAP["openrouter_fallback"]["litellm_model"] == "openrouter/openrouter/free"
    assert MODEL_MAP["groq_fast"]["provider_model_id"] == "openai/gpt-oss-20b"
    assert is_free_model("openrouter_fallback")
    assert is_free_model("groq_fast")


def test_retired_free_aliases_resolve_to_current_fallback():
    from model_gateway.model_map import resolve_model_key
    assert resolve_model_key("llama-3-free") == "llama-3-free"
    assert MODEL_MAP["llama-3-free"]["replacement"] == "openrouter_fallback"
    assert MODEL_MAP["mimo-v2-free"]["replacement"] == "openrouter_fallback"


@pytest.mark.asyncio
async def test_openrouter_fallback_policy_never_reuses_failed_primary(monkeypatch):
    from model_gateway.adapters import OpenRouterAdapter

    captured = {}
    original = OpenRouterAdapter._resolve_model

    async def fake_call(self, messages, model_id, temperature, max_tokens, gateway_policy, model_pool, routing_policy, user_id=None, response_format=None, tools=None, tool_choice=None, api_key=None):
        captured["model_id"] = model_id
        captured["gateway_policy"] = gateway_policy
        return type("Result", (), {"success": False})()

    monkeypatch.setattr(OpenRouterAdapter, "call_llm", fake_call)
    # Importing model_map installs the fallback guard; calling through the
    # gateway policy must therefore rewrite the primary model to the dedicated
    # free fallback sentinel before reaching OpenRouter.
    from model_gateway.model_map import _install_fallback_model_guard
    _install_fallback_model_guard()
    adapter = OpenRouterAdapter()
    await adapter.call_llm([], "gemini_general", 0.0, 8, "fallback", "fallback", "test")
    assert captured["model_id"] == "__consultaion_free_fallback__"
    assert captured["gateway_policy"] == "fallback"
    assert original is not None
