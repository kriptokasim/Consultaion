"""Unit tests for canonical model target resolver (PS181)."""
import pytest
from model_gateway.model_target import (
    ResolvedModelTarget,
    UnknownModelError,
    resolve_model_target,
)


def test_resolve_canonical_key():
    target = resolve_model_target("openai_fast")
    assert isinstance(target, ResolvedModelTarget)
    assert target.canonical_id == "openai_fast"
    assert target.provider == "openai"
    assert target.litellm_model == "openai/gpt-4o-mini"
    assert target.uses_openrouter is False
    assert target.cost_class == "cheap"


def test_resolve_alias():
    target = resolve_model_target("gpt-4o-mini")
    assert target.canonical_id == "openai_fast"
    assert target.provider == "openai"

    target_sonnet = resolve_model_target("claude-3-5-sonnet")
    assert target_sonnet.canonical_id == "anthropic_reasoning"
    assert target_sonnet.provider == "anthropic"


def test_resolve_litellm_string():
    target = resolve_model_target("openai/gpt-4o-mini")
    assert target.canonical_id == "openai_fast"
    assert target.provider == "openai"

    target_openrouter = resolve_model_target("openrouter/deepseek/deepseek-r1")
    assert target_openrouter.canonical_id == "deepseek-r1"
    assert target_openrouter.provider == "openrouter"
    assert target_openrouter.uses_openrouter is True


def test_resolve_default_when_none_or_empty():
    target_none = resolve_model_target(None)
    assert target_none.canonical_id == "openai_fast"

    target_empty = resolve_model_target("")
    assert target_empty.canonical_id == "openai_fast"


def test_resolve_unknown_model_raises_error():
    with pytest.raises(UnknownModelError):
        resolve_model_target("completely_unknown_model_xyz_999")
