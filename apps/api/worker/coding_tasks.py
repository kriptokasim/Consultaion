"""
Celery tasks for executing Coding Agent turns.
Implements the multi-lane routing, early exit, and SSE broadcasting.
"""
import asyncio
import logging
import time
import uuid
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

CONVERGENCE_THRESHOLD = 0.85
TURN_LEASE_TTL_SECONDS = 180
TURN_FOLLOW_POLL_SECONDS = 0.5


@dataclass(frozen=True)
class LaneExecutionResult:
    lane_name: str
    model_key: str
    status: str
    content: str | None
    error: str | None


@dataclass(frozen=True)
class _LaneLease:
    key: str | None
    token: str | None
    client: object | None


class LaneCoordinationUnavailable(RuntimeError):
    """Distributed Coding Agent ownership cannot be verified."""


def _lane_snapshot(record: CodingLaneResult) -> LaneExecutionResult:
    return LaneExecutionResult(
        lane_name=record.lane_name,
        model_key=record.model_key,
        status=record.status,
        content=record.content,
        error=record.error,
    )


def _load_lane_snapshot(
    run_id: str,
    turn_id: str,
    lane: str,
    *,
    terminal_only: bool = False,
) -> LaneExecutionResult | None:
    with session_scope() as db_session:
        record = db_session.exec(
            select(CodingLaneResult).where(
                CodingLaneResult.coding_run_id == run_id,
                CodingLaneResult.coding_turn_id == turn_id,
                CodingLaneResult.lane_name == lane,
            )
        ).first()
        if record is None:
            return None
        if terminal_only and record.status not in {"completed", "failed"}:
            return None
        return _lane_snapshot(record)


def _turn_is_terminal(run_id: str, turn_id: str) -> bool:
    """Return whether the durable turn already reached a terminal product state."""
    with session_scope() as db_session:
        run = db_session.get(CodingRun, run_id)
        turn = db_session.get(CodingTurn, turn_id)
        if run is None or turn is None:
            return True
        return turn.status in {"completed", "failed", "cancelled"}


async def _try_acquire_redis_lease(
    key: str,
    *,
    ttl_seconds: int,
) -> _LaneLease | None:
    from config import settings
    from redis_pool import get_async_redis_client

    client = get_async_redis_client()
    if client is None:
        if getattr(settings, "IS_LOCAL_ENV", False):
            return _LaneLease(key=None, token=None, client=None)
        raise LaneCoordinationUnavailable(
            "Coding Agent coordination is temporarily unavailable."
        )

    token = str(uuid.uuid4())
    try:
        acquired = await client.set(key, token, ex=ttl_seconds, nx=True)
    except Exception as exc:
        if getattr(settings, "IS_LOCAL_ENV", False):
            logger.warning("Coding Agent Redis lease unavailable locally: %s", exc)
            return _LaneLease(key=None, token=None, client=None)
        raise LaneCoordinationUnavailable(
            "Coding Agent coordination is temporarily unavailable."
        ) from exc
    if not acquired:
        return None
    return _LaneLease(key=key, token=token, client=client)


async def _try_acquire_lane_lease(
    run_id: str,
    turn_id: str,
    lane: str,
    *,
    ttl_seconds: int,
) -> _LaneLease | None:
    return await _try_acquire_redis_lease(
        f"coding:lane:lease:{run_id}:{turn_id}:{lane}",
        ttl_seconds=ttl_seconds,
    )


async def _release_lane_lease(lease: _LaneLease | None) -> None:
    if lease is None or lease.client is None or not lease.key or not lease.token:
        return
    script = (
        "if redis.call('get', KEYS[1]) == ARGV[1] then "
        "return redis.call('del', KEYS[1]) else return 0 end"
    )
    try:
        await lease.client.eval(script, 1, lease.key, lease.token)
    except Exception:
        logger.warning("Failed to release Coding Agent lease %s", lease.key, exc_info=True)


async def _acquire_or_follow_turn(run_id: str, turn_id: str) -> _LaneLease | None:
    """Own one parent turn or follow the current owner until durable completion."""
    if _turn_is_terminal(run_id, turn_id):
        return None

    key = f"coding:turn:lease:{run_id}:{turn_id}"
    deadline = time.monotonic() + TURN_LEASE_TTL_SECONDS + 10
    while True:
        lease = await _try_acquire_redis_lease(
            key,
            ttl_seconds=TURN_LEASE_TTL_SECONDS,
        )
        if lease is not None:
            if _turn_is_terminal(run_id, turn_id):
                await _release_lane_lease(lease)
                return None
            return lease

        if _turn_is_terminal(run_id, turn_id):
            return None
        if time.monotonic() >= deadline:
            raise LaneCoordinationUnavailable(
                "Coding turn is already executing and did not reach a durable result."
            )
        await asyncio.sleep(TURN_FOLLOW_POLL_SECONDS)


