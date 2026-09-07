"""Semantic claim similarity helper.

Uses litellm embeddings to compute semantic cosine similarity between claims.
Includes a robust fallback to token overlap & SequenceMatcher string similarity
in case embedding calls fail or keys are missing.
"""

from __future__ import annotations

import difflib
import logging
import math
import time
from typing import List

from litellm import aembedding

from config import settings

logger = logging.getLogger(__name__)

# Consecutive-failure cooldown for the embedding upstream.
#
# This call sits outside the model gateway, so none of the gateway's protections
# reach it: no circuit breaker, no budget guard, no free-only gate. Production
# showed what that costs -- 29 identical 429s ("You have no credits remaining")
# in eight seconds against a dead OpenAI account, one per synthesis attempt,
# every one a network round trip inside the synthesis path. The result was still
# correct, because the caller falls back to string similarity, but the failure
# was silent, unbudgeted and unbounded.
_EMBED_FAILURE_THRESHOLD = 3
_EMBED_COOLDOWN_SECONDS = 300.0
_embed_consecutive_failures = 0
_embed_cooldown_until = 0.0


def _embedding_cooldown_active() -> bool:
    return time.monotonic() < _embed_cooldown_until


def _note_embedding_failure() -> None:
    global _embed_consecutive_failures, _embed_cooldown_until
    _embed_consecutive_failures += 1
    if _embed_consecutive_failures >= _EMBED_FAILURE_THRESHOLD:
        _embed_cooldown_until = time.monotonic() + _EMBED_COOLDOWN_SECONDS
        logger.warning(
            "Embedding upstream failed %d times consecutively; pausing embedding "
            "calls for %.0fs and using string similarity meanwhile.",
            _embed_consecutive_failures,
            _EMBED_COOLDOWN_SECONDS,
        )


def _note_embedding_success() -> None:
    global _embed_consecutive_failures, _embed_cooldown_until
    _embed_consecutive_failures = 0
    _embed_cooldown_until = 0.0


def _embedding_blocked_reason(model_name: str) -> str | None:
    """Why this embedding call must not be made, or None to proceed.

    FREE_ONLY_MODE is the important one. The gateway enforces it for every chat
    completion, but this path never went through the gateway, so a deployment
    running free-only was still calling a paid embedding model on every debate --
    both a policy breach and, with no paid credit behind it, a guaranteed failure.
    """
    if getattr(settings, "LLM_KILL_SWITCH_ENABLED", False):
        return "kill switch engaged"
    if getattr(settings, "FREE_ONLY_MODE", False):
        try:
            from model_gateway.model_map import is_free_model, resolve_model_key

            if not is_free_model(resolve_model_key(model_name)):
                return f"FREE_ONLY_MODE is on and {model_name!r} is not a free route"
        except Exception:
            # An unresolvable key is not a known-free key.
            return f"FREE_ONLY_MODE is on and {model_name!r} is not a known free route"
    if _embedding_cooldown_active():
        return "embedding upstream is in cooldown after repeated failures"
    return None


def compute_string_similarity(c1: str, c2: str) -> float:
    """Compare claims using lowercase token overlap and SequenceMatcher (Jaccard-like)."""
    s1 = set(c1.lower().split())
    s2 = set(c2.lower().split())
    if not s1 or not s2:
        return 0.0
    jaccard = len(s1.intersection(s2)) / len(s1.union(s2))
    matcher = difflib.SequenceMatcher(None, c1.lower(), c2.lower()).ratio()
    return max(jaccard, matcher)


def cosine_similarity(v1: List[float], v2: List[float]) -> float:
    """Compute cosine similarity between two float vectors."""
    if not v1 or not v2 or len(v1) != len(v2):
        return 0.0
    
    dot_product = sum(a * b for a, b in zip(v1, v2, strict=False))
    norm_a = math.sqrt(sum(a * a for a in v1))
    norm_b = math.sqrt(sum(b * b for b in v2))
    
    if norm_a == 0.0 or norm_b == 0.0:
        return 0.0
    
    return dot_product / (norm_a * norm_b)


async def get_claim_embeddings(claims: List[str], debate_id: str | None = None) -> List[List[float]]:
    """Batch fetch embeddings for a list of claims using litellm."""
    if not claims:
        return []
        
    if settings.USE_MOCK:
        # Return dummy embeddings (1536-dim vectors with pseudo-random floats derived from claim string)
        # to ensure fast and deterministic behavior in mock mode
        dummy_vectors = []
        for claim in claims:
            # Simple hash-based deterministic vector generator
            val = sum(ord(char) for char in claim)
            dummy_vectors.append([math.sin(val + i) for i in range(128)])  # Smaller dimension is fine for mock
        return dummy_vectors

    model_name = getattr(settings, "EMBEDDING_MODEL", "openai/text-embedding-3-small")

    blocked = _embedding_blocked_reason(model_name)
    if blocked:
        logger.info(
            "Skipping embedding call (%s); using string similarity for debate %s.",
            blocked,
            debate_id or "-",
        )
        return []

    kwargs: dict = {}
    try:
        from model_gateway.proxy_transport import proxy_enabled

        if proxy_enabled():
            # Embeddings are spend like any other call; when the proxy owns the
            # budget it must see them too, or the ceiling is measuring a subset.
            kwargs["api_base"] = str(settings.LITELLM_PROXY_URL).rstrip("/")
            kwargs["api_key"] = settings.LITELLM_PROXY_API_KEY
    except Exception:
        logger.debug("Proxy transport unavailable for embeddings", exc_info=True)

    try:
        # We wrap in try-except to ensure fallback if API keys are missing or call fails
        response = await aembedding(
            model=model_name,
            input=claims,
            **kwargs,
        )
    except Exception as exc:
        _note_embedding_failure()
        logger.warning(
            "Embedding API call failed for model %s. Falling back to string similarity. Error: %s",
            model_name,
            exc,
        )
        return []

    _note_embedding_success()
    return [data["embedding"] for data in response["data"]]


async def compute_semantic_similarity(
    claim1: str,
    claim2: str,
    embed1: List[float] | None = None,
    embed2: List[float] | None = None,
) -> float:
    """Compute semantic similarity using embeddings, falling back to string overlap if needed."""
    if not claim1.strip() or not claim2.strip():
        return 0.0

    # If embeddings are provided, compute cosine similarity
    if embed1 and embed2:
        return cosine_similarity(embed1, embed2)

    # If embeddings are missing, try fetching them on the fly
    try:
        embeds = await get_claim_embeddings([claim1, claim2])
        if len(embeds) == 2:
            return cosine_similarity(embeds[0], embeds[1])
    except Exception as exc:
        logger.debug("Failed on-the-fly embedding similarity computation: %s", exc)

    # Fallback to string similarity
    return compute_string_similarity(claim1, claim2)
