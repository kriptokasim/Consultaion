"""Tests for the retry stage graph module."""

from orchestration.stage_graph import (
    KNOWN_STAGES,
    STAGE_ALIASES,
    STAGE_INVALIDATION_GRAPH,
    normalize_stage_key,
    downstream_stages,
    validate_stage_graph,
    get_stages_to_invalidate,
)


class TestStageNormalization:
    def test_known_stage_unchanged(self):
        assert normalize_stage_key("draft") == "draft"

    def test_alias_resolved(self):
        assert normalize_stage_key("opening") == "draft"
        assert normalize_stage_key("argument") == "critique"
        assert normalize_stage_key("evaluation") == "judge"

    def test_unknown_stage_passthrough(self):
        assert normalize_stage_key("unknown") == "unknown"


class TestDownstreamStages:
    def test_draft_downstream(self):
        downstream = downstream_stages("draft")
        assert "critique" in downstream
        assert "judge" in downstream
        assert "synthesis" in downstream

    def test_unknown_stage_returns_self(self):
        downstream = downstream_stages("unknown")
        assert "unknown" in downstream

    def test_no_duplicates(self):
        downstream = downstream_stages("draft")
        assert len(downstream) == len(set(downstream))


class TestStageGraphValidation:
    def test_graph_valid(self):
        errors = validate_stage_graph()
        assert errors == [], f"Graph validation errors: {errors}"

    def test_all_known_stages_have_entries(self):
        for stage in KNOWN_STAGES:
            assert stage in STAGE_INVALIDATION_GRAPH, f"Missing entry for {stage}"

    def test_no_self_loops_except_intended(self):
        for stage, deps in STAGE_INVALIDATION_GRAPH.items():
            for dep in deps:
                if dep == stage:
                    assert stage in KNOWN_STAGES, f"Self-loop on unknown stage: {stage}"


class TestGetStagesToInvalidate:
    def test_known_stage(self):
        stages = get_stages_to_invalidate("draft")
        assert "draft" in stages
        assert "critique" in stages

    def test_alias_stage(self):
        stages = get_stages_to_invalidate("opening")
        assert "draft" in stages

    def test_unknown_stage_returns_self(self):
        stages = get_stages_to_invalidate("unknown")
        assert stages == ["unknown"]


class TestStageAliases:
    def test_all_aliases_resolve(self):
        for alias, target in STAGE_ALIASES.items():
            assert normalize_stage_key(alias) == target

    def test_all_alias_targets_are_known(self):
        for alias, target in STAGE_ALIASES.items():
            assert target in KNOWN_STAGES, f"Alias target {target} not in known stages"
