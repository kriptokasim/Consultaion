"""Patchset 138: Model resolution regression tests.

Tests that:
1. All default panel config (frontend-side) model IDs resolve correctly
2. All canonical keys pass through unchanged
3. All short aliases resolve correctly
4. All litellm-format model strings resolve correctly
5. Unknown model keys raise ModelKeyError
6. Each resolved canonical key exists in MODEL_MAP
"""
import pytest
from model_gateway.model_map import (
    MODEL_MAP,
    MODEL_ALIASES,
    ModelKeyError,
    resolve_model_key,
    get_model_cost_class,
    is_free_model,
)


class TestModelResolution:
    """Default values that frontend sends as seat.model (from schemas.default_panel_config)."""

    DEFAULT_PANEL_SEAT_MODELS = [
        "openai/gpt-4o-mini",
        "anthropic/claude-3-5-sonnet-20240620",
    ]

    FRONTEND_MODEL_IDS = [
        "gpt4o-mini",
        "gpt4o-deep",
        "claude-sonnet",
        "claude-haiku",
        "gemini-2-flash",
        "gemini-2-5-pro",
        "groq-llama-3-3",
        "mistral-large",
        "deepseek-r1",
        "router-smart",
        "router-deep",
    ]

    LITELLM_FORMAT_IDS = [
        "openai/gpt-4o-mini",
        "openai/gpt-4o",
        "anthropic/claude-3-5-sonnet-20240620",
        "anthropic/claude-3-haiku-20240307",
        "gemini/gemini-2.0-flash",
        "gemini/gemini-2.5-pro-preview-06-05",
        "groq/llama-3.3-70b-versatile",
        "mistral/mistral-large-latest",
        "openrouter/deepseek/deepseek-r1",
    ]

    CANONICAL_KEYS = list(MODEL_MAP.keys())

    @pytest.mark.parametrize("model_id", DEFAULT_PANEL_SEAT_MODELS)
    def test_default_panel_seat_models_resolve(self, model_id: str):
        """Default panel config seat models must resolve to a canonical key."""
        resolved = resolve_model_key(model_id)
        assert resolved in MODEL_MAP, (
            f"Default panel seat model '{model_id}' resolved to '{resolved}' "
            f"which is not a canonical MODEL_MAP key"
        )

    @pytest.mark.parametrize("model_id", FRONTEND_MODEL_IDS)
    def test_frontend_model_ids_resolve(self, model_id: str):
        """All frontend-facing model IDs must resolve to canonical keys."""
        resolved = resolve_model_key(model_id)
        assert resolved in MODEL_MAP, (
            f"Frontend model ID '{model_id}' → '{resolved}' not in MODEL_MAP"
        )

    @pytest.mark.parametrize("model_id", LITELLM_FORMAT_IDS)
    def test_litellm_format_ids_resolve(self, model_id: str):
        """Litellm-format model strings must resolve (arena engine passes these as model_override)."""
        resolved = resolve_model_key(model_id)
        assert resolved in MODEL_MAP, (
            f"Litellm format '{model_id}' → '{resolved}' not in MODEL_MAP"
        )

    @pytest.mark.parametrize("canonical_key", CANONICAL_KEYS)
    def test_canonical_keys_pass_through(self, canonical_key: str):
        """Canonical keys must be returned unchanged."""
        resolved = resolve_model_key(canonical_key)
        assert resolved == canonical_key, (
            f"Canonical key '{canonical_key}' changed to '{resolved}'"
        )

    def test_unknown_key_raises(self):
        """An unknown model key must raise ModelKeyError."""
        with pytest.raises(ModelKeyError):
            resolve_model_key("completely-fake-model-name")

    def test_all_resolved_keys_have_metadata(self):
        """Every model key that resolves must have a MODEL_MAP entry."""
        all_ids = set(self.FRONTEND_MODEL_IDS + self.LITELLM_FORMAT_IDS + self.CANONICAL_KEYS)
        for model_id in all_ids:
            try:
                resolved = resolve_model_key(model_id)
                assert resolved in MODEL_MAP, f"{model_id} → {resolved} missing from MODEL_MAP"
                record = MODEL_MAP[resolved]
                assert "provider" in record, f"{resolved} missing 'provider'"
                assert "litellm_model" in record, f"{resolved} missing 'litellm_model'"
            except ModelKeyError:
                pass  # unknown keys tested separately

    def test_deprecated_usage_logs_warning(self, caplog):
        """Using an alias (not canonical) logs a deprecation warning."""
        import logging
        caplog.set_level(logging.WARNING, logger="model_gateway.model_map")
        resolve_model_key("gpt4o-mini")
        assert "Deprecated model alias" in caplog.text

    def test_alias_count(self):
        """MODEL_ALIASES count includes all reverse lookups."""
        assert len(MODEL_ALIASES) >= 20  # short + litellm format aliases

    def test_aliases_dont_duplicate_canonical_keys(self):
        """No alias should be a canonical key."""
        for alias in MODEL_ALIASES:
            assert alias not in MODEL_MAP, (
                f"Alias '{alias}' also appears as a canonical key in MODEL_MAP"
            )


class TestModelCostClassification:
    """Cost class and free-model helpers should work after resolution."""

    def test_free_models(self):
        """Known free models should return True for is_free_model."""
        free_canonicals = [
            k for k, v in MODEL_MAP.items() if v.get("cost_class") == "free"
        ]
        assert free_canonicals, "Expected at least one free model"
        for key in free_canonicals:
            assert is_free_model(key), f"{key} should be free"

    def test_paid_models(self):
        """Known paid models should return False for is_free_model."""
        paid_canonicals = [
            k for k, v in MODEL_MAP.items() if v.get("cost_class") == "paid"
        ]
        assert paid_canonicals, "Expected at least one paid model"
        for key in paid_canonicals:
            assert not is_free_model(key), f"{key} should not be free"

    def test_unknown_model_cost_class(self):
        """An unknown key returns 'unknown' cost class without error."""
        cls = get_model_cost_class("nonexistent_model_key")
        assert cls == "unknown"
