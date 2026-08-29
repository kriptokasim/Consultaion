"""Environment hardening for checkpoint lease requirements.

The canonical checkpoint implementation historically failed closed without an
ExecutionLease only when APP_ENV == "production". Staging is a distributed,
production-like environment too; allowing active stages to fall into the
unfenced legacy path there makes takeover/race bugs invisible before release.
This runtime guard keeps explicit post-terminal ``allow_unfenced=True`` support
while enforcing lease ownership for active stages in both production and staging.
"""

from __future__ import annotations

import logging

logger = logging.getLogger(__name__)
_installed = False
_original_resolve_lease = None


def install_checkpoint_runtime_guard() -> None:
    global _installed, _original_resolve_lease
    if _installed:
        return

    import orchestration.checkpoints as checkpoints
    from config import settings
    from orchestration.execution_context import get_current_execution_lease

    _original_resolve_lease = checkpoints._resolve_lease

    def _resolve_lease_hardened(execution_lease, allow_unfenced: bool = False):
        lease = execution_lease or get_current_execution_lease()
        if lease is None and settings.APP_ENV in {"production", "staging"}:
            if allow_unfenced:
                return None
            raise RuntimeError(
                "run_with_checkpoint requires an ExecutionLease in production/staging "
                "(pass execution_lease= or bind one via execution_context)."
            )
        return lease

    checkpoints._resolve_lease = _resolve_lease_hardened
    _installed = True
    logger.info("checkpoint.runtime_guard_installed")
