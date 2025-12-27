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


def create_openrouter_client() -> dict:
    return _noop_factory("openrouter")()


def create_groq_client() -> dict:
    return _noop_factory("groq")()


def create_mistral_client() -> dict:
    return _noop_factory("mistral")()


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
    "openrouter": ProviderConfig(
        name="OpenRouter",
        base_url="https://openrouter.ai/api/v1",
        api_key_env="OPENROUTER_API_KEY",
        client_factory=create_openrouter_client,
    ),
    "groq": ProviderConfig(
        name="Groq",
        base_url=None,  # LiteLLM uses groq/ prefix
        api_key_env="GROQ_API_KEY",
        client_factory=create_groq_client,
    ),
    "mistral": ProviderConfig(
        name="Mistral",
        base_url=None,  # LiteLLM uses mistral/ prefix
        api_key_env="MISTRAL_API_KEY",
        client_factory=create_mistral_client,
    ),
}


def get_provider_config(key: str) -> ProviderConfig | None:
    return PROVIDERS.get(key)
