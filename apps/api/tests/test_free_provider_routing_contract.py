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


def test_openrouter_fallback_sentinel_resolves_to_current_free_router():
    from model_gateway.adapters import OpenRouterAdapter
    assert OpenRouterAdapter._resolve_model("__consultaion_free_fallback__") == "openrouter/openrouter/free"
