import logging
from datetime import datetime, timezone

from log_config import log_event
from orchestration.execution_lease import ExecutionSupersededError
from sse_backend import get_sse_backend

from .interfaces import DebateContext, DebatePipeline, DebateState
from .state import DebateStateManager

logger = logging.getLogger(__name__)


def _safe_engine_failure(exc: Exception) -> tuple[str, str]:
    """Return a UI-safe message/code while retaining raw detail in server logs."""
    try:
        from llm_errors import classify_provider_exception

        failure = classify_provider_exception(exc)
        if failure.code.value != "unknown":
            return failure.message, failure.code.value
    except Exception:
        pass
    return "Debate execution failed. Please retry.", "terminal_execution_error"


class DebateRunner:
    """
    Orchestrates the execution of a debate pipeline.
    """
    def __init__(self, pipeline: DebatePipeline, state_manager: DebateStateManager):
        self.pipeline = pipeline
        self.state_manager = state_manager

    async def run(self, context: DebateContext) -> DebateState:
        """
        Run the debate pipeline.
        """
        start_time = datetime.now(timezone.utc)
        backend = get_sse_backend()

        # Initial state
        await self.state_manager.set_status("running")

        try:
            logger.debug("Debate %s: starting pipeline execution", context.debate_id)

            # Execute pipeline
            final_state = await self.pipeline.execute(context)

            if final_state.status == "perspectives_ready":
                await self.state_manager.set_status("perspectives_ready")
                await backend.publish(
                    context.channel_id,
                    {
                        "type": "perspectives_ready",
                        "debate_id": context.debate_id,
                    }
                )
                duration = (datetime.now(timezone.utc) - start_time).total_seconds()
                log_event(
                    "debate.perspectives_ready",
                    debate_id=context.debate_id,
                    user_id=context.user_id,
                    duration_seconds=duration,
                    status=final_state.status,
                )
                return final_state

            # Finalize durably before publishing the terminal payload.
            await self.state_manager.complete_debate(
                final_content=final_state.final_content or "",
                final_meta=final_state.final_meta,
                status=final_state.status,
                tokens_total=float(context.usage_tracker.total_tokens)
            )

            await backend.publish(
                context.channel_id,
                {
                    "type": "final",
                    "debate_id": context.debate_id,
                    "content": final_state.final_content,
                    "meta": final_state.final_meta,
                }
            )

            duration = (datetime.now(timezone.utc) - start_time).total_seconds()
            log_event(
                "debate.completed",
                debate_id=context.debate_id,
                user_id=context.user_id,
                duration_seconds=duration,
                tokens_total=float(context.usage_tracker.total_tokens),
                status=final_state.status,
            )

            return final_state

        except ExecutionSupersededError:
            # Ownership hand-off is not a product failure. The newer worker owns
            # all subsequent state and SSE; do not write "failed" or emit an
            # error event from this stale runner.
            raise
        except Exception as exc:
            logger.exception("Debate %s failed: %s", context.debate_id, exc)
            safe_message, failure_code = _safe_engine_failure(exc)

            await self.state_manager.set_status(
                "failed",
                meta={
                    "error": safe_message,
                    "failure_code": failure_code,
                    "failure_detail_safe": safe_message,
                },
            )

            duration = (datetime.now(timezone.utc) - start_time).total_seconds()
            log_event(
                "debate.failed",
                debate_id=context.debate_id,
                user_id=context.user_id,
                duration_seconds=duration,
                error=safe_message,
                error_type=type(exc).__name__,
            )

            await backend.publish(
                context.channel_id,
                {
                    "type": "error",
                    "debate_id": context.debate_id,
                    "message": safe_message,
                    "failure_code": failure_code,
                },
            )

            raise
