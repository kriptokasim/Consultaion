import asyncio
import logging
import os
import socket
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Sequence, Tuple

from agents import (
    UsageAccumulator,
    criticize_and_revise,
    judge_scores,
    produce_candidate,
)
from config import settings
from conversation.engine import run_conversation_debate
from database_async import async_session_scope
from integrations.email import send_debate_summary_email
from integrations.langfuse import current_trace_id
from integrations.slack import send_slack_alert
from models import Debate, DebateRound, Message, Score, User, Vote
from parliament.engine import run_parliament_debate
from schemas import DebateConfig, DebateSummary, default_agents, default_judges
from sqlalchemy import or_, update
from sse_backend import get_sse_backend

logger = logging.getLogger(__name__)


class DebateEngineError(RuntimeError):
    """Base class for orchestration errors."""



class SeatExecutionError(DebateEngineError):
    def __init__(self, seat: str, stage: str, original: Exception):
        self.seat = seat
        self.stage = stage
        self.original = original
        super().__init__(f"{stage} failed for {seat}: {original}")


def _get_runner_id() -> str:
    """Generate a unique ID for this worker process."""
    return f"{socket.gethostname()}-{os.getpid()}"


async def _try_acquire_lease(debate_id: str, runner_id: str, lease_seconds: int = 60) -> bool:
    """Attempt to acquire a lock on the debate execution."""
    async with async_session_scope() as session:
        now = datetime.now(timezone.utc)
        # Update if unowned OR lease expired OR owned by self
        stmt = (
            update(Debate)
            .where(Debate.id == debate_id)
            .where(
                or_(
                    Debate.runner_id.is_(None),
                    Debate.lease_expires_at < now,
                    Debate.runner_id == runner_id
                )
            )
            .values(
                runner_id=runner_id,
                lease_expires_at=now + timedelta(seconds=lease_seconds),
                last_heartbeat_at=now,
                status="running",
                # Increment run_attempt only if we are taking over (not just refreshing own)
                # But simple Increment is safer for tracking restarts
                run_attempt=Debate.run_attempt + 1
            )
        )
        result = await session.execute(stmt)
        await session.commit()
        return result.rowcount > 0


async def _heartbeat(debate_id: str, runner_id: str, lease_seconds: int = 60) -> None:
    """Refresh the lease."""
    async with async_session_scope() as session:
        now = datetime.now(timezone.utc)
        stmt = (
            update(Debate)
            .where(Debate.id == debate_id)
            .where(Debate.runner_id == runner_id)
            .values(
                lease_expires_at=now + timedelta(seconds=lease_seconds),
                last_heartbeat_at=now
            )
        )
        await session.execute(stmt)
        await session.commit()


async def _release_lease(debate_id: str, runner_id: str) -> None:
    """Release the lease (cleanup)."""
    async with async_session_scope() as session:
        stmt = (
            update(Debate)
            .where(Debate.id == debate_id)
            .where(Debate.runner_id == runner_id)
            .values(runner_id=None, lease_expires_at=None)
        )
        await session.execute(stmt)
        await session.commit()


async def _build_and_send_summary(debate_id: str, user_id: str | None) -> None:
    if not user_id:
        return
    
    async with async_session_scope() as session:
        user = await session.get(User, user_id)
        if not user or not user.email_summaries_enabled or not user.email:
            return
        
        debate = await session.get(Debate, debate_id)
        if not debate:
            return
            
        # Collect models used
        models = set()
        if debate.model_id:
            models.add(debate.model_id)
        if debate.routed_model:
            models.add(debate.routed_model)
        
        # Best effort to get winner
        winner = None
        if debate.final_meta and "ranking" in debate.final_meta:
            ranking = debate.final_meta["ranking"]
            if ranking and isinstance(ranking, list):
                winner = ranking[0]
        
        summary_text = debate.final_content or "No summary available."
        url = f"{settings.WEB_APP_ORIGIN}/debates/{debate.id}" if settings.WEB_APP_ORIGIN else None
        
        summary = DebateSummary(
            debate_id=str(debate.id),
            title=debate.prompt[:100] if debate.prompt else "Unnamed Debate",
            models_used=list(models),
            winner=winner,
            summary_text=summary_text[:2000], # Truncate for email
            url=url,
        )
    
    # Fire and forget
    asyncio.create_task(send_debate_summary_email(user.email, summary))


