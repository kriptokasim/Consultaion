"""Semantic claim similarity helper.

Uses litellm embeddings to compute semantic cosine similarity between claims.
Includes a robust fallback to token overlap & SequenceMatcher string similarity
in case embedding calls fail or keys are missing.
"""

from __future__ import annotations

import difflib
import logging
import math
from typing import List

from config import settings
from litellm import aembedding

logger = logging.getLogger(__name__)


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
    try:
        # We wrap in try-except to ensure fallback if API keys are missing or call fails
        response = await aembedding(
            model=model_name,
            input=claims,
        )
        return [data["embedding"] for data in response["data"]]
    except Exception as exc:
        logger.warning(
            "Embedding API call failed for model %s. Falling back to string similarity. Error: %s",
            model_name,
            exc,
        )
        return []


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
