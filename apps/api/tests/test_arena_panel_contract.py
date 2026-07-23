"""Regression coverage for the durable Arena panel execution contract."""

from types import SimpleNamespace

from arena.engine import _resolve_arena_models_from_panel
from serializers import _get_models_expected


def test_panel_models_resolve_in_selected_order_with_legacy_aliases():
    panel = {
        "seats": [
            {"model": "gpt-4o", "seat_id": "openai"},
            {"model": "claude-sonnet", "seat_id": "anthropic"},
            {"model": "gemini-1.5-flash", "seat_id": "google"},
        ]
    }

    models = _resolve_arena_models_from_panel(panel)

    assert [model.id for model in models] == [
        "gpt4o-deep",
        "claude-sonnet",
        "gemini-2-flash",
    ]


def test_panel_model_identity_is_deduplicated_after_canonicalization():
    panel = {
        "seats": [
            {"model": "gpt4o-mini"},
            {"model": "openai/gpt-4o-mini"},
            {"model": "unknown-model"},
        ]
    }

    models = _resolve_arena_models_from_panel(panel)

    assert [model.id for model in models] == ["gpt4o-mini"]


def test_models_expected_uses_the_persisted_execution_panel():
    debate = SimpleNamespace(
        mode="arena",
        config={},
        panel_config={
            "seats": [
                {"model": "gpt4o-mini"},
                {"model": "claude-sonnet"},
            ]
        },
    )

    assert _get_models_expected(debate) == 2
