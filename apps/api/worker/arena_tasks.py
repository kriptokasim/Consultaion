from __future__ import annotations

import asyncio
import logging
import re
import json
import difflib
from typing import Optional, List, Dict, Any

from celery.utils.log import get_task_logger
from database import session_scope
from models import Debate, Message, DivergenceReport
from sqlmodel import Session, select
from agents import call_llm_for_role
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
        "Output strictly as a JSON object of form: {\"claims\": [\"claim 1\", \"claim 2\"]}"
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
        match = re.search(r"\{.*\}", raw, flags=re.S)
        if match:
            data = json.loads(match.group(0))
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
    """Core logic to fetch responses, extract claims, calculate similarity, and store report."""
    with session_scope() as session:
        debate = session.get(Debate, debate_id)
        if not debate:
            module_logger.warning("Debate %s not found for divergence computation", debate_id)
            return
        
        prompt = debate.prompt
        
        # Fetch arena responses
        stmt = select(Message).where(
            Message.debate_id == debate_id,
            Message.role == "arena_response"
        )
        db_responses = session.exec(stmt).all()
        responses = [
            {"content": r.content, "persona": r.persona or "Model"}
            for r in db_responses
        ]

    if not responses:
        module_logger.warning("No arena responses found for debate %s", debate_id)
        # Create empty report
        with session_scope() as session:
            report = session.exec(select(DivergenceReport).where(DivergenceReport.debate_id == debate_id)).first()
            if not report:
                report = DivergenceReport(
                    debate_id=debate_id,
                    divergence_score=0.0,
                    consensus_claims={"claims": []},
                    contested_claims={"claims": []}
                )
                session.add(report)
            return

    # Delegate to the upgraded semantic claim matching synthesizer analysis
    from reporting.synthesizer import run_semantic_claims_analysis
    try:
        res = await run_semantic_claims_analysis(prompt, responses, debate_id)
        divergence_score = res["divergence_score"]
        consensus_list = res["consensus_claims"]
        contested_list = res["contested_claims"]
    except Exception as exc:
        module_logger.error("Failed semantic divergence analysis: %s. Falling back to string overlap.", exc)
        # Fallback to older inline logic using compute_string_similarity
        tasks = []
        for resp in responses:
            tasks.append(_extract_claims_from_response(prompt, resp["content"], resp["persona"], debate_id))
        extracted_lists = await asyncio.gather(*tasks)
        
        all_claims = []
        for resp, claims in zip(responses, extracted_lists, strict=False):
            model_name = resp["persona"]
            for c in claims:
                all_claims.append({"claim": c, "model": model_name})
        
        processed = set()
        consensus_list = []
        contested_list = []
        
        for i, item1 in enumerate(all_claims):
            if i in processed:
                continue
            matching_indices = []
            matching_models = [item1["model"]]
            
            for j, item2 in enumerate(all_claims):
                if i != j and j not in processed:
                    sim = compute_string_similarity(item1["claim"], item2["claim"])
                    if sim >= 0.70:
                        matching_indices.append(j)
                        matching_models.append(item2["model"])
            
            if matching_indices:
                processed.add(i)
                for idx in matching_indices:
                    processed.add(idx)
                consensus_list.append({
                    "claim": item1["claim"],
                    "models": list(set(matching_models))
                })
            else:
                processed.add(i)
                contested_list.append({
                    "claim": item1["claim"],
                    "model": item1["model"]
                })
        
        total_distinct = len(consensus_list) + len(contested_list)
        divergence_score = len(contested_list) / total_distinct if total_distinct > 0 else 0.0

    with session_scope() as session:
        report = session.exec(select(DivergenceReport).where(DivergenceReport.debate_id == debate_id)).first()
        if not report:
            report = DivergenceReport(debate_id=debate_id)
        report.divergence_score = float(round(divergence_score, 2))
        report.consensus_claims = {"claims": consensus_list}
        report.contested_claims = {"claims": contested_list}
        session.add(report)
        session.commit()
        module_logger.info("Saved semantic DivergenceReport for debate %s. Score: %.2f", debate_id, divergence_score)


@celery_app.task(name="arena.compute_divergence", bind=True, max_retries=3)
def compute_divergence_task(self, debate_id: str) -> None:
    """Celery task that computes claim divergence for an Arena debate."""
    try:
        asyncio.run(_execute_divergence_computation(debate_id))
    except Exception as exc:
        logger.exception("Error while computing divergence for debate %s", debate_id)
        raise self.retry(exc=exc, countdown=10) from exc
