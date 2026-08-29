"""Low-cost provider diagnostics for production routing.

This module deliberately bypasses gateway fallback/circuit mutation while probing
one concrete provider at a time. It answers the operational question we actually
need during incidents: is the configured credential + concrete model capable of
returning a minimal completion right now?

Enable at process startup with ``PROVIDER_SELF_TEST_ON_STARTUP=true``. Results
are emitted as one structured, secret-free log line that can be inspected from
Render without opening the web UI or using an authenticated admin endpoint.
"""

from __future__ import annotations

import asyncio
import json
import logging
import time
from typing import Any

from llm_errors import classify_provider_exception
from model_gateway.adapters import DirectProviderAdapter, OpenRouterAdapter
from model_gateway.model_map import MODEL_MAP

logger = logging.getLogger("model_gateway.provider_diagnostics")

# Keep this list intentionally aligned with traffic-bearing Arena providers plus
# Mistral (configured in production but not currently part of arena_primary_pool)
# and a couple of OpenRouter candidates. Each call asks for only a handful of
# tokens to minimize cost.
PROBE_MATRIX: tuple[tuple[str, str], ...] = (
    ("openai", "openai_fast"),
    ("anthropic", "anthropic_reasoning"),
    ("gemini", "gemini_general"),
    ("groq", "groq_fast"),
    ("mistral", "mistral_large"),
    ("openrouter", "openrouter_fallback"),
    ("openrouter", "llama-3-free"),
    ("openrouter", "mimo-v2-free"),
)


def _server_key(provider: str) -> str | None:
    from config import settings

    names = {
        "openai": ("OPENAI_API_KEY",),
        "anthropic": ("ANTHROPIC_API_KEY",),
        "gemini": ("GEMINI_API_KEY", "GOOGLE_API_KEY"),
        "groq": ("GROQ_API_KEY",),
        "mistral": ("MISTRAL_API_KEY",),
        "openrouter": ("OPENROUTER_API_KEY",),
    }.get(provider, ())
    for name in names:
        value = getattr(settings, name, None)
        if value:
            return str(value)
    return None


def _safe_failure(exc: Exception) -> tuple[str, str]:
    failure = classify_provider_exception(exc)
    code = failure.code.value if hasattr(failure.code, "value") else str(failure.code)
    # Classifier output is expected to be sanitized; cap it anyway so provider
    # bodies cannot flood logs.
    message = str(failure.message or "Provider probe failed")[:300]
    return code, message


async def _probe_one(provider: str, model_id: str) -> dict[str, Any]:
    record = MODEL_MAP.get(model_id)
    if record is None:
        return {
            "provider": provider,
            "model_id": model_id,
            "configured": False,
            "success": False,
            "error_code": "unknown_model",
            "message": "Model is not present in MODEL_MAP.",
        }

    key = _server_key(provider)
    if not key:
        return {
            "provider": provider,
            "model_id": model_id,
            "litellm_model": record.get("litellm_model"),
            "configured": False,
            "success": False,
            "error_code": "missing_provider_key",
            "message": "Provider key is not configured.",
        }

    adapter = OpenRouterAdapter() if provider == "openrouter" else DirectProviderAdapter()
    started = time.monotonic()
    try:
        result = await asyncio.wait_for(
            adapter.call_llm(
                messages=[{"role": "user", "content": "Reply with exactly: OK"}],
                model_id=model_id,
                temperature=0.0,
                max_tokens=8,
                gateway_policy="direct",
                model_pool="provider_diagnostic",
                routing_policy="isolated-startup-probe",
                user_id=None,
                api_key=key,
            ),
            timeout=20.0,
        )
        latency_ms = round((time.monotonic() - started) * 1000, 1)
        return {
            "provider": provider,
            "model_id": model_id,
            "litellm_model": record.get("litellm_model"),
            "configured": True,
            "success": bool(result.success),
            "latency_ms": latency_ms,
            "response_preview": (result.content or "").strip()[:40] if result.success else None,
            "error_code": None if result.success else (result.error_code or "provider_error"),
            "message": None if result.success else (result.error_message or "Provider call failed")[:300],
        }
    except Exception as exc:
        code, message = _safe_failure(exc)
        return {
            "provider": provider,
            "model_id": model_id,
            "litellm_model": record.get("litellm_model"),
            "configured": True,
            "success": False,
            "latency_ms": round((time.monotonic() - started) * 1000, 1),
            "error_code": code,
            "message": message,
        }


def _routing_summary(results: list[dict[str, Any]]) -> dict[str, Any]:
    by_model = {row["model_id"]: row for row in results}
    arena_order = ["openai_fast", "anthropic_reasoning", "gemini_general", "groq_fast"]
    healthy_arena = [mid for mid in arena_order if by_model.get(mid, {}).get("success")]
    healthy_openrouter = [
        mid
        for mid in ("openrouter_fallback", "llama-3-free", "mimo-v2-free")
        if by_model.get(mid, {}).get("success")
    ]
    healthy_mistral = bool(by_model.get("mistral_large", {}).get("success"))
    return {
        "arena_primary_order": arena_order,
        "healthy_arena_primary": healthy_arena,
        "openrouter_candidates": ["openrouter_fallback", "llama-3-free", "mimo-v2-free"],
        "healthy_openrouter_candidates": healthy_openrouter,
        "mistral_configured_but_not_in_arena_primary": True,
        "mistral_probe_success": healthy_mistral,
        "would_all_models_fail": not healthy_arena and not healthy_openrouter,
    }


async def run_provider_matrix_diagnostic() -> dict[str, Any]:
    """Probe providers concurrently and emit one secret-free structured report."""
    rows = await asyncio.gather(*(_probe_one(provider, model_id) for provider, model_id in PROBE_MATRIX))
    report = {
        "event": "provider_matrix_diagnostic",
        "results": rows,
        "routing": _routing_summary(rows),
    }
    logger.warning("PROVIDER_MATRIX_DIAGNOSTIC %s", json.dumps(report, sort_keys=True))
    return report