async def _acquire_or_follow_lane(
    run_id: str,
    turn_id: str,
    lane: str,
    *,
    timeout_seconds: int,
) -> tuple[_LaneLease | None, LaneExecutionResult | None]:
    existing = _load_lane_snapshot(run_id, turn_id, lane, terminal_only=True)
    if existing is not None:
        return None, existing

    lease_ttl = max(timeout_seconds + 45, 90)
    deadline = time.monotonic() + lease_ttl + 5

    while True:
        lease = await _try_acquire_lane_lease(
            run_id,
            turn_id,
            lane,
            ttl_seconds=lease_ttl,
        )
        if lease is not None:
            completed = _load_lane_snapshot(run_id, turn_id, lane, terminal_only=True)
            if completed is not None:
                await _release_lane_lease(lease)
                return None, completed
            return lease, None

        completed = _load_lane_snapshot(run_id, turn_id, lane, terminal_only=True)
        if completed is not None:
            return None, completed
        if time.monotonic() >= deadline:
            raise LaneCoordinationUnavailable(
                f"Coding lane '{lane}' is already executing and did not reach a durable result."
            )
        await asyncio.sleep(0.5)


def compute_similarity(text1: str, text2: str) -> float:
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
    """Execute exactly one provider call for a run/turn/lane identity."""
    model_key = LANE_MODELS[lane]
    timeout = LANE_TIMEOUTS[lane]
    lease: _LaneLease | None = None

    try:
        lease, followed_result = await _acquire_or_follow_lane(
            run_id,
            turn_id,
            lane,
            timeout_seconds=timeout,
        )
        if followed_result is not None:
            return followed_result
    except LaneCoordinationUnavailable as exc:
        incr_metric("coding.lane_failure_count", tags={"lane": lane, "reason": "coordination"})
        return LaneExecutionResult(
            lane_name=lane,
            model_key=model_key,
            status="failed",
            content=None,
            error=str(exc),
        )

    sse = get_sse_backend()
    start_time = datetime.now(timezone.utc)

    try:
        with session_scope() as db_session:
            existing = db_session.exec(
                select(CodingLaneResult).where(
                    CodingLaneResult.coding_run_id == run_id,
                    CodingLaneResult.coding_turn_id == turn_id,
                    CodingLaneResult.lane_name == lane,
                )
            ).first()
            if existing and existing.status in {"completed", "failed"}:
                return _lane_snapshot(existing)
            if existing is None:
                existing = CodingLaneResult(
                    coding_run_id=run_id,
                    coding_turn_id=turn_id,
                    lane_name=lane,
                    model_key=model_key,
                    provider="gateway",
                    status="running",
                )
            else:
                existing.status = "running"
                existing.error = None
                existing.completed_at = None
            db_session.add(existing)
            db_session.commit()

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

        status = "completed"
        content: str | None = None
        error: str | None = None
        token_usage: dict | None = None
        try:
            content, usage = await asyncio.wait_for(
                call_model_via_gateway(
                    messages=[{"role": "user", "content": prompt}],
                    model_id=model_key,
                    role="coding_agent",
                    user_id=user_id,
                    db_session=None,
                ),
                timeout=timeout,
            )
            token_usage = {
                "prompt": usage.prompt_tokens,
                "completion": usage.completion_tokens,
                "total": usage.total_tokens,
            }
        except asyncio.TimeoutError:
            status = "failed"
            error = "Lane execution timed out"
            incr_metric("coding.lane_failure_count", tags={"lane": lane, "reason": "timeout"})
        except Exception as exc:
            status = "failed"
            error = str(exc)
            if "free-only mode" in str(exc).lower():
                incr_metric("coding.free_only_block_count", tags={"lane": lane, "model": model_key})
            incr_metric("coding.lane_failure_count", tags={"lane": lane, "reason": "error"})

        completed_at = datetime.now(timezone.utc)
        latency_ms = (completed_at - start_time).total_seconds() * 1000

        with session_scope() as db_session:
            result_record = db_session.exec(
                select(CodingLaneResult).where(
                    CodingLaneResult.coding_run_id == run_id,
                    CodingLaneResult.coding_turn_id == turn_id,
                    CodingLaneResult.lane_name == lane,
                )
            ).first()
            if result_record is None:
                raise RuntimeError("Coding lane durable claim disappeared before finalization")
            result_record.status = status
            result_record.content = content
            result_record.error = error
            result_record.token_usage = token_usage
            result_record.completed_at = completed_at
            result_record.latency_ms = latency_ms
            db_session.add(result_record)
            db_session.commit()
            snapshot = _lane_snapshot(result_record)

        record_timer("coding.lane_latency_ms", latency_ms, tags={"lane": lane})
        return snapshot
    finally:
        await _release_lane_lease(lease)


