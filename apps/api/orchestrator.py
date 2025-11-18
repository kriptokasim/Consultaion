import asyncio
import logging
import os
from datetime import datetime, timezone
from typing import Any, Callable, Dict, List, Sequence

from agents import (
    criticize_and_revise,
    get_usage,
    judge_scores,
    produce_candidate,
    reset_usage,
    synthesize,
)
from database import session_scope
from models import Debate, DebateRound, Message, Score, Vote
from ratings import update_ratings_for_debate
from schemas import DebateConfig, default_agents, default_judges
from usage_limits import record_token_usage

logger = logging.getLogger(__name__)


def _start_round(debate_id: str, index: int, label: str, note: str) -> int:
    with session_scope() as session:
        round_record = DebateRound(debate_id=debate_id, index=index, label=label, note=note)
        session.add(round_record)
        session.commit()
        session.refresh(round_record)
        return round_record.id  # type: ignore[return-value]


def _end_round(round_id: int) -> None:
    with session_scope() as session:
        round_record = session.get(DebateRound, round_id)
        if round_record:
            round_record.ended_at = datetime.now(timezone.utc)
            session.add(round_record)
            session.commit()


def _persist_messages(debate_id: str, round_index: int, messages: List[Dict[str, Any]], role: str) -> None:
    with session_scope() as session:
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
        session.commit()


def _check_budget(budget) -> str | None:
    if not budget:
        return None
    usage = get_usage()
    tokens_total = float(usage.get("tokens", {}).get("total", 0))
    cost_total = float(usage.get("cost_usd") or usage.get("cost", 0) or 0)
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


