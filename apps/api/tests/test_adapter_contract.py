"""Verify BaseAdapter ABC enforces the adapter contract."""

from __future__ import annotations

import pytest
from model_gateway.adapters import (
    BaseAdapter,
    DirectProviderAdapter,
    MockAdapter,
    OpenRouterAdapter,
)


def test_base_adapter_cannot_be_instantiated() -> None:
    with pytest.raises(TypeError, match="Can't instantiate abstract class"):
        BaseAdapter()  # type: ignore[abstract]


def test_incomplete_subclass_cannot_be_instantiated() -> None:
    class Incomplete(BaseAdapter):
        async def call_llm(self, **kwargs):
            raise NotImplementedError()

    with pytest.raises(TypeError, match="abstract"):
        Incomplete()  # type: ignore[abstract]


def test_direct_provider_adapter_instantiates() -> None:
    adapter = DirectProviderAdapter()
    assert isinstance(adapter, BaseAdapter)


def test_openrouter_adapter_instantiates() -> None:
    adapter = OpenRouterAdapter()
    assert isinstance(adapter, BaseAdapter)


def test_mock_adapter_instantiates() -> None:
    adapter = MockAdapter()
    assert isinstance(adapter, BaseAdapter)
