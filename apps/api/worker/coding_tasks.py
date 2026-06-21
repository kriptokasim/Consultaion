"""
Celery tasks for executing Coding Agent turns.
Implements the multi-lane routing, early exit, and SSE broadcasting.
"""
import asyncio
import logging
import uuid
import json
from datetime import datetime
from sqlmodel import Session, select
from typing import Dict, Any, List

from worker.celery_app import celery_app
from database import session_scope
from models import CodingRun, CodingTurn, CodingLaneResult, CodingPatchArtifact
from model_gateway.agent_bridge import call_model_via_gateway
from coding_agent.lane_router import classify_tier
from streaming_types import StreamEventType
from sse_backend import get_sse_backend
from metrics import incr_metric, record_timer

logger = logging.getLogger("worker.coding_tasks")

LANE_MODELS = {
    "fast": "groq_fast",
    "thinking": "gemini_general",
    "verifier": "deepinfra_reasoning",
    "judge": "together_general",
}

LANE_TIMEOUTS = {
    "fast": 30,
    "thinking": 60,
    "verifier": 60,
    "judge": 45,
}

# Early exit convergence threshold (similarity)
CONVERGENCE_THRESHOLD = 0.85

def compute_similarity(text1: str, text2: str) -> float:
    """Basic Jaccard-like similarity for convergence check."""
    s1 = set(text1.lower().split())
    s2 = set(text2.lower().split())
    if not s1 and not s2:
        return 1.0
    if not s1 or not s2:
        return 0.0
    return len(s1.intersection(s2)) / len(s1.union(s2))


async def _execute_lane(
    db_session: Session,
    turn: CodingTurn,
    run: CodingRun,
    lane: str,
    prompt: str
) -> CodingLaneResult:
    """Execute a single lane via the model gateway."""
    model_key = LANE_MODELS[lane]
    timeout = LANE_TIMEOUTS[lane]
    
    # Broadcast lane assignment
    sse = get_sse_backend()
    await sse.publish(
        f"run-{run.id}",
        {
            "type": StreamEventType.LANE_ASSIGNED.value,
            "lane_name": lane,
            "model_key": model_key,
            "tier": run.tier,
            "timestamp": datetime.utcnow().isoformat()
        }
    )
    
    # Check idempotency
    existing = db_session.exec(
        select(CodingLaneResult).where(
            CodingLaneResult.coding_run_id == run.id,
            CodingLaneResult.coding_turn_id == turn.id,
            CodingLaneResult.lane_name == lane
        )
    ).first()
    
    if existing and existing.status == "completed":
        return existing

    result_record = existing or CodingLaneResult(
        coding_run_id=run.id,
        coding_turn_id=turn.id,
        lane_name=lane,
        model_key=model_key,
        provider="gateway",
        status="running"
    )
    if not existing:
        db_session.add(result_record)
        db_session.commit()
    
    # Execute through gateway with FREE_ONLY_MODE guard
    start_time = datetime.utcnow()
    try:
        # Send thinking/planning start event
        await sse.publish(
            f"run-{run.id}",
            {
                "type": StreamEventType.AGENT_PROGRESS_DELTA.value,
                "lane": lane,
                "model_id": model_key,
                "phase": "planning",
                "text": "Starting analysis...",
                "sequence": 1,
                "timestamp": datetime.utcnow().isoformat()
            }
        )

        content, usage = await asyncio.wait_for(
            call_model_via_gateway(
                messages=[{"role": "user", "content": prompt}],
                model_id=model_key,
                role="coding_agent",
                user_id=run.user_id,
                db_session=db_session
            ),
            timeout=timeout
        )
        
        result_record.status = "completed"
        result_record.content = content
        result_record.token_usage = {
            "prompt": usage.prompt_tokens,
            "completion": usage.completion_tokens,
            "total": usage.total_tokens
        }
        
    except asyncio.TimeoutError:
        result_record.status = "failed"
        result_record.error = "Lane execution timed out"
        incr_metric("coding.lane_failure_count", tags={"lane": lane, "reason": "timeout"})
    except Exception as e:
        result_record.status = "failed"
        result_record.error = str(e)
        if "free-only mode" in str(e).lower():
            incr_metric("coding.free_only_block_count", tags={"lane": lane, "model": model_key})
        incr_metric("coding.lane_failure_count", tags={"lane": lane, "reason": "error"})
        
    result_record.completed_at = datetime.utcnow()
    latency_ms = (result_record.completed_at - start_time).total_seconds() * 1000
    result_record.latency_ms = latency_ms
    db_session.commit()
    
    record_timer("coding.lane_latency_ms", latency_ms, tags={"lane": lane})
    
    return result_record


