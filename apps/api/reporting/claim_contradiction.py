"""Claim contradiction classifier.

A lightweight classifier using LiteLLM to identify active contradictions
among semantically related claims (similarity between 0.60 and 0.78).
"""

from __future__ import annotations

import json
import logging
import re
from typing import Dict, Any

from agents import call_llm_for_role
from config import settings

logger = logging.getLogger(__name__)


async def classify_contradiction(
    claim_a: str,
    claim_b: str,
    debate_id: str | None = None,
    usage: Any | None = None,
) -> Dict[str, Any]:
    """Determine if two related claims are actively contradictory or simply complementary."""
    if not claim_a.strip() or not claim_b.strip():
        return {"is_contradictory": False, "explanation": "Empty claims"}

    if settings.USE_MOCK:
        # Simple heuristic to simulate contradiction classification in mock mode
        lower_a = claim_a.lower()
        lower_b = claim_b.lower()
        
        opposites = [
            ("increase", "decrease"),
            ("yes", "no"),
            ("support", "oppose"),
            ("high", "low"),
            ("proceed", "reject"),
            ("do not", "should"),
            ("never", "always"),
        ]
        
        is_contra = False
        for op1, op2 in opposites:
            if (op1 in lower_a and op2 in lower_b) or (op2 in lower_a and op1 in lower_b):
                is_contra = True
                break
                
        return {
            "is_contradictory": is_contra,
            "explanation": f"[MOCK] Classified claim contradiction between '{claim_a}' and '{claim_b}'."
        }

    system_prompt = (
        "You are a logical validation agent. Compare two related statements and determine "
        "if they actively contradict each other (express opposing facts, incompatible conclusions, "
        "or mutually exclusive recommendations) or if they are complementary/non-contradictory. "
        "Output strictly valid JSON with no other formatting or explanation outside the JSON. "
        "Schema: {\"is_contradictory\": boolean, \"explanation\": \"short reason why\"}"
    )

    user_content = (
        f"Claim A: \"{claim_a}\"\n"
        f"Claim B: \"{claim_b}\"\n\n"
        "Are these contradictory?"
    )

    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_content},
    ]

    try:
        raw, call_usage = await call_llm_for_role(
            messages,
            role="Arena:ContradictionClassifier",
            temperature=0.1,
            max_tokens=200,
            debate_id=debate_id,
        )
        if usage is not None and hasattr(usage, "add_call"):
            usage.add_call(call_usage)

        # Parse JSON fragment from LLM output
        match = re.search(r"\{.*\}", raw, flags=re.S)
        if match:
            data = json.loads(match.group(0))
            is_contra = bool(data.get("is_contradictory", False))
            explanation = str(data.get("explanation", "Parsed explanation"))
            return {"is_contradictory": is_contra, "explanation": explanation}
            
        # Try raw fallback
        data = json.loads(raw.strip())
        return {
            "is_contradictory": bool(data.get("is_contradictory", False)),
            "explanation": str(data.get("explanation", "Parsed raw explanation")),
        }
    except Exception as exc:
        logger.warning(
            "Failed to classify contradiction between '%s' and '%s': %s. Defaulting to False.",
            claim_a,
            claim_b,
            exc,
        )
        return {
            "is_contradictory": False,
            "explanation": f"Classification failed: {exc}",
        }
