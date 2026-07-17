from __future__ import annotations

import asyncio
import logging

from agents import call_llm_for_role
from celery.utils.log import get_task_logger
from database_async import async_session_scope
from models import Debate, Score
from sqlmodel import select
from utils.json_utils import extract_and_parse_json

from worker.celery_app import celery_app

logger = get_task_logger(__name__)
module_logger = logging.getLogger(__name__)


async def _execute_vote_reasons_extraction(debate_id: str) -> None:
    """Read judge scores/rationales, call LLM to synthesize winner vs dissenter reasons, update final_meta."""
    async with async_session_scope() as session:
        debate = await session.get(Debate, debate_id)
        if not debate:
            module_logger.warning("Debate %s not found for vote reasons extraction", debate_id)
            return

        # Fetch all scores for this debate
        stmt = select(Score).where(Score.debate_id == debate_id)
        res = await session.execute(stmt)
        scores = res.scalars().all()
        
        if not scores:
            module_logger.warning("No scores found for debate %s to extract vote reasons", debate_id)
            return

        # Build context from scores
        rationales_context = []
        for s in scores:
            rationales_context.append(
                f"Judge: {s.judge}\nCandidate: {s.persona}\nScore: {s.score}\nRationale: {s.rationale}\n"
            )
        
        rationales_str = "\n---\n".join(rationales_context)
        prompt = debate.prompt

    system_prompt = (
        "You are an AI analytics engine. Synthesize the debate outcomes based on the provided judges' evaluations.\n"
        "Analyze why the winning candidate excelled, and why the other candidates failed or received lower scores.\n"
        "Extract 2-3 concise 'winner_highlights' (keys to success) and 2-3 'dissenter_highlights' (criticisms/drawbacks of other models).\n"
        "Output strictly as a JSON object of form:\n"
        '{"winner_highlights": ["Point 1", "Point 2"], "dissenter_highlights": ["Point 1", "Point 2"]}'
    )

    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": f"Debate Prompt: {prompt}\n\nJudges' Rationales:\n{rationales_str}"}
    ]

    winner_hl = ["Highly structured and coherent response"]
    dissenter_hl = ["Missed key constraints", "Lacked detail compared to winner"]

    try:
        raw, _ = await call_llm_for_role(
            messages,
            role="Voting:ReasonsExtractor",
            temperature=0.2,
            max_tokens=400,
            debate_id=debate_id
        )

        # PS155.4: Robust JSON parsing and integrity validation
        data = extract_and_parse_json(raw)
        if data and isinstance(data, dict):
            w = data.get("winner_highlights", [])
            d = data.get("dissenter_highlights", [])
            
            # Validation: must be lists of non-empty strings
            if isinstance(w, list):
                valid_w = [str(x).strip() for x in w if str(x).strip()]
                if valid_w:
                    winner_hl = valid_w[:5]  # cap at 5
            
            if isinstance(d, list):
                valid_d = [str(x).strip() for x in d if str(x).strip()]
                if valid_d:
                    dissenter_hl = valid_d[:5]  # cap at 5
    except Exception as exc:
        module_logger.warning("Failed to extract vote reasons via LLM for debate %s: %s", debate_id, exc)

    # Update debate.final_meta
    # Update debate.final_meta
    async with async_session_scope() as session:
        debate = await session.get(Debate, debate_id)
        if debate:
            meta = dict(debate.final_meta or {})
            meta["vote_reasons"] = {
                "winner_highlights": winner_hl,
                "dissenter_highlights": dissenter_hl
            }
            debate.final_meta = meta
            session.add(debate)
            await session.commit()
            module_logger.info("Successfully saved vote reasons in final_meta for debate %s", debate_id)


@celery_app.task(name="voting.extract_vote_reasons", bind=True, max_retries=3)
def extract_vote_reasons_task(self, debate_id: str) -> None:
    """Celery task to run LLM extraction of vote highlights/criticisms."""
    try:
        asyncio.run(_execute_vote_reasons_extraction(debate_id))
    except Exception as exc:
        logger.exception("Error while extracting vote reasons for debate %s", debate_id)
        raise self.retry(exc=exc, countdown=10) from exc
