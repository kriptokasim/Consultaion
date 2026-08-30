"""Production-safe model runtime bootstrap.

Render does not guarantee Python's sitecustomize hook is loaded from the API
working directory. The application therefore needs a normal import-time hook
for fast-moving free model aliases and a tiny provider smoke test.
"""
from __future__ import annotations

import asyncio
import logging
import os
import threading
import time

logger = logging.getLogger("model_gateway.production_bootstrap")
_started = False


def start_production_model_bootstrap() -> None:
    """Install free model aliases and optionally run one real free smoke test."""
    global _started
    if _started:
        return
    _started = True

    try:
        from model_gateway.free_model_runtime import install_current_free_model_targets
        install_current_free_model_targets()
        logger.warning("FREE_MODEL_RUNTIME_BOOTSTRAPPED source=application_import")
    except Exception as exc:
        logger.exception("FREE_MODEL_RUNTIME_BOOTSTRAP_FAILED error_type=%s", type(exc).__name__)
        return

    # Always smoke-test the real free hosted route in production. This is a
    # single minimal request, bounded to 15s, and never touches paid providers.
    app_env = os.getenv("APP_ENV", os.getenv("ENV", "production")).lower()
    enabled = os.getenv("PROVIDER_SELF_TEST_ON_STARTUP", "").strip().lower() in {"1", "true", "yes", "on"}
    if app_env not in {"production", "staging"} and not enabled:
        return

    def _worker() -> None:
        time.sleep(5)
        try:
            from model_gateway.provider_diagnostics import run_provider_matrix_diagnostic
            report = asyncio.run(run_provider_matrix_diagnostic())
            logger.warning(
                "PROVIDER_SELF_TEST_COMPLETE would_all_models_fail=%s healthy_openrouter=%s",
                report["routing"]["would_all_models_fail"],
                report["routing"]["healthy_openrouter_candidates"],
            )
        except Exception as exc:
            logger.exception("PROVIDER_SELF_TEST_BOOTSTRAP_FAILED error_type=%s", type(exc).__name__)

    threading.Thread(target=_worker, name="provider-self-test", daemon=True).start()
