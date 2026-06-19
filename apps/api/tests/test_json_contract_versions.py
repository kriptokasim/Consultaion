from json_contracts import (
    DebateConfigV2,
    migrate_config_v1_to_v2,
    migrate_final_meta_v1_to_v2,
    safe_validate_config,
    safe_validate_final_meta,
    validate_debate_config,
    validate_final_meta,
)


class TestDebateConfigV2:
    def test_current_version(self):
        data = {"schema_version": 2, "agents": [], "judges": [], "max_rounds": 5}
        config = validate_debate_config(data)
        assert config.schema_version == 2

    def test_prior_version_migrates(self):
        data = {"schema_version": 1}
        config = validate_debate_config(data)
        assert config.schema_version == 2
        assert config.max_rounds == 5

    def test_unknown_future_keys_preserved(self):
        data = {
            "schema_version": 2,
            "future_feature": True,
            "agents": [],
            "judges": [],
        }
        config = validate_debate_config(data)
        assert hasattr(config, "future_feature") or config.model_extra is not None

    def test_malformed_shape_uses_defaults(self):
        config = validate_debate_config({"not_a_config": True})
        assert config.max_rounds == 5

    def test_round_trip(self):
        original = DebateConfigV2(
            agents=[],
            judges=[],
            max_rounds=3,
            mode="arena",
        )
        data = original.model_dump()
        restored = validate_debate_config(data)
        assert restored.max_rounds == 3
        assert restored.mode == "arena"


class TestFinalMetaV2:
    def test_current_version(self):
        data = {"schema_version": 2, "winner": "model-a"}
        meta = validate_final_meta(data)
        assert meta.schema_version == 2

    def test_prior_version_migrates(self):
        data = {"schema_version": 1, "winner": "model-a"}
        meta = validate_final_meta(data)
        assert meta.schema_version == 2
        assert meta.attempt_count == 0

    def test_unknown_keys_preserved(self):
        data = {"schema_version": 2, "custom_field": "value"}
        meta = validate_final_meta(data)
        assert hasattr(meta, "custom_field") or meta.model_extra is not None

    def test_partial_historical_records(self):
        data = {"schema_version": 2}
        meta = validate_final_meta(data)
        assert meta.winner is None
        assert meta.scores == {}


class TestSafeValidation:
    def test_safe_validate_config_returns_none_for_none(self):
        assert safe_validate_config(None) is None

    def test_safe_validate_config_returns_valid_for_invalid(self):
        result = safe_validate_config({"garbage": True})
        assert result is not None

    def test_safe_validate_config_returns_valid(self):
        result = safe_validate_config({"schema_version": 2, "agents": [], "judges": []})
        assert result is not None
        assert result.schema_version == 2

    def test_safe_validate_final_meta_returns_none_for_none(self):
        assert safe_validate_final_meta(None) is None

    def test_safe_validate_final_meta_returns_valid_for_invalid(self):
        result = safe_validate_final_meta({"invalid": True})
        assert result is not None


class TestMigration:
    def test_config_v1_to_v2_adds_required_fields(self):
        data = {"schema_version": 1}
        result = migrate_config_v1_to_v2(data)
        assert result["schema_version"] == 2
        assert "agents" in result
        assert "judges" in result
        assert "max_rounds" in result

    def test_config_v1_to_v2_preserves_existing(self):
        data = {"schema_version": 1, "max_rounds": 10}
        result = migrate_config_v1_to_v2(data)
        assert result["max_rounds"] == 10

    def test_final_meta_v1_to_v2_adds_counters(self):
        data = {"schema_version": 1, "winner": "a"}
        result = migrate_final_meta_v1_to_v2(data)
        assert result["attempt_count"] == 0
        assert result["continuation_count"] == 0
