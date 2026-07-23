"""Regression coverage for the durable Arena panel execution contract."""

from types import SimpleNamespace

import pytest
from arena.engine import (
    _resolve_arena_models_from_panel,
    _select_arena_execution_models,
)
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
        ]
    }

    models = _resolve_arena_models_from_panel(panel)

    assert [model.id for model in models] == ["gpt4o-mini"]


def test_retired_web_panel_model_resolves_to_explicit_compatibility_seat():
    models = _resolve_arena_models_from_panel(
        {"seats": [{"model": "gpt-4.1-mini"}]}
    )

    assert [model.id for model in models] == ["gpt4o-mini"]


@pytest.mark.parametrize(
    "seats",
    [
        [{"model": "unknown-model"}],
        [{"model": "gpt4o-mini"}, {"model": "unknown-model"}],
        [{"display_name": "Missing durable model identity"}],
        ["not-a-seat-object"],
    ],
)
def test_nonempty_panel_with_unresolved_seat_fails_closed(seats):
    with pytest.raises(ValueError, match="unresolved model seats"):
        _select_arena_execution_models({"seats": seats})


def test_legacy_missing_or_empty_panel_retains_global_fallback(monkeypatch):
    fallback = [SimpleNamespace(id="global-fallback")]
    monkeypatch.setattr("arena.engine.get_arena_models", lambda: fallback)

    assert _select_arena_execution_models(None) is fallback
    assert _select_arena_execution_models({"seats": []}) is fallback


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
