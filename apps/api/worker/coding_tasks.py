"""
Celery tasks for executing Coding Agent turns.
Implements the multi-lane routing, early exit, and SSE broadcasting.
"""
import asyncio
import logging
from dataclasses import dataclass
from datetime import datetime, timezone

from coding_agent.lane_router import classify_tier
from database import session_scope
from metrics import incr_metric, record_timer
from model_gateway.agent_bridge import call_model_via_gateway
from models import CodingLaneResult, CodingPatchArtifact, CodingRun, CodingTurn
from sqlmodel import select
from sse_backend import get_sse_backend
from streaming_types import StreamEventType

from worker.celery_app import celery_app

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


@dataclass(frozen=True)
class LaneExecutionResult:
    """Detached immutable view returned from one independently-scoped lane."""

    lane_name: str
    model_key: str
    status: str
    content: str | None
    error: str | None


def _lane_snapshot(record: CodingLaneResult) -> LaneExecutionResult:
    return LaneExecutionResult(
        lane_name=record.lane_name,
        model_key=record.model_key,
        status=record.status,
        content=record.content,
        error=record.error,
    )


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
    run_id: str,
    turn_id: str,
    lane: str,
    prompt: str,
    *,
    run_tier: int,
    user_id: str,
) -> LaneExecutionResult:
    """Execute one lane using a lane-local SQLModel Session.

    SQLAlchemy/SQLModel sessions are not safe for concurrent use. Each lane is
    gathered concurrently, so sharing the parent turn session lets one lane's
    query/commit race another lane's transaction. A dedicated session per lane
    keeps transaction ownership explicit and prevents random flush/rollback
    cross-talk under real multi-lane traffic.
    """
    model_key = LANE_MODELS[lane]
    timeout = LANE_TIMEOUTS[lane]

    sse = get_sse_backend()
    await sse.publish(
        f"run-{run_id}",
        {
            "type": StreamEventType.LANE_ASSIGNED.value,
            "lane_name": lane,
            "model_key": model_key,
            "tier": run_tier,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        },
    )

    start_time = datetime.now(timezone.utc)
    with session_scope() as db_session:
        existing = db_session.exec(
            select(CodingLaneResult).where(
                CodingLaneResult.coding_run_id == run_id,
                CodingLaneResult.coding_turn_id == turn_id,
                CodingLaneResult.lane_name == lane,
            )
        ).first()

        if existing and existing.status == "completed":
            return _lane_snapshot(existing)

        result_record = existing or CodingLaneResult(
            coding_run_id=run_id,
            coding_turn_id=turn_id,
            lane_name=lane,
            model_key=model_key,
            provider="gateway",
            status="running",
        )
        if not existing:
            db_session.add(result_record)
            # Persist the idempotency row before the provider call. The unique
            # constraint on (run, turn, lane) remains the database authority.
            db_session.commit()

        try:
            await sse.publish(
                f"run-{run_id}",
                {
                    "type": StreamEventType.AGENT_PROGRESS_DELTA.value,
                    "lane": lane,
                    "model_id": model_key,
                    "phase": "planning",
                    "text": "Starting analysis...",
                    "sequence": 1,
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                },
            )

            content, usage = await asyncio.wait_for(
                call_model_via_gateway(
                    messages=[{"role": "user", "content": prompt}],
                    model_id=model_key,
                    role="coding_agent",
                    user_id=user_id,
                    db_session=db_session,
                ),
                timeout=timeout,
            )

            result_record.status = "completed"
            result_record.content = content
            result_record.error = None
            result_record.token_usage = {
                "prompt": usage.prompt_tokens,
                "completion": usage.completion_tokens,
                "total": usage.total_tokens,
            }
        except asyncio.TimeoutError:
            result_record.status = "failed"
            result_record.error = "Lane execution timed out"
            incr_metric("coding.lane_failure_count", tags={"lane": lane, "reason": "timeout"})
        except Exception as exc:
            result_record.status = "failed"
            result_record.error = str(exc)
            if "free-only mode" in str(exc).lower():
                incr_metric("coding.free_only_block_count", tags={"lane": lane, "model": model_key})
            incr_metric("coding.lane_failure_count", tags={"lane": lane, "reason": "error"})

        result_record.completed_at = datetime.now(timezone.utc)
        latency_ms = (result_record.completed_at - start_time).total_seconds() * 1000
        result_record.latency_ms = latency_ms
        db_session.add(result_record)
        db_session.commit()

        record_timer("coding.lane_latency_ms", latency_ms, tags={"lane": lane})
        return _lane_snapshot(result_record)


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
        db.add(run)
        db.commit()

        # Snapshot scalar inputs before concurrent work. ORM objects and this
        # parent Session stay on the coordinating coroutine only.
        prompt = turn.prompt
        run_tier = run.tier
        user_id = run.user_id

        tasks = []
        for lane in tier_res.active_lanes:
            if lane != "judge":
                tasks.append(
                    _execute_lane(
                        run.id,
                        turn.id,
                        lane,
                        prompt,
                        run_tier=run_tier,
                        user_id=user_id,
                    )
                )

        results = await asyncio.gather(*tasks)
        results_by_lane = {result.lane_name: result for result in results}

        final_content = None
        judge_skipped = False

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
                        "timestamp": datetime.now(timezone.utc).isoformat(),
                    },
                )

                if sim >= CONVERGENCE_THRESHOLD:
                    judge_skipped = True
                    final_content = fast_res.content
                    incr_metric("coding.early_exit_rate", tags={"tier": run.tier})

        if not judge_skipped and "judge" in tier_res.active_lanes:
            incr_metric("coding.judge_invoked_count", tags={"tier": run.tier})

            judge_prompt = f"Evaluate the following proposals for this task:\n\nTask: {prompt}\n\n"
            for lane, res in results_by_lane.items():
                if res.status == "completed":
                    judge_prompt += f"--- {lane.upper()} PROPOSAL ---\n{res.content}\n\n"
            judge_prompt += "Provide the final unified patch."

            judge_res = await _execute_lane(
                run.id,
                turn.id,
                "judge",
                judge_prompt,
                run_tier=run_tier,
                user_id=user_id,
            )
            if judge_res.status == "completed":
                final_content = judge_res.content
            else:
                fast_fallback = results_by_lane.get("fast")
                final_content = fast_fallback.content if fast_fallback else None

        if not final_content and "fast" in results_by_lane:
            final_content = results_by_lane["fast"].content

        if final_content:
            artifact = db.exec(
                select(CodingPatchArtifact).where(
                    CodingPatchArtifact.coding_run_id == run.id,
                    CodingPatchArtifact.coding_turn_id == turn.id,
                )
            ).first()
            if artifact is None:
                artifact = CodingPatchArtifact(
                    coding_run_id=run.id,
                    coding_turn_id=turn.id,
                    final_patch=final_content,
                )
            else:
                artifact.final_patch = final_content
            db.add(artifact)

        turn.status = "completed"
        turn.completed_at = datetime.now(timezone.utc)
        run.status = "completed"
        run.completed_at = datetime.now(timezone.utc)
        db.add(turn)
        db.add(run)
        db.commit()


@celery_app.task(name="coding.execute_turn")
def execute_turn(run_id: str, turn_id: str):
    """Celery task entrypoint."""
    asyncio.run(_async_execute_turn(run_id, turn_id))