async def _start_round(debate_id: str, index: int, label: str, note: str) -> int:
    async with async_session_scope() as session:
        round_record = DebateRound(debate_id=debate_id, index=index, label=label, note=note)
        session.add(round_record)
        await session.commit()
        await session.refresh(round_record)
        return round_record.id  # type: ignore[return-value]


async def _end_round(round_id: int) -> None:
    async with async_session_scope() as session:
        round_record = await session.get(DebateRound, round_id)
        if round_record:
            round_record.ended_at = datetime.now(timezone.utc)
            session.add(round_record)
            await session.commit()


async def _persist_messages(debate_id: str, round_index: int, messages: List[Dict[str, Any]], role: str) -> None:
    async with async_session_scope() as session:
        for payload in messages:
            session.add(
                Message(
                    debate_id=debate_id,
                    round_index=round_index,
                    role=role,
                    persona=payload.get("persona"),
                    content=payload.get("text", ""),
                    meta={k: v for k, v in payload.items() if k not in {"persona", "text"}},
                )
            )
        await session.commit()


def _check_budget(budget, usage: UsageAccumulator) -> str | None:
    if not budget:
        return None
    tokens_total = float(usage.total_tokens)
    cost_total = float(usage.cost_usd)
    if budget.max_tokens and tokens_total > budget.max_tokens:
        return "token_budget_exceeded"
    if budget.max_cost_usd and cost_total > budget.max_cost_usd:
        return "cost_budget_exceeded"
    return None


def _compute_rankings(scores: Sequence[Dict[str, Any]]):
    if not scores:
        return [], {"borda": {}, "condorcet": {}, "combined": {}}
    sorted_scores = sorted(scores, key=lambda s: s["score"], reverse=True)
    n = len(sorted_scores)
    borda = {entry["persona"]: float(n - idx - 1) for idx, entry in enumerate(sorted_scores)}
    condorcet = {entry["persona"]: 0.0 for entry in sorted_scores}

    for i in range(n):
        for j in range(i + 1, n):
            first = sorted_scores[i]
            second = sorted_scores[j]
            if first["score"] >= second["score"]:
                condorcet[first["persona"]] += 1
            else:
                condorcet[second["persona"]] += 1

    combined = {
        persona: borda[persona] + condorcet[persona]
        for persona in borda
    }

    ranking = sorted(
        combined.keys(),
        key=lambda persona: (
            combined[persona],
            borda[persona],
            condorcet[persona],
        ),
        reverse=True,
    )

    details = {"borda": borda, "condorcet": condorcet, "combined": combined}
    return ranking, details


def _select_candidates(preferred: Sequence[str], candidates: List[Dict[str, Any]], fallback_count: int = 3):
    if preferred:
        selected = [c for c in candidates if c["persona"] in preferred]
        if selected:
            return selected
    return candidates[:fallback_count] if candidates else []


async def _complete_debate_record(
    debate_id: str,
    *,
    final_content: str,
    final_meta: dict,
    status: str,
    tokens_total: float = 0.0,
    user_id: str | None = None,
) -> None:
    async with async_session_scope() as session:
        debate = await session.get(Debate, debate_id)
        if not debate:
            return
        debate.final_content = final_content
        debate.final_meta = final_meta
        debate.status = status
        debate.updated_at = datetime.now(timezone.utc)
        session.add(debate)
        if user_id:
            try:
                # TODO: Async token usage recording
                # record_token_usage(session, user_id, tokens_total, commit=False)
                pass
            except Exception:
                logger.exception("Failed to record token usage for debate %s", debate_id)
        await session.commit()


