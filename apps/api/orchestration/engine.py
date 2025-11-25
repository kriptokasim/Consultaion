import logging
import asyncio
from datetime import datetime, timezone
from typing import Optional

from sse_backend import get_sse_backend
from .interfaces import DebateContext, DebatePipeline, DebateState
from .state import DebateStateManager
from log_config import log_event

logger = logging.getLogger(__name__)


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
        self.state_manager.set_status("running")
        
        try:
            logger.debug("Debate %s: starting pipeline execution", context.debate_id)
            
            # Execute pipeline
            final_state = await self.pipeline.execute(context)
            
            # Finalize
            self.state_manager.complete_debate(
                final_content=final_state.final_content or "",
                final_meta=final_state.final_meta,
                status=final_state.status,
                tokens_total=float(context.usage_tracker.total_tokens)
            )
            
            # Publish final event
            await backend.publish(
                context.channel_id,
                {
                    "type": "final",
                    "debate_id": context.debate_id,
                    "content": final_state.final_content,
                    "meta": final_state.final_meta,
                }
            )
            
            # Log completion
            duration = (datetime.now(timezone.utc) - start_time).total_seconds()
            log_event(
                "debate.completed",
                debate_id=context.debate_id,
                user_id=context.config.get("user_id"), # Assuming user_id is in config or context
                duration_seconds=duration,
                tokens_total=float(context.usage_tracker.total_tokens),
                status=final_state.status,
            )
            
            return final_state

        except Exception as exc:
            logger.exception("Debate %s failed: %s", context.debate_id, exc)
            
            # Record failure
            self.state_manager.set_status("failed", meta={"error": str(exc)})
            
            # Log failure
            duration = (datetime.now(timezone.utc) - start_time).total_seconds()
            log_event(
                "debate.failed",
                debate_id=context.debate_id,
                user_id=context.config.get("user_id"),
                duration_seconds=duration,
                error=str(exc),
                error_type=type(exc).__name__,
            )
            
            # Notify frontend
            await backend.publish(
                context.channel_id,
                {"type": "error", "debate_id": context.debate_id, "message": str(exc)},
            )
            
            raise