async def run_debate(
    debate_id: str,
    prompt: str,
    q,
    config_data: Dict[str, Any],
    model_id: str | None = None,
    cleanup_cb: Callable[[str], None] | None = None,
):
    config = DebateConfig.model_validate(config_data or {})
    agent_configs = config.agents or default_agents()
    judge_configs = config.judges or default_judges()
    budget = config.budget

    await q.put({"type": "round_started", "round": 0, "note": "plan"})

    final_answer = ""
    aggregate_scores: List[Dict[str, Any]] = []
    ranking: List[str] = []
    vote_details: Dict[str, Any] = {}
    budget_reason: str | None = None
    early_stop_reason: str | None = None
    source_candidates: List[Dict[str, Any]] = []
    selected_override: List[str] | None = None
    budget_notice_sent = False

    usage_snapshot: Dict[str, Any] = {}
    debate_user_id: str | None = None
    reset_usage()
    try:
        logger.debug("Debate %s: starting orchestration", debate_id)
        if os.getenv("FAST_DEBATE", "0") == "1":
            mock_scores = [
                {"persona": agent.name, "score": 8.0, "rationale": "fast-track"}
                for agent in agent_configs
            ]
            await q.put({"type": "message", "round": 0, "candidates": []})
            await q.put(
                {
                    "type": "score",
                    "scores": mock_scores,
                    "judges": [
                        {"persona": score["persona"], "judge": "FastJudge", "score": score["score"], "rationale": score["rationale"]}
                        for score in mock_scores
                    ],
                }
            )
            await q.put(
                {
                    "type": "final",
                    "content": "Fast debate completed.",
                    "meta": {"scores": mock_scores, "ranking": [entry["persona"] for entry in mock_scores], "usage": {}},
                }
            )
            _complete_debate_record(
                debate_id,
                final_content="Fast debate completed.",
                final_meta={"scores": mock_scores, "ranking": [entry["persona"] for entry in mock_scores], "usage": {}},
                status="completed",
            )
            if cleanup_cb:
                cleanup_cb(debate_id)
            return
        with session_scope() as session:
            debate = session.get(Debate, debate_id)
            if not debate:
                await q.put({"type": "error", "message": "debate not found"})
                if cleanup_cb:
                    cleanup_cb(debate_id)
                return
            debate_user_id = debate.user_id
            debate.status = "running"
            debate.updated_at = datetime.now(timezone.utc)
            session.add(debate)
            session.commit()

        draft_round = _start_round(debate_id, 1, "draft", "candidate drafting")
        candidates = await asyncio.gather(*[produce_candidate(prompt, agent, model_id=model_id, debate_id=debate_id) for agent in agent_configs])
        source_candidates = candidates
        _persist_messages(debate_id, 1, candidates, role="candidate")
        _end_round(draft_round)
        await q.put({"type": "message", "round": 1, "candidates": candidates})
        logger.debug("Debate %s: produced %d candidates", debate_id, len(candidates))
        budget_reason = _check_budget(budget) or budget_reason
        if budget_reason and not budget_notice_sent:
            await q.put({"type": "notice", "message": budget_reason})
            budget_notice_sent = True

        revised = candidates
        if not budget_reason:
            critique_round = _start_round(debate_id, 2, "critique", "cross-critique and revision")
            revised = await criticize_and_revise(prompt, candidates, model_id=model_id, debate_id=debate_id)
            source_candidates = revised
            _persist_messages(debate_id, 2, revised, role="revised")
            _end_round(critique_round)
            await q.put({"type": "message", "round": 2, "revised": revised})
            logger.debug("Debate %s: critique round completed", debate_id)
            budget_reason = _check_budget(budget) or budget_reason
            if budget_reason and not budget_notice_sent:
                await q.put({"type": "notice", "message": budget_reason})
                budget_notice_sent = True

        judge_details: List[Dict[str, Any]] = []
        if not budget_reason:
            judge_round = _start_round(debate_id, 3, "judge", "rubric scoring")
            aggregate_scores, judge_details = await judge_scores(prompt, revised, judge_configs, model_id=model_id, debate_id=debate_id)
            with session_scope() as session:
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
                session.commit()
            _end_round(judge_round)
            await q.put({"type": "score", "round": 3, "scores": aggregate_scores, "judges": judge_details})
            ranking, vote_details = _compute_rankings(aggregate_scores)
            logger.debug("Debate %s: judges completed with %d entries", debate_id, len(judge_details))
            with session_scope() as session:
                session.add(
                    Vote(
                        debate_id=debate_id,
                        method="borda+condorcet",
                        rankings={"order": ranking},
                        weights={"borda_weight": 1.0, "condorcet_weight": 1.0},
                        result=vote_details,
                    )
                )
                session.commit()

            if aggregate_scores:
                sorted_scores = sorted(aggregate_scores, key=lambda s: s["score"], reverse=True)
                if (
                    budget
                    and budget.early_stop_delta is not None
                    and len(sorted_scores) > 1
                    and (sorted_scores[0]["score"] - sorted_scores[1]["score"]) > budget.early_stop_delta
                ):
                    early_stop_reason = f"score_gap_{sorted_scores[0]['score'] - sorted_scores[1]['score']:.2f}"
                    selected_override = [sorted_scores[0]["persona"]]

        if not aggregate_scores:
            aggregate_scores = [
                {"persona": c["persona"], "score": 0.0, "rationale": "No judges available"}
                for c in (source_candidates or candidates)
            ]
            ranking = [c["persona"] for c in (source_candidates or candidates)]
        elif not ranking:
            ranking = [c["persona"] for c in aggregate_scores]

        preferred = selected_override or ranking[:3]
        selected_candidates = _select_candidates(preferred, source_candidates or candidates)
        selected_scores = [s for s in aggregate_scores if s["persona"] in {c["persona"] for c in selected_candidates}]
        if not selected_candidates:
            selected_candidates = source_candidates or candidates
        if not selected_scores:
            selected_scores = aggregate_scores

        final_answer = await synthesize(prompt, selected_candidates, selected_scores, model_id=model_id, debate_id=debate_id)
        usage_snapshot = get_usage()
        tokens_total = float(usage_snapshot.get("tokens", {}).get("total", 0) or 0)
        final_meta = {
            "prompt": prompt,
            "scores": aggregate_scores,
            "ranking": ranking,
            "usage": usage_snapshot,
            "vote": vote_details,
            "budget_reason": budget_reason,
            "early_stop_reason": early_stop_reason,
        }
        _complete_debate_record(
            debate_id,
            final_content=final_answer,
            final_meta=final_meta,
            status="completed" if not budget_reason else "completed_budget",
            tokens_total=tokens_total,
            user_id=debate_user_id,
        )

        await q.put(
            {
                "type": "final",
                "content": final_answer,
                "meta": {
                    "prompt": prompt,
                    "scores": aggregate_scores,
                    "ranking": ranking,
                    "usage": usage_snapshot or get_usage(),
                    "budget_reason": budget_reason,
                    "early_stop_reason": early_stop_reason,
                    "vote": vote_details,
                },
            }
        )
        logger.debug("Debate %s: finalized, triggering rating update", debate_id)
        loop = asyncio.get_running_loop()
        def _run_update():
            try:
                update_ratings_for_debate(debate_id)
                logger.debug("Debate %s: rating update completed", debate_id)
            except Exception:
                logger.exception("Rating update failed for debate %s", debate_id)

        loop.run_in_executor(None, _run_update)
    except Exception as exc:
        logger.exception("Debate %s failed: %s", debate_id, exc)
        with session_scope() as session:
            debate = session.get(Debate, debate_id)
            if debate:
                debate.status = "failed"
                debate.updated_at = datetime.now(timezone.utc)
                debate.final_meta = {"error": str(exc)}
                session.add(debate)
                session.commit()
        await q.put({"type": "error", "message": str(exc)})
    finally:
        if cleanup_cb:
            cleanup_cb(debate_id)
def _complete_debate_record(
    debate_id: str,
    *,
    final_content: str,
    final_meta: dict,
    status: str,
    tokens_total: float = 0.0,
    user_id: str | None = None,
) -> None:
    with session_scope() as session:
        debate = session.get(Debate, debate_id)
        if not debate:
            return
        debate.final_content = final_content
        debate.final_meta = final_meta
        debate.status = status
        debate.updated_at = datetime.now(timezone.utc)
        session.add(debate)
        if user_id:
            try:
                record_token_usage(session, user_id, tokens_total, commit=False)
            except Exception:
                logger.exception("Failed to record token usage for debate %s", debate_id)
        session.commit()