async def _async_execute_turn_owned(run_id: str, turn_id: str) -> None:
    """Execute a turn after parent ownership has been established."""
    sse = get_sse_backend()

    with session_scope() as db:
        run = db.get(CodingRun, run_id)
        turn = db.get(CodingTurn, turn_id)
        if not run or not turn:
            return
        if turn.status in {"completed", "failed", "cancelled"}:
            return

        tier_res = classify_tier(run.file_paths or [], turn.prompt)
        run.tier = tier_res.tier
        db.add(run)
        db.commit()

        prompt = turn.prompt
        run_tier = run.tier
        user_id = run.user_id
        run_pk = run.id
        turn_pk = turn.id

    tasks = []
    for lane in tier_res.active_lanes:
        if lane != "judge":
            tasks.append(
                _execute_lane(
                    run_pk,
                    turn_pk,
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
                f"run-{run_pk}",
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
                incr_metric("coding.early_exit_rate", tags={"tier": run_tier})

    if not judge_skipped and "judge" in tier_res.active_lanes:
        incr_metric("coding.judge_invoked_count", tags={"tier": run_tier})
        judge_prompt = f"Evaluate the following proposals for this task:\n\nTask: {prompt}\n\n"
        for lane, res in results_by_lane.items():
            if res.status == "completed":
                judge_prompt += f"--- {lane.upper()} PROPOSAL ---\n{res.content}\n\n"
        judge_prompt += "Provide the final unified patch."
        judge_res = await _execute_lane(
            run_pk,
            turn_pk,
            "judge",
            judge_prompt,
            run_tier=run_tier,
            user_id=user_id,
        )
        if judge_res.status == "completed":
            final_content = judge_res.content
        else:
            fast_fallback = results_by_lane.get("fast")
            final_content = (
                fast_fallback.content
                if fast_fallback and fast_fallback.status == "completed"
                else None
            )

    if not final_content and "fast" in results_by_lane:
        fast_fallback = results_by_lane["fast"]
        if fast_fallback.status == "completed":
            final_content = fast_fallback.content

    terminal_status = "completed" if final_content else "failed"
    completed_at = datetime.now(timezone.utc)

    with session_scope() as db:
        run = db.get(CodingRun, run_pk)
        turn = db.get(CodingTurn, turn_pk)
        if not run or not turn:
            return
        if turn.status in {"completed", "failed", "cancelled"}:
            return

        if final_content:
            artifact = db.exec(
                select(CodingPatchArtifact).where(
                    CodingPatchArtifact.coding_run_id == run_pk,
                    CodingPatchArtifact.coding_turn_id == turn_pk,
                )
            ).first()
            if artifact is None:
                artifact = CodingPatchArtifact(
                    coding_run_id=run_pk,
                    coding_turn_id=turn_pk,
                    final_patch=final_content,
                )
            else:
                artifact.final_patch = final_content
            db.add(artifact)

        turn.status = terminal_status
        turn.completed_at = completed_at
        run.status = terminal_status
        run.completed_at = completed_at
        run.error = None if final_content else "Coding Agent produced no successful patch."
        db.add(turn)
        db.add(run)
        db.commit()


async def _async_execute_turn(run_id: str, turn_id: str):
    """Single-owner parent entrypoint for one Coding Agent turn identity."""
    lease = await _acquire_or_follow_turn(run_id, turn_id)
    if lease is None:
        return

    try:
        await _async_execute_turn_owned(run_id, turn_id)
    finally:
        await _release_lane_lease(lease)


@celery_app.task(name="coding.execute_turn", bind=True, max_retries=3)
def execute_turn(self, run_id: str, turn_id: str):
    """Celery task entrypoint with bounded retry for coordination/runtime faults."""
    try:
        asyncio.run(_async_execute_turn(run_id, turn_id))
    except LaneCoordinationUnavailable as exc:
        incr_metric("coding.turn_failure_count", tags={"reason": "coordination"})
        logger.warning(
            "Coding turn coordination unavailable run=%s turn=%s; retrying: %s",
            run_id,
            turn_id,
            exc,
        )
        raise self.retry(exc=exc, countdown=10) from exc
    except Exception as exc:
        incr_metric("coding.turn_failure_count", tags={"reason": "runtime"})
        logger.exception("Coding turn failed run=%s turn=%s", run_id, turn_id)
        raise self.retry(exc=exc, countdown=10) from exc
