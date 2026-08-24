from __future__ import annotations

import asyncio
import logging
from typing import Any

from database_async import async_session_scope
from models import Debate, DivergenceReport, Message
from sqlmodel import select

logger = logging.getLogger(__name__)
_installed = False


class _OrchestratorSettingsProxy:
    """Keep dispatch Celery-backed but run lease-bound post-processing inline."""

    def __init__(self, base: Any) -> None:
        object.__setattr__(self, "_base", base)

    def __getattr__(self, name: str) -> Any:
        if name == "DEBATE_DISPATCH_MODE":
            return "inline"
        return getattr(object.__getattribute__(self, "_base"), name)

    def __setattr__(self, name: str, value: Any) -> None:
        setattr(object.__getattribute__(self, "_base"), name, value)


async def _execute_current_attempt_divergence(debate_id: str) -> None:
    from worker import arena_tasks

    async with async_session_scope() as session:
        debate = await session.get(Debate, debate_id)
        if debate is None:
            logger.warning("Debate %s not found for divergence computation", debate_id)
            return
        prompt = debate.prompt
        run_attempt = max(int(debate.run_attempt or 0), 1)
        result = await session.execute(
            select(Message)
            .where(Message.debate_id == debate_id)
            .where(Message.role == "arena_response")
            .order_by(Message.created_at.asc(), Message.id.asc())
        )
        rows = list(result.scalars().all())

    latest: dict[str, Message] = {}
    generations: dict[str, int] = {}
    for row in rows:
        meta = row.meta or {}
        if int(meta.get("run_attempt", 1) or 1) != run_attempt:
            continue
        if meta.get("success", True) is False:
            continue
        model_id = str(meta.get("model_id") or row.persona or row.id)
        generation = int(meta.get("retry_generation", 0) or 0)
        if model_id not in latest or generation >= generations[model_id]:
            latest[model_id] = row
            generations[model_id] = generation

    responses = [
        {
            "model_id": model_id,
            "content": row.content,
            "persona": row.persona or model_id,
            "response_id": row.response_id,
        }
        for model_id, row in sorted(latest.items())
    ]

    if not responses:
        async with async_session_scope() as session:
            result = await session.execute(
                select(DivergenceReport).where(DivergenceReport.debate_id == debate_id)
            )
            report = result.scalars().first() or DivergenceReport(debate_id=debate_id)
            report.divergence_score = 0.0
            report.consensus_claims = {"claims": []}
            report.contested_claims = {"claims": []}
            session.add(report)
            await session.commit()
        return

    checkpoint_input = {
        "prompt": prompt,
        "run_attempt": run_attempt,
        "responses": [
            {
                "model_id": item["model_id"],
                "response_id": item["response_id"],
                "content": item["content"],
            }
            for item in responses
        ],
    }

    async def run_divergence():
        from reporting.synthesizer import run_semantic_claims_analysis

        try:
            result = await run_semantic_claims_analysis(prompt, responses, debate_id)
            divergence_score = result["divergence_score"]
            consensus_list = result["consensus_claims"]
            contested_list = result["contested_claims"]
        except Exception as exc:
            logger.warning(
                "Semantic divergence failed for %s; using string fallback: %s",
                debate_id,
                exc,
            )
            extracted = await asyncio.gather(
                *[
                    arena_tasks._extract_claims_from_response(
                        prompt,
                        item["content"],
                        item["persona"],
                        debate_id,
                    )
                    for item in responses
                ]
            )
            all_claims: list[dict[str, str]] = []
            for item, claims in zip(responses, extracted, strict=False):
                for claim in claims:
                    all_claims.append({"claim": claim, "model": item["persona"]})

            processed: set[int] = set()
            consensus_list = []
            contested_list = []
            for index, item in enumerate(all_claims):
                if index in processed:
                    continue
                matches: list[int] = []
                models = [item["model"]]
                for other_index, other in enumerate(all_claims):
                    if index == other_index or other_index in processed:
                        continue
                    if arena_tasks.compute_string_similarity(item["claim"], other["claim"]) >= 0.70:
                        matches.append(other_index)
                        models.append(other["model"])
                processed.add(index)
                if matches:
                    processed.update(matches)
                    consensus_list.append(
                        {"claim": item["claim"], "models": sorted(set(models))}
                    )
                else:
                    contested_list.append(
                        {"claim": item["claim"], "model": item["model"]}
                    )
            total = len(consensus_list) + len(contested_list)
            divergence_score = len(contested_list) / total if total else 0.0

        async with async_session_scope() as session:
            result = await session.execute(
                select(DivergenceReport).where(DivergenceReport.debate_id == debate_id)
            )
            report = result.scalars().first() or DivergenceReport(debate_id=debate_id)
            report.divergence_score = float(round(divergence_score, 2))
            report.consensus_claims = {"claims": consensus_list}
            report.contested_claims = {"claims": contested_list}
            session.add(report)
            await session.commit()
        return divergence_score, consensus_list, contested_list

    async def load_divergence(session):
        result = await session.execute(
            select(DivergenceReport).where(DivergenceReport.debate_id == debate_id)
        )
        report = result.scalars().first()
        if report is None:
            return 0.0, [], []
        return (
            report.divergence_score,
            (report.consensus_claims or {}).get("claims", []),
            (report.contested_claims or {}).get("claims", []),
        )

    from orchestration.checkpoints import run_with_checkpoint

    await run_with_checkpoint(
        debate_id=debate_id,
        stage_key="divergence_analysis",
        input_data=checkpoint_input,
        run_fn=run_divergence,
        load_fn=load_divergence,
    )


def install_divergence_guard() -> None:
    global _installed
    if _installed:
        return

    import orchestrator
    from worker import arena_tasks

    # debate_dispatch imports config.settings independently, so real run
    # dispatch stays Celery-backed. Only orchestrator's post-process branch is
    # forced inline while its execution lease/context is still bound.
    if not isinstance(orchestrator.settings, _OrchestratorSettingsProxy):
        orchestrator.settings = _OrchestratorSettingsProxy(orchestrator.settings)
    arena_tasks._execute_divergence_computation = _execute_current_attempt_divergence
    _installed = True
