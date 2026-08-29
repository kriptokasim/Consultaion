"""Exception and credential-scope hardening for the gateway runtime boundary.

Reservations are created before provider routing. Before any adapter boundary,
an exception is known to have incurred no provider spend and the reservation is
released. After at least one adapter attempt, interruption is different: provider
work may already have consumed tokens/cost. In that case the durable reservation
is settled from known attempt results, retaining the conservative slice for any
attempt whose usage metadata is unavailable. This avoids both silent spend loss
and permanently orphaned ``reserved`` quota after cancellation/fallback blocks.

The legacy Agent layer also performed a shared circuit-breaker check before the
Model Gateway resolved whether the concrete credential was hosted/server or
user BYOK. That credential-blind gate is disabled here: the gateway route is the
single circuit authority and evaluates circuit state only after credential scope
has been resolved.
"""

from __future__ import annotations

import logging

logger = logging.getLogger(__name__)
_installed = False
_original_agent_circuit_check = None


def install_runtime_exception_guard() -> None:
    """Install crash-safe reservation cleanup and credential-scoped circuit authority."""
    global _installed, _original_agent_circuit_check
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
            ProviderAttemptBudgetBlocked,
            aggregate_accounting_result,
            bind_attempt_context,
            reset_attempt_context,
        )
        from model_gateway.costs import bind_cost_reservation, reset_cost_reservation
        from model_gateway.reservations import (
            release_gateway_budget_sync,
            settle_gateway_budget_sync,
        )
        from model_gateway.types import GatewayModelCallResult, GatewayQuotaExceededError

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

        def _settle_interrupted_attempts(reason: str) -> None:
            """Settle known/unknown provider work without cancellation-sensitive awaits."""
            active = attempt_context.reservation
            if active is None or not attempt_context.records:
                return

            last_known = next(
                (
                    record.result
                    for record in reversed(attempt_context.records)
                    if record.result is not None
                ),
                None,
            )
            synthetic = GatewayModelCallResult(
                content="",
                model_used=(last_known.model_used if last_known is not None else model_id),
                provider=(last_known.provider if last_known is not None else "interrupted"),
                success=False,
                error_message="Model execution was interrupted before normal completion.",
                error_code="execution_interrupted",
                model_pool=(last_known.model_pool if last_known is not None else "runtime_exception"),
                routing_policy=(
                    last_known.routing_policy if last_known is not None else "runtime_exception"
                ),
                fallback_used=bool(last_known.fallback_used) if last_known is not None else False,
                fallback_reason=(last_known.fallback_reason if last_known is not None else None),
                retry_count=(int(last_known.retry_count or 0) if last_known is not None else 0),
                user_plan=user_plan,
            )
            accounted = aggregate_accounting_result(synthetic, attempt_context)
            settle_gateway_budget_sync(
                active,
                result=accounted,
                safe_error_message="Model execution was interrupted before normal completion.",
            )
            attempt_context.reservation = None
            logger.warning(
                "gateway.interrupted_usage_settled user=%s debate=%s reason=%s attempts=%s tokens=%s cost=%s provider=%s",
                user_id,
                debate_id,
                reason,
                len(attempt_context.records),
                accounted.total_tokens,
                accounted.cost_usd,
                accounted.provider,
            )

        try:
            try:
                result = await route_call()
            except ProviderAttemptBudgetBlocked as exc:
                try:
                    _settle_interrupted_attempts("provider_attempt_budget_blocked")
                except Exception:
                    logger.exception(
                        "gateway.interrupted_usage_settlement_failed user=%s debate=%s",
                        user_id,
                        debate_id,
                    )
                raise GatewayQuotaExceededError(str(exc)) from exc
            except BaseException as exc:
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
                elif attempt_context.records and attempt_context.reservation is not None:
                    try:
                        _settle_interrupted_attempts(type(exc).__name__)
                    except Exception:
                        logger.exception(
                            "gateway.interrupted_usage_settlement_failed user=%s debate=%s",
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
            release_gateway_budget_sync(
                active_reservation,
                reason=result.error_code or "no_provider_attempt",
            )
            return result, estimate, None

        aggregated = aggregate_accounting_result(result, attempt_context)
        return aggregated, estimate, active_reservation

    runtime_guard._execute_guarded_route = _execute_guarded_route_hardened

    try:
        import agents

        _original_agent_circuit_check = getattr(agents, "is_circuit_open", None)
        agents.is_circuit_open = lambda *_args, **_kwargs: False
    except Exception:
        logger.warning("Could not disable legacy credential-blind circuit gate", exc_info=True)

    _installed = True
