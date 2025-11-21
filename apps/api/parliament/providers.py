from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Dict


@dataclass(slots=True)
class ProviderConfig:
    name: str
    base_url: str | None
    api_key_env: str
    client_factory: Callable[[], Any]


def _noop_factory(name: str) -> Callable[[], dict]:
    def _factory() -> dict:
        # Placeholder object; litellm handles routing via model override.
        return {"provider": name}

    return _factory


def create_openai_client() -> dict:
    return _noop_factory("openai")()


def create_anthropic_client() -> dict:
    return _noop_factory("anthropic")()


def create_gemini_client() -> dict:
    return _noop_factory("google")()


PROVIDERS: Dict[str, ProviderConfig] = {
    "openai": ProviderConfig(
        name="OpenAI",
        base_url=None,
        api_key_env="OPENAI_API_KEY",
        client_factory=create_openai_client,
    ),
    "anthropic": ProviderConfig(
        name="Anthropic",
        base_url=None,
        api_key_env="ANTHROPIC_API_KEY",
        client_factory=create_anthropic_client,
    ),
    "google": ProviderConfig(
        name="Google Gemini",
        base_url=None,
        api_key_env="GEMINI_API_KEY",
        client_factory=create_gemini_client,
    ),
}


def get_provider_config(key: str) -> ProviderConfig | None:
    return PROVIDERS.get(key)
