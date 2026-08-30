from parliament import model_registry


def test_sota_roster_uses_current_verified_model_slugs():
    expected = {
        "sota-gpt": "openrouter/openai/gpt-5.6-sol",
        "sota-claude": "openrouter/anthropic/claude-opus-5",
        "sota-gemini": "openrouter/google/gemini-3.1-pro-preview",
        "sota-grok": "openrouter/x-ai/grok-4.6",
        "sota-glm": "openrouter/z-ai/glm-5",
        "sota-kimi": "openrouter/moonshotai/kimi-k2.5",
    }
    for model_id, slug in expected.items():
        info = model_registry.get_model_info(model_id)
        assert info is not None
        assert info.litellm_model == slug
        assert info.provider == "openrouter"
        assert info.quality_tier == "flagship"


def test_free_roster_remains_explicit_and_disjoint_from_sota_roster():
    assert model_registry.FREE_ARENA_MODELS
    assert model_registry.SOTA_ARENA_MODELS
    assert set(model_registry.FREE_ARENA_MODELS).isdisjoint(
        model_registry.SOTA_ARENA_MODELS
    )


def test_sota_roster_is_selected_when_free_only_is_disabled(monkeypatch):
    monkeypatch.setattr(model_registry.settings, "FREE_ONLY_MODE", False)
    monkeypatch.setattr(model_registry, "list_enabled_models", lambda: list(model_registry.ALL_MODELS))
    selected = [model.id for model in model_registry.get_arena_models()]
    assert selected == model_registry.SOTA_ARENA_MODELS


def test_free_roster_is_selected_when_free_only_is_enabled(monkeypatch):
    monkeypatch.setattr(model_registry.settings, "FREE_ONLY_MODE", True)
    monkeypatch.setattr(model_registry, "list_enabled_models", lambda: list(model_registry.ALL_MODELS))
    selected = [model.id for model in model_registry.get_arena_models()]
    assert selected == model_registry.FREE_ARENA_MODELS
