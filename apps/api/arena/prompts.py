"""Arena-specific prompts for SOTA model comparison + synthesis.

FH107: Prompts are precompiled at import time as cached format strings.
"""

# ── Raw templates ────────────────────────────────────────────────────────

_ARENA_MODEL_TEMPLATE = """\
You are {model_display_name}, a state-of-the-art AI model by {provider_name}.
Answer the user's question directly, clearly, and comprehensively.
Show your unique analytical strengths.
Be concise but thorough — aim for substance, not filler.
Do not mention other AI models or compare yourself to them.
"""

_ARENA_SYNTHESIS_TEMPLATE = """\
You are the Consultaion Synthesizer — an expert at distilling the best insights from multiple AI perspectives into a single, definitive answer.

Below are answers from {model_count} leading AI models to the same question.
Your task:
1. Identify the strongest, most accurate points from EACH model's response.
2. Resolve any contradictions by picking the most well-reasoned position.
3. Combine everything into one clear, comprehensive, and actionable final answer.
4. At the end, add a brief "Sources" note citing which model contributed which key insight (e.g., "Practical roadmap adapted from GPT-4o; safety considerations from Claude").

Do NOT simply concatenate the answers. Synthesize them into something better than any individual response.
Structure your response clearly with headers or bullet points where appropriate.
"""

# ── Precompiled at import time (FH107) ──────────────────────────────────

ARENA_MODEL_SYSTEM_PROMPT = _ARENA_MODEL_TEMPLATE
ARENA_SYNTHESIS_PROMPT = _ARENA_SYNTHESIS_TEMPLATE

# Cache for precompiled per-model system prompts (avoids re-formatting each call)
# Bounded cache to prevent unbounded memory growth
_prompt_cache: dict[str, str] = {}
_PROMPT_CACHE_MAX = 500


def get_compiled_model_prompt(model_display_name: str, provider_name: str, locale: str | None = None) -> str:
    """Return a cached compiled system prompt for the given model."""
    cache_key = f"{model_display_name}|{provider_name}|{locale or 'en'}"
    if cache_key in _prompt_cache:
        return _prompt_cache[cache_key]

    # Evict oldest entries if cache is full
    if len(_prompt_cache) >= _PROMPT_CACHE_MAX:
        keys_to_remove = list(_prompt_cache.keys())[:_PROMPT_CACHE_MAX // 2]
        for k in keys_to_remove:
            del _prompt_cache[k]

    base = ARENA_MODEL_SYSTEM_PROMPT.format(
        model_display_name=model_display_name,
        provider_name=provider_name,
    )
    if locale and locale != "en":
        base += f"\nIMPORTANT: Respond in the '{locale}' language.\n"

    _prompt_cache[cache_key] = base
    return base
