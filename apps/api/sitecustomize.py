"""Opt-in process-start provider diagnostics.

Python imports ``sitecustomize`` automatically when this repository root is on
``sys.path`` (Render starts the API from ``apps/api``). Keeping the hook here
avoids coupling diagnostics to FastAPI routes or administrator authentication.

Nothing happens unless PROVIDER_SELF_TEST_ON_STARTUP is explicitly true.
"""

from __future__ import annotations

import os
import threading
import time


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
        # Never expose provider response bodies or secrets from this bootstrap
        # boundary. Detailed safe per-provider errors are logged by the harness.
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
