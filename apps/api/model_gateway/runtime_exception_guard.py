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
            """Settle known/unknown provider work without awaiting cancellation-sensitive I/O."""
            active = attempt_context.reservation
            if active is None or not attempt_context.records:
                return
            synthetic = GatewayModelCallResult(
                content="",
                model_used=model_id,
                provider="interrupted",
                success=False,
                error_message="Model execution was interrupted before normal completion.",
                error_code="execution_interrupted",
                model_pool="runtime_exception",
                routing_policy="runtime_exception",
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
                "gateway.interrupted_usage_settled user=%s debate=%s reason=%s attempts=%s tokens=%s cost=%s",
                user_id,
                debate_id,
                reason,
                len(attempt_context.records),
                accounted.total_tokens,
                accounted.cost_usd,
            )

        try:
            try:
                result = await route_call()
            except ProviderAttemptBudgetBlocked as exc:
                # The control signal deliberately bypassed the route's broad
                # provider-error catcher. Earlier attempts may already have
                # spent money; settle them before exposing the real quota error.
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
                    # No provider boundary was crossed: full compensation is safe.
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
                    # A cancellation/exception after provider entry may have
                    # consumed unknown usage. Settle known results and keep the
                    # reserved slice for unknown attempts instead of orphaning it.
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

    # ``agents._raw_llm_call`` used to inspect shared provider circuits before
    # it knew which credential the gateway would use. Keeping that gate would
    # still allow a broken hosted key to block a healthy tenant BYOK key. The
    # gateway now owns this decision after credential resolution, so make the
    # legacy pre-router check deliberately permissive.
    try:
        import agents

        _original_agent_circuit_check = getattr(agents, "is_circuit_open", None)
        agents.is_circuit_open = lambda *_args, **_kwargs: False
    except Exception:
        logger.warning("Could not disable legacy credential-blind circuit gate", exc_info=True)

    _installed = True
