"""Canonical model target resolution for the Model Gateway (PS181)."""
from __future__ import annotations

import logging
from dataclasses import dataclass

from model_gateway.model_map import MODEL_ALIASES, MODEL_MAP, ModelKeyError

logger = logging.getLogger("model_gateway.model_target")


class UnknownModelError(ModelKeyError):
    """Raised when a model target cannot be resolved."""
    pass


@dataclass(frozen=True)
class ResolvedModelTarget:
    canonical_id: str
    provider: str
    litellm_model: str
    uses_openrouter: bool
    cost_class: str
    provider_model_id: str


def resolve_model_target(model_id: str | None) -> ResolvedModelTarget:
    """Canonicalize model target resolution.

    Resolves arbitrary model keys, vendor aliases, litellm formatted strings,
    and provider prefixes into a single canonical ResolvedModelTarget.

    Fails closed with UnknownModelError if model_id cannot be resolved.
    """
    if not model_id:
        target_key = "openai_fast"
    else:
        # Step 1: Direct match in MODEL_MAP
        if model_id in MODEL_MAP:
            target_key = model_id
        else:
            # Step 2: Match in MODEL_ALIASES
            target_key = MODEL_ALIASES.get(model_id)

        # Step 3: OpenRouter prefix stripping check
        if target_key is None and model_id.startswith("openrouter/"):
            stripped = model_id[len("openrouter/"):]
            if stripped in MODEL_MAP:
                target_key = stripped
            elif stripped in MODEL_ALIASES:
                target_key = MODEL_ALIASES[stripped]

        # Step 4: Check litellm_model or provider_model_id match across MODEL_MAP
        if target_key is None:
            for key, rec in MODEL_MAP.items():
                if rec.get("litellm_model") == model_id or rec.get("provider_model_id") == model_id:
                    target_key = key
                    break

    if target_key is None or target_key not in MODEL_MAP:
        raise UnknownModelError(
            f"Cannot resolve model target for '{model_id}'. Unknown or unsupported model."
        )

    rec = MODEL_MAP[target_key]
    provider = str(rec.get("provider", "unknown"))
    litellm_model = str(rec.get("litellm_model", target_key))
    uses_openrouter = provider == "openrouter" or litellm_model.startswith("openrouter/")
    cost_class = str(rec.get("cost_class", "unknown"))
    provider_model_id = str(rec.get("provider_model_id", litellm_model))

    return ResolvedModelTarget(
        canonical_id=target_key,
        provider=provider,
        litellm_model=litellm_model,
        uses_openrouter=uses_openrouter,
        cost_class=cost_class,
        provider_model_id=provider_model_id,
    )
