"""Per-model rubric scoring evaluator.

Assesses candidate model responses based on a 3-part rubric:
1. Logic & Correctness (depth, accuracy, reasoning)
2. Completeness (answering all parts of the user request)
3. Conciseness & Precision (avoiding bloat, clarity)

To reduce evaluation bias, model names and providers are redacted before scoring.
"""

from __future__ import annotations

import json
import logging
import re
from typing import Any, Dict, List

from agents import call_llm_for_role
from config import settings

logger = logging.getLogger(__name__)


def redact_model_names(
    text: str,
    model_mappings: Dict[str, str],
) -> str:
    """Replace model display names and provider names with anonymous placeholders (e.g. Model A)."""
    redacted = text
    # Order mappings from longest name to shortest to prevent partial matches
    sorted_keys = sorted(model_mappings.keys(), key=len, reverse=True)
    
    for real_name in sorted_keys:
        placeholder = model_mappings[real_name]
        
        # Exact word match replacement
        pattern = re.compile(re.escape(real_name), re.IGNORECASE)
        redacted = pattern.sub(placeholder, redacted)
        
        # Also replace provider words if they are part of the name
        provider_name = real_name.split()[0] if " " in real_name else real_name
        if len(provider_name) > 3 and provider_name.lower() not in ("model", "agent", "critic", "sota"):
            provider_pattern = re.compile(re.escape(provider_name), re.IGNORECASE)
            redacted = provider_pattern.sub(placeholder + " Provider", redacted)
            
    return redacted


async def evaluate_models_blind(
    prompt: str,
    responses: List[Dict[str, Any]],
    debate_id: str | None = None,
    usage: Any | None = None,
) -> List[Dict[str, Any]]:
    """Score model responses anonymously using a multi-rubric evaluator LLM."""
    if not responses:
        return []

    # 1. Build anonymous mappings
    model_mappings = {}
    reverse_mappings = {}
    for idx, resp in enumerate(responses):
        original_name = resp.get("persona", resp.get("model", f"Model-{idx}"))
        placeholder = f"Model_{chr(65 + idx)}"  # Model_A, Model_B, etc.
        model_mappings[original_name] = placeholder
        reverse_mappings[placeholder] = original_name

    # 2. Redact responses
    anonymized_responses = []
    for resp in responses:
        original_name = resp.get("persona", resp.get("model", ""))
        content = resp.get("text", resp.get("content", ""))
        
        # Redact both original content and query references
        redacted_content = redact_model_names(content, model_mappings)
        placeholder = model_mappings.get(original_name, "Model_Unknown")
        
        anonymized_responses.append({
            "placeholder": placeholder,
            "content": redacted_content,
        })

    if settings.USE_MOCK:
        # Return mock scores
        scores = []
        for resp in responses:
            name = resp.get("persona", resp.get("model", ""))
            scores.append({
                "model": name,
                "logic_score": 0.85,
                "completeness_score": 0.90,
                "conciseness_score": 0.80,
                "overall_score": 0.85,
                "rationale": f"[MOCK] High-quality structured analysis from {name}.",
            })
        return scores

    # 3. Build evaluation prompt
    candidates_block = ""
    for resp in anonymized_responses:
        candidates_block += f"### Candidate: {resp['placeholder']}\nResponse:\n{resp['content']}\n\n---\n\n"

    system_prompt = (
        "You are an expert AI evaluator. Assess the quality of the candidate responses "
        "provided for the original user query. Score each candidate on a scale of 0.0 to 1.0 (with 2 decimal precision) "
        "across three distinct rubrics:\n"
        "1. logic_score: depth of reasoning, factual accuracy, logical rigor.\n"
        "2. completeness_score: addresses all parts and implicit needs of the prompt.\n"
        "3. conciseness_score: precise language, actionability, lack of fluff.\n\n"
        "Generate an overall_score (average of the three rubrics) and a brief evaluation rationale for each candidate.\n"
        "You MUST output strictly in JSON format. Do not add markdown code fences, headers, or conversational text. "
        "Your response must be parseable by json.loads().\n"
        "Schema format:\n"
        "{\n"
        '  "evaluations": [\n'
        "    {\n"
        '      "candidate": "Model_A",\n'
        '      "logic_score": 0.90,\n'
        '      "completeness_score": 0.85,\n'
        '      "conciseness_score": 0.95,\n'
        '      "overall_score": 0.90,\n'
        '      "rationale": "Detailed explanation..."\n'
        "    }\n"
        "  ]\n"
        "}"
    )

    user_content = (
        f"**Original User Prompt:**\n{prompt}\n\n"
        f"**Anonymized Candidate Responses:**\n\n{candidates_block}"
    )

    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_content},
    ]

    try:
        raw, call_usage = await call_llm_for_role(
            messages,
            role="Arena:ModelEvaluator",
            temperature=0.2,
            max_tokens=800,
            debate_id=debate_id,
        )
        if usage is not None and hasattr(usage, "add_call"):
            usage.add_call(call_usage)

        # Extract JSON
        match = re.search(r"\{.*\}", raw, flags=re.S)
        raw_json = match.group(0) if match else raw
        
        data = json.loads(raw_json)
        evals = data.get("evaluations", [])
        
        results = []
        for val in evals:
            placeholder = val.get("candidate")
            original_name = reverse_mappings.get(placeholder)
            if not original_name:
                continue
                
            results.append({
                "model": original_name,
                "logic_score": float(val.get("logic_score", 0.7)),
                "completeness_score": float(val.get("completeness_score", 0.7)),
                "conciseness_score": float(val.get("conciseness_score", 0.7)),
                "overall_score": float(val.get("overall_score", 0.7)),
                "rationale": str(val.get("rationale", "")),
            })
            
        # Ensure we have scores for all models, even if JSON failed some
        scored_models = {r["model"] for r in results}
        for name in model_mappings.keys():
            if name not in scored_models:
                results.append({
                    "model": name,
                    "logic_score": 0.7,
                    "completeness_score": 0.7,
                    "conciseness_score": 0.7,
                    "overall_score": 0.7,
                    "rationale": "Evaluator parser fallback default score.",
                })
                
        return results

    except Exception as exc:
        logger.warning("Blind model evaluation failed: %s. Returning fallback scores.", exc)
        # Fallback scores
        results = []
        for resp in responses:
            name = resp.get("persona", resp.get("model", ""))
            results.append({
                "model": name,
                "logic_score": 0.7,
                "completeness_score": 0.7,
                "conciseness_score": 0.7,
                "overall_score": 0.7,
                "rationale": f"Fallback rating due to evaluator error: {exc}",
            })
        return results
