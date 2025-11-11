import asyncio
import json
import logging
import os
import re
from typing import Any, Dict, List, Optional, Sequence, Tuple

from litellm import acompletion
from schemas import AgentConfig, JudgeConfig

logger = logging.getLogger(__name__)

_use_mock_env = os.getenv("USE_MOCK")
_has_llm_key = any(
    os.getenv(key)
    for key in (
        "OPENAI_API_KEY",
        "ANTHROPIC_API_KEY",
        "LITELLM_API_KEY",
        "AZURE_API_KEY",
    )
)
USE_MOCK = (_use_mock_env != "0") if _use_mock_env is not None else not _has_llm_key
LITELLM_MODEL = os.getenv("LITELLM_MODEL", "gpt-4o-mini")
LITELLM_API_BASE = os.getenv("LITELLM_API_BASE")
if LITELLM_API_BASE:
    os.environ["LITELLM_API_BASE"] = LITELLM_API_BASE

USAGE_TRACKER: Dict[str, float] = {"tokens": 0.0, "cost": 0.0}


def reset_usage() -> None:
    USAGE_TRACKER["tokens"] = 0.0
    USAGE_TRACKER["cost"] = 0.0


def get_usage() -> Dict[str, float]:
    return {"tokens": USAGE_TRACKER["tokens"], "cost": USAGE_TRACKER["cost"]}


def _record_usage(tokens: Optional[float], cost: Optional[float]) -> None:
    if tokens:
        USAGE_TRACKER["tokens"] += float(tokens)
    if cost:
        USAGE_TRACKER["cost"] += float(cost)


def _estimate_cost(tokens: Optional[float]) -> float:
    if not tokens:
        return 0.0
    # rough $2 per million tokens default
    return float(tokens) * 0.000002


async def _fake_llm(prompt: str, role: str) -> str:
    await asyncio.sleep(0.2)
    return f"[{role}] Suggestion and reasoning for: {prompt[:80]}…"