async def _run_mock_debate(
    debate_id: str,
    channel_id: str,
    agent_configs: list,
    usage_tracker: UsageAccumulator,
):
    """Execute a fast mock debate for testing."""
    mock_scores = [
        {"persona": agent.name, "score": 8.0, "rationale": "fast-track"}
        for agent in agent_configs
    ]
    usage_snapshot = usage_tracker.snapshot()
    backend = get_sse_backend()
    await backend.publish(channel_id, {"type": "message", "round": 0, "candidates": []})
    await backend.publish(
        channel_id,
        {
            "type": "score",
            "scores": mock_scores,
            "judges": [
                {"persona": score["persona"], "judge": "FastJudge", "score": score["score"], "rationale": score["rationale"]}
                for score in mock_scores
            ],
        }
    )
    await backend.publish(
        channel_id,
        {
            "type": "final",
            "content": "Fast debate completed.",
            "meta": {
                "scores": mock_scores,
                "ranking": [entry["persona"] for entry in mock_scores],
                "usage": usage_snapshot,
            },
        }
    )
    await _complete_debate_record(
        debate_id,
        final_content="Fast debate completed.",
        final_meta={
            "scores": mock_scores,
            "ranking": [entry["persona"] for entry in mock_scores],
            "usage": usage_snapshot,
        },
        status="completed",
        tokens_total=usage_tracker.total_tokens,
    )


async def _run_draft_round(
    debate_id: str,
    prompt: str,
    agent_configs: list,
    model_id: str | None,
    usage_tracker: UsageAccumulator,
    channel_id: str,
) -> List[Dict[str, Any]]:
    """Execute the draft round."""
    draft_round = await _start_round(debate_id, 1, "draft", "candidate drafting")
    candidate_results = await asyncio.gather(
        *[produce_candidate(prompt, agent, model_id=model_id, debate_id=debate_id) for agent in agent_configs],
        return_exceptions=True,
    )
    candidates: list[Dict[str, Any]] = []
    failures: list[SeatExecutionError] = []
    for agent, result in zip(agent_configs, candidate_results, strict=False):
        if isinstance(result, Exception):
            error = SeatExecutionError(agent.name, "draft", result)
            failures.append(error)
            logger.error("Debate %s: draft seat %s failed: %s", debate_id, agent.name, result)
            continue
        payload, candidate_usage = result
        candidates.append(payload)
        usage_tracker.extend(candidate_usage)

    if failures:
        backend = get_sse_backend()
        await backend.publish(
            channel_id,
            {
                "type": "notice",
                "level": "warn",
                "debate_id": debate_id,
                "message": f"{len(failures)} seat(s) failed during drafting",
            },
        )

    if not candidates:
        raise DebateEngineError("All candidate generators failed")

    await _persist_messages(debate_id, 1, candidates, role="candidate")
    await _end_round(draft_round)
    backend = get_sse_backend()
    await backend.publish(channel_id, {"type": "message", "round": 1, "candidates": candidates})
    logger.debug("Debate %s: produced %d candidates", debate_id, len(candidates))
    return candidates


async def _run_critique_round(
    debate_id: str,
    prompt: str,
    candidates: List[Dict[str, Any]],
    model_id: str | None,
    usage_tracker: UsageAccumulator,
    channel_id: str,
) -> List[Dict[str, Any]]:
    """Execute the critique and revision round."""
    critique_round = await _start_round(debate_id, 2, "critique", "cross-critique and revision")
    revised, critique_usage = await criticize_and_revise(prompt, candidates, model_id=model_id, debate_id=debate_id)
    usage_tracker.extend(critique_usage)
    
    await _persist_messages(debate_id, 2, revised, role="revised")
    await _end_round(critique_round)
    backend = get_sse_backend()
    await backend.publish(channel_id, {"type": "message", "round": 2, "revised": revised})
    logger.debug("Debate %s: critique round completed", debate_id)
    return revised


