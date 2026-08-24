from __future__ import annotations

import asyncio
import logging

from orchestration.state import DebateStateManager

logger = logging.getLogger(__name__)
_installed = False
_original_complete_debate = DebateStateManager.complete_debate


def install_terminal_accounting_guard() -> None:
    """Make product terminal state authoritative before accounting side effects."""
    global _installed
    if _installed:
        return

    async def complete_debate_after_commit(
        self: DebateStateManager,
        final_content: str,
        final_meta: dict,
        status: str,
        tokens_total: float = 0.0,
    ) -> None:
        user_id = self.user_id
        # The original implementation commits Debate + DebateAttempt correctly,
        # but performs token-ledger work before that commit. Suppress only that
        # internal side effect; preserve all state/checkpoint logic unchanged.
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
        if not user_id or tokens <= 0:
            return

        def _record_and_settle() -> None:
            from database import session_scope
            from services.usage_ledger import record_token_usage, settle_token_usage

            with session_scope() as session:
                entry = record_token_usage(
                    session,
                    user_id=user_id,
                    debate_id=self.debate_id,
                    attempt_id=self.attempt_id,
                    tokens=tokens,
                )
                if entry.status in {"reserved", "settlement_pending", "reconciliation_pending"}:
                    settle_token_usage(
                        session,
                        user_id=user_id,
                        debate_id=self.debate_id,
                        attempt_id=self.attempt_id,
                    )

        try:
            await asyncio.get_running_loop().run_in_executor(None, _record_and_settle)
        except Exception:
            # Debate/attempt terminal state is already durable. Reconciliation is
            # idempotent by (debate_id, attempt_id) and may safely retry later.
            logger.exception("Failed to settle token usage for debate %s", self.debate_id)

    DebateStateManager.complete_debate = complete_debate_after_commit  # type: ignore[method-assign]
    _installed = True