async def _call_llm(
    messages: List[Dict[str, str]],
    *,
    role: str,
    temperature: float = 0.3,
    max_tokens: int = 600,
    model_override: str | None = None,
) -> str:
    if USE_MOCK:
        text = await _fake_llm(messages[-1]["content"], role=role)
        approx_tokens = max(50, len(messages[-1]["content"]) // 2)
        _record_usage(approx_tokens, _estimate_cost(approx_tokens))
        return text

    try:
        response = await acompletion(
            model=model_override or LITELLM_MODEL,
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens,
        )
        content = response.choices[0].message["content"]
        if not content:
            raise ValueError("LLM response contained no content")
        usage = getattr(response, "usage", {}) or {}
        tokens = usage.get("total_tokens")
        cost = getattr(response, "response_cost", None)
        if isinstance(cost, dict):
            cost = cost.get("total_cost")
        if cost is None:
            cost = usage.get("total_cost")
        _record_usage(tokens, cost if cost is not None else _estimate_cost(tokens))
        return content.strip()
    except Exception as exc:
        logger.warning("LLM call failed, falling back to mock: %s", exc)
        return await _fake_llm(messages[-1]["content"], role=role)


async def produce_candidate(prompt: str, agent: AgentConfig) -> Dict[str, Any]:
    system_prompt = (
        f"You are {agent.name}, a specialist contributing to a multi-agent deliberation. "
        "Deliver a concrete, source-aware strategy. Include numbered steps where useful."
    )
    user_prompt = (
        f"Primary prompt:\n{prompt}\n\n"
        "Write a self-contained draft response in under 250 words."
    )
    text = await _call_llm(
        [{"role": "system", "content": system_prompt}, {"role": "user", "content": user_prompt}],
        role=agent.name,
        temperature=0.5,
        model_override=agent.model,
    )
    return {"persona": agent.name, "persona_prompt": agent.persona, "text": text}


async def criticize_and_revise(
    prompt: str,
    candidates: List[Dict[str, Any]],
):
    if USE_MOCK:
        return [{**c, "text": c["text"] + " (revised)"} for c in candidates]

    async def _revise(candidate: Dict[str, Any]) -> Dict[str, Any]:
        peer_views = [
            f"{c['persona']}: {c['text']}"
            for c in candidates
            if c["persona"] != candidate["persona"]
        ]
        peer_block = "\n\n".join(peer_views) or "No peer drafts available."
        messages = [
            {
                "role": "system",
                "content": (
                    f"You are {candidate['persona']} acting as a critic and reviser. "
                    "Identify factual gaps, risks, or missing steps in the peer drafts, then "
                    "return an improved version of your own answer."
                ),
            },
            {
                "role": "user",
                "content": (
                    f"Prompt:\n{prompt}\n\n"
                    f"Your previous draft:\n{candidate['text']}\n\n"
                    f"Peer drafts:\n{peer_block}\n\n"
                    "Output the improved answer only."
                ),
            },
        ]
        revised_text = await _call_llm(
            messages,
            role=f"{candidate['persona']} Critic",
            temperature=0.4,
        )
        return {**candidate, "text": revised_text}

    return await asyncio.gather(*[_revise(c) for c in candidates])


def _extract_json_fragment(text: str) -> str | None:
    match = re.search(r"\{.*\}", text, flags=re.S)
    return match.group(0) if match else None


async def judge_scores(
    prompt: str,
    revised: List[Dict[str, Any]],
    judges: Sequence[JudgeConfig],
) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    if not judges:
        judges = [JudgeConfig(name="DefaultJudge")]

    if USE_MOCK:
        base = 7.0
        scores = []
        details = []
        for i, c in enumerate(revised):
            score = round(base + (i % 3) * 0.5, 2)
            rationale = "Mock judge rationale"
            scores.append({"persona": c["persona"], "score": score, "rationale": rationale})
            details.append(
                {"persona": c["persona"], "judge": "MockJudge", "score": score, "rationale": rationale}
            )
        return scores, details

    async def _judge_candidate(candidate: Dict[str, Any], judge: JudgeConfig) -> Dict[str, Any]:
        rubric_text = ", ".join(judge.rubrics)
        messages = [
            {
                "role": "system",
                "content": (
                    f"You are {judge.name}, applying the rubric ({rubric_text}). "
                    "Score from 0-10 and justify briefly."
                ),
            },
            {
                "role": "user",
                "content": (
                    f"Prompt:\n{prompt}\n\n"
                    f"Candidate ({candidate['persona']}):\n{candidate['text']}\n\n"
                    "Return strict JSON of the form {\"score\": <0-10 number>, \"rationale\": \"...\"}."
                ),
            },
        ]
        raw = await _call_llm(
            messages,
            role=f"Judge:{judge.name}",
            temperature=0.2,
            max_tokens=400,
            model_override=judge.model,
        )
        fragment = _extract_json_fragment(raw)
        try:
            data = json.loads(fragment or raw)
            score_val = float(data.get("score", 6.5))
            rationale = data.get("rationale") or raw.strip()
        except Exception:
            score_val = 6.5
            rationale = raw.strip() or "Judge response unavailable."
        score_val = max(0.0, min(10.0, round(score_val, 2)))
        return {
            "persona": candidate["persona"],
            "judge": judge.name,
            "score": score_val,
            "rationale": rationale,
        }

    judge_details = []
    for judge in judges:
        judge_results = await asyncio.gather(*[_judge_candidate(c, judge) for c in revised])
        judge_details.extend(judge_results)

    aggregated: Dict[str, Dict[str, Any]] = {}
    for detail in judge_details:
        persona_entry = aggregated.setdefault(
            detail["persona"], {"persona": detail["persona"], "scores": [], "rationale": detail["rationale"]}
        )
        persona_entry["scores"].append(detail["score"])
        persona_entry["rationale"] = detail["rationale"]

    summary = []
    for persona, payload in aggregated.items():
        avg_score = sum(payload["scores"]) / max(1, len(payload["scores"]))
        summary.append(
            {
                "persona": persona,
                "score": round(avg_score, 2),
                "rationale": payload["rationale"],
            }
        )

    summary.sort(
        key=lambda entry: next(
            (idx for idx, candidate in enumerate(revised) if candidate["persona"] == entry["persona"]), 0
        )
    )

    return summary, judge_details


async def synthesize(prompt: str, revised: List[Dict[str, Any]], scores: List[Dict[str, Any]]):
    if USE_MOCK:
        best = max(zip(revised, scores), key=lambda rs: rs[1]["score"])[0]
        return f"Final Answer (Consultaion):\n\n{best['text']}\n\n— automatic synthesis"

    by_persona = {s["persona"]: s for s in scores}
    ranked = sorted(
        revised,
        key=lambda c: by_persona.get(c["persona"], {}).get("score", 0),
        reverse=True,
    )
    top_candidates = ranked[:2] if len(ranked) >= 2 else ranked
    candidate_block = "\n\n".join(
        f"Candidate: {c['persona']}\nScore: {by_persona.get(c['persona'], {}).get('score', 'n/a')}\n"
        f"Rationale: {by_persona.get(c['persona'], {}).get('rationale', 'n/a')}\n"
        f"Answer:\n{c['text']}"
        for c in top_candidates
    )
    messages = [
        {
            "role": "system",
            "content": (
                "You synthesize multiple agent answers into a single, concise, actionable response. "
                "Blend the strongest points, resolve conflicts, cite assumptions, and keep a confident tone."
            ),
        },
        {
            "role": "user",
            "content": (
                f"Prompt:\n{prompt}\n\n"
                f"Top candidates with judge scores:\n{candidate_block}\n\n"
                "Produce the final response. Include a short summary and numbered plan or bullet list."
            ),
        },
    ]
    return await _call_llm(messages, role="Synthesizer", temperature=0.35, max_tokens=700)