async def _run_judge_round(
    debate_id: str,
    prompt: str,
    candidates: List[Dict[str, Any]],
    judge_configs: list,
    model_id: str | None,
    usage_tracker: UsageAccumulator,
    channel_id: str,
) -> Tuple[List[Dict[str, Any]], List[str], Dict[str, Any]]:
    """Execute the judging round and return (aggregate_scores, ranking, vote_details)."""
    judge_round = await _start_round(debate_id, 3, "judge", "rubric scoring")
    aggregate_scores, judge_details, judge_usage = await judge_scores(
        prompt, candidates, judge_configs, model_id=model_id, debate_id=debate_id
    )
    usage_tracker.extend(judge_usage)
    
    async with async_session_scope() as session:
        for detail in judge_details:
            session.add(
                Score(
                    debate_id=debate_id,
                    persona=detail["persona"],
                    judge=detail["judge"],
                    score=detail["score"],
                    rationale=detail["rationale"],
                )
            )
        await session.commit()
    
    await _end_round(judge_round)
    backend = get_sse_backend()
    await backend.publish(channel_id, {"type": "score", "round": 3, "scores": aggregate_scores, "judges": judge_details})
    ranking, vote_details = _compute_rankings(aggregate_scores)
    logger.debug("Debate %s: judges completed with %d entries", debate_id, len(judge_details))
    
    async with async_session_scope() as session:
        session.add(
            Vote(
                debate_id=debate_id,
                method="borda+condorcet",
                rankings={"order": ranking},
                weights={"borda_weight": 1.0, "condorcet_weight": 1.0},
                result=vote_details,
            )
        )
        await session.commit()
        
    return aggregate_scores, ranking, vote_details