async def _async_execute_turn(run_id: str, turn_id: str):
    """Async implementation of the turn execution."""
    sse = get_sse_backend()
    
    with session_scope() as db:
        run = db.get(CodingRun, run_id)
        turn = db.get(CodingTurn, turn_id)
        if not run or not turn:
            return
            
        tier_res = classify_tier(run.file_paths or [], turn.prompt)
        run.tier = tier_res.tier
        db.commit()
        
        # Execute active lanes concurrently (except judge)
        tasks = []
        for lane in tier_res.active_lanes:
            if lane != "judge":
                tasks.append(_execute_lane(db, turn, run, lane, turn.prompt))
                
        results = await asyncio.gather(*tasks)
        results_by_lane = {r.lane_name: r for r in results}
        
        final_content = None
        judge_skipped = False
        
        # Convergence logic
        if "fast" in results_by_lane and "thinking" in results_by_lane:
            fast_res = results_by_lane["fast"]
            think_res = results_by_lane["thinking"]
            
            if fast_res.status == "completed" and think_res.status == "completed":
                sim = compute_similarity(fast_res.content or "", think_res.content or "")
                
                await sse.publish(
                    f"run-{run.id}",
                    {
                        "type": StreamEventType.LANE_CONVERGENCE_CHECKED.value,
                        "similarity_score": sim,
                        "threshold": CONVERGENCE_THRESHOLD,
                        "early_exit": sim >= CONVERGENCE_THRESHOLD,
                        "judge_skipped": sim >= CONVERGENCE_THRESHOLD,
                        "source": "fast_vs_thinking",
                        "timestamp": datetime.utcnow().isoformat()
                    }
                )
                
                if sim >= CONVERGENCE_THRESHOLD:
                    judge_skipped = True
                    final_content = fast_res.content
                    incr_metric("coding.early_exit_rate", tags={"tier": run.tier})
                    
        # Fallback to judge if no early exit and tier requires it
        if not judge_skipped and "judge" in tier_res.active_lanes:
            incr_metric("coding.judge_invoked_count", tags={"tier": run.tier})
            
            # Construct judge prompt
            judge_prompt = f"Evaluate the following proposals for this task:\n\nTask: {turn.prompt}\n\n"
            for lane, res in results_by_lane.items():
                if res.status == "completed":
                    judge_prompt += f"--- {lane.upper()} PROPOSAL ---\n{res.content}\n\n"
            judge_prompt += "Provide the final unified patch."
            
            judge_res = await _execute_lane(db, turn, run, "judge", judge_prompt)
            if judge_res.status == "completed":
                final_content = judge_res.content
            else:
                # Absolute fallback
                final_content = results_by_lane.get("fast", judge_res).content
                
        if not final_content and "fast" in results_by_lane:
            final_content = results_by_lane["fast"].content
            
        # Store artifact
        if final_content:
            artifact = CodingPatchArtifact(
                coding_run_id=run.id,
                coding_turn_id=turn.id,
                final_patch=final_content
            )
            db.add(artifact)
            
        turn.status = "completed"
        turn.completed_at = datetime.utcnow()
        run.status = "completed"
        run.completed_at = datetime.utcnow()
        db.commit()


@celery_app.task(name="coding.execute_turn")
def execute_turn(run_id: str, turn_id: str):
    """Celery task entrypoint."""
    asyncio.run(_async_execute_turn(run_id, turn_id))
