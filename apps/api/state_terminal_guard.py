from __future__ import annotations

import asyncio
import logging

from orchestration.state import DebateStateManager

logger = logging.getLogger(__name__)
_installed = False
_original_complete_debate = DebateStateManager.complete_debate


def install_terminal_accounting_guard() -> None:
    """Install terminal, ownership, recovery, quota, and gateway accounting guards."""
    global _installed
    if _installed:
        return

    # Install cross-cutting runtime guards before execution/cleanup begins.
    # Order matters: terminal reconciliation wraps the already-hardened stale
    # cleanup function installed immediately before it.
    from checkpoint_runtime_guard import install_checkpoint_runtime_guard
    from cleanup_recovery_guard import install_cleanup_recovery_guard
    from model_gateway.runtime_exception_guard import install_runtime_exception_guard
    from model_gateway.runtime_guard import install_gateway_runtime_guard
    from retry_accounting_guard import install_retry_accounting_guard
    from retry_presentation_guard import install_retry_presentation_guard
    from sse_execution_guard import install_sse_execution_guard
    from terminal_accounting_reconciler import install_terminal_accounting_reconciler

    install_checkpoint_runtime_guard()
    install_sse_execution_guard()
    install_gateway_runtime_guard()
    install_runtime_exception_guard()
    install_retry_accounting_guard()
    install_retry_presentation_guard()
    install_cleanup_recovery_guard()
    install_terminal_accounting_reconciler()

    async def complete_debate_after_commit(
        self: DebateStateManager,
        final_content: str,
        final_meta: dict,
        status: str,
        tokens_total: float = 0.0,
    ) -> None:
        user_id = self.user_id
        # Keep terminal product state authoritative before accounting side
        # effects. Suppress the original method's ledger side effect while
        # preserving its Debate/Attempt/checkpoint transaction.
        self.user_id = None
        try:
            await _original_complete_debate(
                self,
                final_content=final_content,
                final_meta=final_meta,
                status=status,
                tokens_total=tokens_total,
            )
        finally:
            self.user_id = user_id

        tokens = max(int(tokens_total), 0)
        if not user_id or tokens <= 0 or not self.attempt_id:
            return

        def _record_settle_and_apply_quota() -> None:
            from database import session_scope
            from models import Debate, DebateAttempt
            from terminal_accounting_reconciler import ensure_token_accounting_once

            with session_scope() as session:
                debate = session.get(Debate, self.debate_id)
                attempt = session.get(DebateAttempt, self.attempt_id)
                if debate is None or attempt is None:
                    raise RuntimeError(
                        "Terminal token accounting lost its durable debate/attempt identity"
                    )
                ensure_token_accounting_once(
                    session,
                    debate=debate,
                    attempt=attempt,
                )

        try:
            await asyncio.get_running_loop().run_in_executor(
                None,
                _record_settle_and_apply_quota,
            )
        except Exception:
            logger.exception("Failed to finalize token accounting for debate %s", self.debate_id)

    DebateStateManager.complete_debate = complete_debate_after_commit  # type: ignore[method-assign]
    _installed = True
