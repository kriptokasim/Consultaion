from __future__ import annotations

import asyncio
import difflib
import logging
import re
from typing import List

from agents import call_llm_for_role
from celery.utils.log import get_task_logger
from database_async import async_session_scope
from models import Debate, DivergenceReport, Message
from sqlmodel import select
from utils.json_utils import extract_and_parse_json

from worker.celery_app import celery_app

logger = get_task_logger(__name__)
module_logger = logging.getLogger(__name__)


def compute_string_similarity(c1: str, c2: str) -> float:
    """Compare claims using lowercase token overlap and SequenceMatcher."""
    s1 = set(c1.lower().split())
    s2 = set(c2.lower().split())
    if not s1 or not s2:
        return 0.0
    jaccard = len(s1.intersection(s2)) / len(s1.union(s2))
    matcher = difflib.SequenceMatcher(None, c1.lower(), c2.lower()).ratio()
    return max(jaccard, matcher)


async def _extract_claims_from_response(prompt: str, response_content: str, model_display_name: str, debate_id: str) -> List[str]:
    """Use SOTA LLM to extract clean, key logical claims from a model response."""
    system_prompt = (
        "You are an AI analyst. Extract a clean list of 3-5 distinct, key factual or logical claims made in the text. "
        "Each claim should be a standalone sentence in under 15 words. Do not quote the text. Do not add numbers. "
        'Output strictly as a JSON object of form: {"claims": ["claim 1", "claim 2"]}'
    )
    
    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": f"Context/Question: {prompt}\n\nModel Response:\n{response_content}"}
    ]

    try:
        raw, _ = await call_llm_for_role(
            messages,
            role="Arena:ClaimExtractor",
            temperature=0.1,
            max_tokens=300,
            debate_id=debate_id
        )
        
        # Try extracting JSON fragment
        data = extract_and_parse_json(raw) or {}
        claims = data.get("claims", [])
        if isinstance(claims, list) and all(isinstance(c, str) for c in claims):
            return [c.strip() for c in claims if c.strip()]
    except Exception as exc:
        module_logger.warning("Failed to parse LLM extracted claims for %s: %s", model_display_name, exc)
    
    # Fallback parsing (split by sentences or lines)
    sentences = [s.strip() for s in re.split(r"[.!?\n]", response_content) if len(s.strip()) > 12]
    claims = [s for s in sentences if not s.startswith("⚠️")][:4]
    if not claims:
        claims = [f"Direct response statement from model {model_display_name}"]
    return claims


async def _execute_divergence_computation(debate_id: str) -> None:
    """Compute divergence from only the current attempt's canonical responses."""
    async with async_session_scope() as session:
        debate = await session.get(Debate, debate_id)
        if debate is None:
            module_logger.warning("Debate %s not found for divergence computation", debate_id)
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
            result = await session.execute(select(DivergenceReport).where(DivergenceReport.debate_id == debate_id))
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
            module_logger.warning(
                "Semantic divergence failed for %s; using string fallback: %s",
                debate_id,
                exc,
            )
            extracted = await asyncio.gather(
                *[
                    _extract_claims_from_response(
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
                    if compute_string_similarity(item["claim"], other["claim"]) >= 0.70:
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
            result = await session.execute(select(DivergenceReport).where(DivergenceReport.debate_id == debate_id))
            report = result.scalars().first()
            if not report:
                report = DivergenceReport(debate_id=debate_id)
            report.divergence_score = float(round(divergence_score, 2))
            report.consensus_claims = {"claims": consensus_list}
            report.contested_claims = {"claims": contested_list}
            session.add(report)
            await session.commit()
            module_logger.info("Saved semantic DivergenceReport for debate %s. Score: %.2f", debate_id, divergence_score)
        return divergence_score, consensus_list, contested_list

    async def load_divergence(session):
        result = await session.execute(select(DivergenceReport).where(DivergenceReport.debate_id == debate_id))
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
        # Divergence runs after the execution lease is released (post-terminal
        # background analysis), so it intentionally never carries a live lease.
        allow_unfenced=True,
    )


@celery_app.task(name="arena.compute_divergence", bind=True, max_retries=3)
def compute_divergence_task(self, debate_id: str) -> None:
    """Celery task that computes claim divergence for an Arena debate."""
    try:
        asyncio.run(_execute_divergence_computation(debate_id))
    except Exception as exc:
        logger.exception("Error while computing divergence for debate %s", debate_id)
        raise self.retry(exc=exc, countdown=10) from exc
