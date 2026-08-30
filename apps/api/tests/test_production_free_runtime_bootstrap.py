from model_gateway.adapters import OpenRouterAdapter
from model_gateway.free_model_runtime import install_current_free_model_targets


def test_legacy_openrouter_fallback_aliases_resolve_to_free_routes():
    install_current_free_model_targets()

    assert OpenRouterAdapter._resolve_model("router-smart") == "openrouter/openrouter/free"
    assert OpenRouterAdapter._resolve_model("gpt4o-mini") == "openrouter/openrouter/free"
    assert OpenRouterAdapter._resolve_model("groq-llama-3-3") == "openrouter/openai/gpt-oss-20b:free"
    assert OpenRouterAdapter._resolve_model("openrouter-nemotron-free") == "openrouter/nvidia/nemotron-3-ultra:free"


def test_current_free_candidates_are_not_old_nemotron_or_llama_slugs():
    install_current_free_model_targets()

    from model_gateway.free_model_runtime import FREE_OPENROUTER_CANDIDATES

    assert "openrouter/nvidia/nemotron-3-super-120b-a12b:free" not in FREE_OPENROUTER_CANDIDATES
    assert "openrouter/meta-llama/llama-3.3-70b-instruct" not in FREE_OPENROUTER_CANDIDATES
