from __future__ import annotations

import logging
from typing import Any

from database_async import async_session_scope
from models import Debate
from sse_backend import SSEBackendProvider

logger = logging.getLogger(__name__)


class TerminalCommitGuard:
    """Suppress only Arena engine failure evidence published before DB commit."""

    def __init__(self, backend: Any) -> None:
        self._backend = backend

    def __getattr__(self, name: str) -> Any:
        return getattr(self._backend, name)

    async def publish(self, channel_id: str, event: dict) -> None:
        # The known offending engine event uniquely carries this reason. Other
        # debate_failed publishers retain their existing behavior.
        if (
            event.get("type") == "debate_failed"
            and event.get("reason") == "all_models_failed"
        ):
            debate_id = str(event.get("debate_id") or "")
            if not debate_id and channel_id.startswith("debate:"):
                debate_id = channel_id.split(":", 1)[1]
            if debate_id:
                try:
                    async with async_session_scope() as session:
                        debate = await session.get(Debate, debate_id)
                        if debate is not None and debate.mode == "arena":
                            if debate.status != "failed":
                                logger.warning(
                                    "Suppressed premature Arena debate_failed event debate=%s status=%s",
                                    debate_id,
                                    debate.status,
                                )
                                try:
                                    from metrics import increment_metric

                                    increment_metric("arena.terminal.premature_suppressed")
                                except Exception:
                                    pass
                                return
                except Exception:
                    # Without durable-state evidence, never expose the engine's
                    # premature terminal signal. The orchestrator will publish
                    # the authoritative terminal after persistence succeeds.
                    logger.exception(
                        "Could not verify Arena terminal commit; suppressing engine event debate=%s",
                        debate_id,
                    )
                    return
        await self._backend.publish(channel_id, event)


_installed = False
_original_provider_get = SSEBackendProvider.get


def install_terminal_commit_guard() -> None:
    """Wrap every provider-created backend, including instances after test reset."""
    global _installed
    if _installed:
        return

    def guarded_get(provider: SSEBackendProvider):
        backend = _original_provider_get(provider)
        if isinstance(backend, TerminalCommitGuard):
            return backend
        wrapped = TerminalCommitGuard(backend)
        provider._backend = wrapped
        return wrapped

    SSEBackendProvider.get = guarded_get  # type: ignore[method-assign]
    _installed = True
