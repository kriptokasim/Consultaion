"""Exception-path hardening for the gateway reservation boundary.

The main runtime guard reserves cost/tokens before routing. Any exception or
cancellation that occurs before the first adapter attempt is therefore known to
have performed no provider work and must release that reservation. Once an
adapter attempt exists, accounting intentionally remains fail-closed because the
provider may already have consumed tokens/cost.
"""

from __future__ import annotations

import logging

logger = logging.getLogger(__name__)
_installed = False


def install_runtime_exception_guard() -> None:
    """Replace ``runtime_guard._execute_guarded_route`` with crash-safe cleanup."""
    global _installed
    if _installed:
        return

    import model_gateway.runtime_guard as runtime_guard

    async def _execute_guarded_route_hardened(
        *,
        route_call,
        user_id: str | None,
        debate_id: str | None,
        model_id: str,
        role: str | None,
        user_plan: str | None,
        messages: list[dict],
        max_tokens: int,
    ):
        from model_gateway.attempt_tracker import (
            GatewayAttemptContext,
            aggregate_accounting_result,
            bind_attempt_context,
            reset_attempt_context,
        )
        from model_gateway.costs import bind_cost_reservation, reset_cost_reservation
        from model_gateway.reservations import release_gateway_budget_sync

        estimate, token_estimate, reservation = await runtime_guard._reserve_budget(
            user_id=user_id,
            debate_id=debate_id,
            model_id=model_id,
            role=role,
            user_plan=user_plan,
            messages=messages,
            max_tokens=max_tokens,
        )
        attempt_context = GatewayAttemptContext(
            user_id=user_id,
            debate_id=debate_id,
            user_plan=user_plan,
            role=role,
            initial_cost_usd=estimate,
            initial_tokens=token_estimate,
            reservation=reservation,
        )
        attempt_token = bind_attempt_context(attempt_context)
        cost_token = (
            bind_cost_reservation(user_id, reservation.reserved_cost_usd)
            if reservation is not None and user_id
            else None
        )

        try:
            try:
                result = await route_call()
            except BaseException as exc:
                # No adapter record means no provider boundary was crossed. Do
                # the compensation synchronously before propagating even a
                # CancelledError; cancellation must not orphan a user charge.
                if not attempt_context.records and attempt_context.reservation is not None:
                    try:
                        release_gateway_budget_sync(
                            attempt_context.reservation,
                            reason=type(exc).__name__,
                        )
                        attempt_context.reservation = None
                    except Exception:
                        logger.exception(
                            "gateway.preprovider_reservation_release_failed user=%s debate=%s",
                            user_id,
                            debate_id,
                        )
                raise
        finally:
            if cost_token is not None:
                reset_cost_reservation(cost_token)
            reset_attempt_context(attempt_token)

        active_reservation = attempt_context.reservation
        if not attempt_context.records and active_reservation is not None:
            # Friendly circuit/missing-key/validation results also prove that no
            # adapter ran, so their reservation is compensation-safe.
            release_gateway_budget_sync(
                active_reservation,
                reason=result.error_code or "no_provider_attempt",
            )
            return result, estimate, None

        aggregated = aggregate_accounting_result(result, attempt_context)
        return aggregated, estimate, active_reservation

    runtime_guard._execute_guarded_route = _execute_guarded_route_hardened
    _installed = True
