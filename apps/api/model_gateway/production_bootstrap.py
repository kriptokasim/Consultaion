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
_install_lock = threading.Lock()
_bootstrap_failed = False
_bootstrap_error: str | None = None


def is_installed() -> bool:
    """Whether the runtime free-model targets are live in this process."""
    from model_gateway.free_model_runtime import is_installed as runtime_is_installed

    return runtime_is_installed()


def bootstrap_failed() -> bool:
    """Whether the last install attempt failed and left paid static fallbacks live.

    Health endpoints read this together with :func:`is_installed`: an uninstalled
    runtime routes traffic to the static paid upstreams, so it is not healthy.
    """
    return _bootstrap_failed


def bootstrap_error() -> str | None:
    """Last install failure description, or None if the last attempt succeeded."""
    return _bootstrap_error


def install_production_model_targets_now(*, source: str = "startup_hook") -> bool:
    """Install the runtime free-model targets synchronously and return success.

    This is the FastAPI startup-hook entry point. Call it from the lifespan
    handler before the application accepts traffic: until it has run, model
    resolution falls through the un-patched static mapping to real paid
    upstreams. It is idempotent and thread-safe, so calling it twice — or
    alongside :func:`start_production_model_bootstrap` — is a no-op after the
    first success, and a failed attempt can simply be retried.
    """
    global _bootstrap_failed, _bootstrap_error

    with _install_lock:
        from model_gateway.free_model_runtime import (
            install_current_free_model_targets,
            is_installed as runtime_is_installed,
        )

        if runtime_is_installed():
            _bootstrap_failed = False
            _bootstrap_error = None
            return True

        try:
            install_current_free_model_targets()
        except Exception as exc:
            _bootstrap_failed = True
            _bootstrap_error = f"{type(exc).__name__}: {exc}"
            logger.exception(
                "FREE_MODEL_RUNTIME_BOOTSTRAP_FAILED source=%s error_type=%s",
                source,
                type(exc).__name__,
            )
            return False

        _bootstrap_failed = False
        _bootstrap_error = None
        logger.warning("FREE_MODEL_RUNTIME_BOOTSTRAPPED source=%s", source)
        return True


def start_production_model_bootstrap() -> None:
    """Schedule runtime installation after Python's import graph settles."""
    global _started
    if _started:
        return
    _started = True

    def _worker() -> None:
        global _started

        # adapters imports llm_errors, so bootstrap must never run synchronously
        # from llm_errors itself. Five seconds is intentionally conservative and
        # still happens before normal user traffic in a healthy Render boot.
        # install_production_model_targets_now() is the gated startup path; this
        # thread is the legacy safety net for entrypoints that do not call it.
        time.sleep(5)
        if not install_production_model_targets_now(source="application_import"):
            # Leave the door open for another caller (lifespan hook, retry) to
            # install rather than latching this process onto paid fallbacks.
            _started = False
            return

        app_env = os.getenv("APP_ENV", os.getenv("ENV", "production")).lower()
        enabled = os.getenv("PROVIDER_SELF_TEST_ON_STARTUP", "").strip().lower() in {"1", "true", "yes", "on"}
        if app_env not in {"production", "staging"} and not enabled:
            return

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

    threading.Thread(target=_worker, name="provider-runtime-bootstrap", daemon=True).start()
