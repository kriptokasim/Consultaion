from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any, List, Optional

from agents import UsageAccumulator, call_llm_for_role
from config import settings
from database import session_scope
from models import Debate, Message
from schemas import PanelConfig, default_panel_config
from sse_backend import get_sse_backend
from prompts.conversation import (
    CONVERSATION_SYSTEM_PROMPT,
    CONVERSATION_SCRIBE_PROMPT,
    CONVERSATION_SYNTHESIS_PROMPT,
)

logger = logging.getLogger(__name__)

async def run_conversation_debate(
    debate: Debate,
    *,
    model_id: str | None,
) -> Any:
    """
    Orchestrate a collaborative conversation mode run.
    """
    # Load config
    panel_payload = debate.panel_config or default_panel_config().model_dump()
    try:
        panel = PanelConfig.model_validate(panel_payload)
    except Exception:
        panel = default_panel_config()

    backend = get_sse_backend()
    usage = UsageAccumulator()
    transcript: List[dict] = []
    
    # Configuration
    num_rounds = 2  # Could be configurable
    
    # Notify start
    await backend.publish(
        f"debate:{debate.id}",
        {"type": "round_started", "debate_id": str(debate.id), "round": 0, "phase": "conversation_start"}
    )

    for round_idx in range(1, num_rounds + 1):
        # Notify round start
        await backend.publish(
            f"debate:{debate.id}",
            {"type": "round_started", "debate_id": str(debate.id), "round": round_idx, "phase": "discussion"}
        )
        
        round_messages = []
        
        for seat in panel.seats:
            # Build context from transcript
            context_text = "\n".join([f"{t['seat']}: {t['content']}" for t in transcript])
            
            messages = [
                {"role": "system", "content": CONVERSATION_SYSTEM_PROMPT},
                {
                    "role": "user", 
                    "content": f"Topic: {debate.prompt}\n\nPrevious discussion:\n{context_text}\n\nYour contribution:"
                }
            ]
            
            try:
                content, call_usage = await call_llm_for_role(
                    messages,
                    role=seat.display_name,
                    temperature=seat.temperature or 0.7,
                    model_override=seat.model,
                    model_id=model_id,
                    debate_id=debate.id,
                    extra_tags={"mode": "conversation"},
                )
                usage.add_call(call_usage)
                
                # Persist message
                with session_scope() as session:
                    session.add(
                        Message(
                            debate_id=debate.id,
                            round_index=round_idx,
                            role="delegate",
                            persona=seat.display_name,
                            content=content,
                            meta={
                                "seat_id": seat.seat_id,
                                "model": seat.model,
                                "mode": "conversation"
                            }
                        )
                    )
                
                # Update transcript
                transcript.append({"seat": seat.display_name, "content": content})
                round_messages.append({"seat": seat.display_name, "content": content})
                
                # Emit event
                await backend.publish(
                    f"debate:{debate.id}",
                    {
                        "type": "seat_message", # Reusing seat_message for compatibility
                        "debate_id": str(debate.id),
                        "round": round_idx,
                        "seat_name": seat.display_name,
                        "content": content,
                        "mode": "conversation"
                    }
                )
                
            except Exception as e:
                logger.error(f"Error in conversation round {round_idx} for seat {seat.display_name}: {e}")
                continue

        # Scribe Summary (Optional, but good for context)
        # For now, we skip explicit scribe step to keep it simple, or we can add it.
        # The user asked for "Round summary (Scribe)".
        
        summary_messages = [
            {"role": "system", "content": CONVERSATION_SCRIBE_PROMPT},
            {"role": "user", "content": f"Topic: {debate.prompt}\n\nRound {round_idx} Transcript:\n" + "\n".join([f"{m['seat']}: {m['content']}" for m in round_messages])}
        ]
        
        try:
            summary_content, summary_usage = await call_llm_for_role(
                summary_messages,
                role="Scribe",
                temperature=0.3,
                model_id=model_id, # Use default or specific model
                debate_id=debate.id,
                extra_tags={"mode": "conversation"},
            )
            usage.add_call(summary_usage)
            
            await backend.publish(
                f"debate:{debate.id}",
                {
                    "type": "conversation_summary",
                    "debate_id": str(debate.id),
                    "round": round_idx,
                    "content": summary_content
                }
            )
            
            # Add summary to transcript for next round context?
            # Maybe just keep full transcript.
            
        except Exception as e:
            logger.error(f"Error generating summary for round {round_idx}: {e}")

    # Final Synthesis
    synthesis_messages = [
        {"role": "system", "content": CONVERSATION_SYNTHESIS_PROMPT},
        {"role": "user", "content": f"Topic: {debate.prompt}\n\nFull Transcript:\n" + "\n".join([f"{t['seat']}: {t['content']}" for t in transcript])}
    ]
    
    final_content = ""
    try:
        final_content, final_usage = await call_llm_for_role(
            synthesis_messages,
            role="Facilitator",
            temperature=0.4,
            model_id=model_id,
            debate_id=debate.id,
            extra_tags={"mode": "conversation"},
        )
        usage.add_call(final_usage)
    except Exception as e:
        logger.error(f"Error generating final synthesis: {e}")
        final_content = "Failed to generate synthesis."

    # Return result structure similar to ParliamentResult
    # We can define a simple object or dict
    
    final_meta = {
        "rounds": num_rounds,
        "transcript_count": len(transcript),
        "usage": usage.snapshot(),
        "mode": "conversation"
    }
    
    return type("ConversationResult", (), {
        "final_answer": final_content,
        "final_meta": final_meta,
        "usage_tracker": usage,
        "status": "completed",
        "error_reason": None
    })
