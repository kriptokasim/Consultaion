"""Patchset 138: Run pipeline regression test (A4).

Tests that a debate created with default arena panel_config flows through
model resolution without immediate failure after "Debate initialized".
"""
import pytest


def _default_arena_seat_models():
    """Return model IDs used by the frontend default panel config."""
    return [
        "openai/gpt-4o-mini",
        "anthropic/claude-3-5-sonnet-20240620",
    ]


class TestDefaultArenaModelResolution:
    """Test that default arena model IDs resolve correctly through the gateway path."""

    @pytest.mark.parametrize("model_id", _default_arena_seat_models())
    def test_seat_model_resolves(self, model_id: str):
        """Each default seat model must resolve to a canonical MODEL_MAP key."""
        from model_gateway.model_map import MODEL_MAP, resolve_model_key
        resolved = resolve_model_key(model_id)
        assert resolved in MODEL_MAP, (
            f"Seat model '{model_id}' resolved to '{resolved}' which is not canonical"
        )

    @pytest.mark.parametrize("model_id", _default_arena_seat_models())
    def test_model_has_litellm_target(self, model_id: str):
        """Resolved model must map to a valid LiteLLM model string."""
        from model_gateway.model_map import MODEL_MAP, resolve_model_key
        resolved = resolve_model_key(model_id)
        record = MODEL_MAP[resolved]
        assert record.get("litellm_model"), f"{resolved} missing litellm_model"
        assert record.get("provider"), f"{resolved} missing provider"

    def test_all_model_pool_references_valid(self):
        """Every canonical key referenced in DEFAULT_POOLS must exist in MODEL_MAP."""
        from model_gateway.model_map import MODEL_MAP
        from model_gateway.pools import load_pools_config

        config = load_pools_config()
        pools = config.get("pools", {})
        bad_refs = []
        for pool_name, pool_info in pools.items():
            # Skip test/demo pools — 'mock' model is not in MODEL_MAP
            if pool_name in ("test_pool", "demo_pool"):
                continue
            for m in pool_info.get("models", []):
                if m not in MODEL_MAP:
                    # Check if it's an alias that resolves
                    try:
                        from model_gateway.model_map import resolve_model_key
                        resolve_model_key(m)
                    except Exception:
                        bad_refs.append(f"{pool_name}.{m}")
        assert not bad_refs, f"Invalid pool model references: {bad_refs}"

    def test_legacy_pool_mappings_valid(self):
        """Every model id in legacy_pools must resolve to a canonical key."""
        from model_gateway.model_map import ModelKeyError, resolve_model_key

        # We read the internal legacy_pools dict by calling get_model_pool directly
        from model_gateway.pools import get_model_pool
        legacy_test_ids = [
            "gpt4o-mini", "gpt4o-deep", "claude-sonnet", "claude-haiku",
            "gemini-2-flash", "gemini-2-5-pro", "groq-llama-3-3",
            "mistral-large", "deepseek-r1", "router-smart", "router-deep",
        ]
        bad = []
        for mid in legacy_test_ids:
            try:
                resolved = resolve_model_key(mid)
                pool = get_model_pool(resolved)
                assert isinstance(pool, str) and pool
            except (ModelKeyError, Exception) as e:
                bad.append(f"{mid}: {e}")
        assert not bad, f"Legacy pool mapping failures: {bad}"


class TestRunPipelineModelValidation:
    """Test that the model validation runs correctly in the debate creation path."""

    def test_default_panel_config_validates(self):
        """The default panel config must pass schema validation."""
        from schemas import PanelConfig, default_panel_config
        config = default_panel_config()
        validated = PanelConfig.model_validate(config.model_dump())
        assert len(validated.seats) > 0
        for seat in validated.seats:
            assert seat.model, f"Seat {seat.seat_id} missing model"
            assert seat.provider_key, f"Seat {seat.seat_id} missing provider_key"

    async def test_model_resolution_with_mock_routing(self):
        """Simulate the route_llm_call path with a litellm-style model_id.

        Uses MockAdapter to avoid real provider calls. Verifies that model
        resolution does not fail before the adapter is reached.
        """
        from model_gateway import route_llm_call
        from model_gateway.types import GatewayRequest

        request = GatewayRequest(
            messages=[{"role": "user", "content": "Test prompt"}],
            model_id="openai/gpt-4o-mini",
            role="test",
            temperature=0.5,
            max_tokens=100,
            gateway_policy="auto",
            user_id=None,
            user_plan="free",
        )

        # We only test that the call doesn't fail at model resolution.
        # It will likely fail at the adapter level because no API keys are set,
        # but that's a different error code (not model_key_unresolved).
        result = await route_llm_call(request, db_session=None)

        assert result is not None
        # The error code should NOT be model_key_unresolved — that means
        # the model resolution step failed.
        if not result.success:
            assert result.error_code != "model_key_unresolved", (
                f"Model resolution failed for '{request.model_id}': {result.error_message}"
            )
