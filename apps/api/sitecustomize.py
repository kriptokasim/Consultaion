"""Process-start compatibility and opt-in provider diagnostics.

Render starts the API from ``apps/api``, so Python imports ``sitecustomize``
automatically. We use this boundary for two narrowly-scoped purposes:
1) refresh fast-moving free provider model slugs while preserving Consultaion's
   stable persisted model IDs;
2) optionally run a low-cost provider matrix self-test.
"""

from __future__ import annotations

import os
import threading
import time

try:
    from model_gateway.free_model_runtime import install_current_free_model_targets

    install_current_free_model_targets()
except Exception as exc:
    # Model-target installation must be visible if packaging/import order ever
    # changes, but avoid printing secrets/provider bodies at interpreter start.
    print(
        "FREE_MODEL_RUNTIME_INSTALL_FAILED "
        f"error_type={type(exc).__name__}",
        flush=True,
    )


def _enabled() -> bool:
    return os.getenv("PROVIDER_SELF_TEST_ON_STARTUP", "").strip().lower() in {
        "1",
        "true",
        "yes",
        "on",
    }


def _run() -> None:
    # Let application imports/logging/DB startup settle. The diagnostic itself
    # does not need the web server or an authenticated request.
    time.sleep(8)
    try:
        import asyncio

        from model_gateway.provider_diagnostics import run_provider_matrix_diagnostic

        report = asyncio.run(run_provider_matrix_diagnostic())
        print(
            "PROVIDER_SELF_TEST_COMPLETE "
            f"would_all_models_fail={report['routing']['would_all_models_fail']}",
            flush=True,
        )
    except Exception as exc:
        print(
            "PROVIDER_SELF_TEST_BOOTSTRAP_FAILED "
            f"error_type={type(exc).__name__}",
            flush=True,
        )


if _enabled():
    threading.Thread(
        target=_run,
        name="provider-self-test",
        daemon=True,
    ).start()