async def run_debate(
    debate_id: str,
    prompt: str,
    channel_id: str,
    config_data: Dict[str, Any],
    model_id: str | None = None,
    trace_id: str | None = None,
):
    if trace_id:
        current_trace_id.set(trace_id)

    config = DebateConfig.model_validate(config_data or {})
    agent_configs = config.agents or default_agents()
    judge_configs = config.judges or default_judges()
    budget = config.budget
    backend = get_sse_backend()
    await backend.publish(channel_id, {"type": "round_started", "round": 0, "note": "plan"})

    usage_tracker = UsageAccumulator()
    debate_user_id: str | None = None
    start_time = datetime.now(timezone.utc)
    
    # State variables
    aggregate_scores: List[Dict[str, Any]] = []
    ranking: List[str] = []
    vote_details: Dict[str, Any] = {}
    source_candidates: List[Dict[str, Any]] = []
    selected_override: List[str] | None = None
    budget_reason: str | None = None
    early_stop_reason: str | None = None
    budget_notice_sent = False

    # Patchset 71: Lease & Heartbeat
    runner_id = _get_runner_id()
    heartbeat_task = None
    stop_heartbeat = asyncio.Event()

    try:
        # Attempt to acquire lease immediately
        if not await _try_acquire_lease(debate_id, runner_id):
            logger.warning(f"Debate {debate_id} lease acquisition failed for {runner_id}. Already running?")
            return

        # Start heartbeat
        async def _lease_heartbeat_loop():
            while not stop_heartbeat.is_set():
                await asyncio.sleep(15)
                if stop_heartbeat.is_set():
                    break
                try:
                    await _heartbeat(debate_id, runner_id)
                except Exception:
                    pass
        heartbeat_task = asyncio.create_task(_lease_heartbeat_loop())

        logger.debug("Debate %s: starting orchestration (runner=%s)", debate_id, runner_id)

        if settings.FAST_DEBATE:
            return await _run_mock_debate(debate_id, channel_id, agent_configs, usage_tracker)

        # 1. Initialize State Manager
        from orchestration.state import DebateStateManager
        
        # Load debate to get user_id for token tracking and email summaries
        async with async_session_scope() as session:
            debate = await session.get(Debate, debate_id)
            if not debate:
                 logger.error(f"Debate {debate_id} not found during execution.")
                 return # Or handle error appropriately
            
            debate_user_id = debate.user_id
            prompt = debate.prompt
            config_data = debate.config
            is_parliament = bool(debate.panel_config)
            debate_mode = debate.mode or "debate"

        state_manager = DebateStateManager(debate_id, debate_user_id)
        await state_manager.set_status("running")

        if debate_mode == "conversation":
            if not settings.ENABLE_CONVERSATION_MODE:
                raise ValueError("Conversation mode is disabled by configuration.")

            result = await run_conversation_debate(debate_id, model_id=model_id)
            
            await state_manager.complete_debate(
                final_content=result.final_answer,
                final_meta=result.final_meta,
                status=result.status,
                tokens_total=float(result.usage_tracker.total_tokens)
            )
            
            await backend.publish(
                channel_id,
                {
                    "type": "final",
                    "debate_id": debate_id,
                    "content": result.final_answer,
                    "meta": result.final_meta,
                },
            )
            return

        if is_parliament:
             # Legacy Parliament Path (for now, or wrap in a pipeline later)
            panel_result = await run_parliament_debate(debate_id, model_id=model_id)
            final_meta = panel_result.final_meta
            final_status = panel_result.status or "completed"
            if panel_result.status != "completed" or panel_result.error_reason:
                final_status = "failed"
            final_content = (
                panel_result.final_answer
                if panel_result.final_answer
                else "Debate aborted due to seat failures."
            )
            
            await state_manager.complete_debate(
                final_content=final_content,
                final_meta=final_meta,
                status=final_status,
                tokens_total=float(panel_result.usage_tracker.total_tokens)
            )

            if final_status == "failed":
                await backend.publish(
                    channel_id,
                    {
                        "type": "debate_failed",
                        "debate_id": debate_id,
                        "reason": panel_result.error_reason or "seat_failure_threshold_exceeded",
                        "meta": final_meta,
                    },
                )
                return
            await backend.publish(
                channel_id,
                {
                    "type": "final",
                    "debate_id": debate_id,
                    "content": panel_result.final_answer,
                    "meta": final_meta,
                },
            )
            return

        # 3. Standard Pipeline Execution
        from orchestration.engine import DebateRunner
        from orchestration.interfaces import DebateContext
        from orchestration.pipeline import StandardDebatePipeline

        context = DebateContext(
            debate_id=debate_id,
            prompt=prompt,
            config=config_data,
            channel_id=channel_id,
            model_id=model_id,
            usage_tracker=usage_tracker, # Pass the tracker we initialized
        )
        
        pipeline = StandardDebatePipeline(state_manager)
        runner = DebateRunner(pipeline, state_manager)
        
        await runner.run(context)
        
        # Success path for Standard Pipeline
        await _build_and_send_summary(debate_id, debate_user_id)

    except Exception as exc:
        logger.exception("Debate %s failed: %s", debate_id, exc)
        
        # Slack Alert
        await send_slack_alert(
            message="[Consultaion] Debate execution failed",
            level="error",
            meta={
                "debate_id": debate_id,
                "user_id": str(debate_user_id) if debate_user_id else "unknown",
                "error": str(exc)[:500],
            },
        )

        # Fallback error handling if Runner didn't catch it (though it should)
        # But we need to ensure DB status is updated if Runner failed completely
        try:
            async with async_session_scope() as session:
                debate = await session.get(Debate, debate_id)
                if debate and debate.status != "failed":
                    debate.status = "failed"
                    debate.updated_at = datetime.now(timezone.utc)
                    debate.final_meta = {"error": str(exc)}
                    session.add(debate)
                    await session.commit()
        except Exception:
            pass

        await backend.publish(
            channel_id,
            {"type": "error", "debate_id": debate_id, "message": str(exc)},
        )

    finally:
        # Cleanup lease and heartbeat
        if heartbeat_task:
            stop_heartbeat.set()
            try:
                await heartbeat_task
            except Exception:
                pass
            await _release_lease(debate_id, runner_id)
