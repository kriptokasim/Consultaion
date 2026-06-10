"""Verifier/critic quality gate.

Compares a draft structured decision report against the original candidate model
responses to calculate completeness, check for hallucinations or unsupported assertions,
and flag if a revision loop is needed.
"""

from __future__ import annotations

import json
import logging
import re
from typing import Dict, Any, List

from agents import call_llm_for_role
from config import settings

logger = logging.getLogger(__name__)


async def verify_synthesis_report(
    prompt: str,
    responses: List[Dict[str, Any]],
    draft_report_json: str,
    debate_id: str | None = None,
    usage: Any | None = None,
) -> Dict[str, Any]:
    """Review the draft decision report against the source responses to calculate quality metrics."""
    if not responses or not draft_report_json:
        return {
            "completeness_score": None,
            "faithfulness_score": None,
            "has_hallucinations": False,
            "needs_revision": False,
            "critic_feedback": "Empty responses or draft.",
            "verification_error": False,
            "verification_source": "fallback",
            "specificity_score": None,
            "genericity_risk": "medium",
        }

    if settings.USE_MOCK:
        # Return static passing verification in mock mode
        return {
            "completeness_score": 0.95,
            "faithfulness_score": 0.98,
            "has_hallucinations": False,
            "needs_revision": False,
            "critic_feedback": "[MOCK] Verifier pass completed successfully. Draft is highly faithful.",
            "verification_error": False,
            "verification_source": "mock",
            "specificity_score": 0.7,
            "genericity_risk": "low",
        }

    # Format the candidate responses for the critic
    responses_block = ""
    for idx, resp in enumerate(responses):
        name = resp.get("persona", resp.get("model", f"Model-{idx}"))
        content = resp.get("text", resp.get("content", ""))
        responses_block += f"### Model: {name}\nResponse:\n{content}\n\n---\n\n"

    system_prompt = (
        "You are an AI verifier/critic. Your job is to compare a DRAFT Decision Report "
        "against the ORIGINAL candidate model responses to verify accuracy, completeness, faithfulness, and specificity.\n"
        "Check for:\n"
        "1. Hallucinations: Does the draft report claim findings/options/arguments that WERE NOT in any source responses?\n"
        "2. Faithfulness: Does the draft report misrepresent any model stances or consensus points?\n"
        "3. Completeness: Did the draft report omit any critical warnings, dissenting views, or key evidence from the source?\n"
        "4. Specificity: Is this report specifically tailored to the user's actual context/question, or is it a generic checklist? "
        "A report full of generic SaaS advice without connection to the user's specific situation scores low on specificity.\n\n"
        "You MUST respond ONLY in valid JSON format matching this schema:\n"
        "{\n"
        "  \"completeness_score\": <float from 0.0 to 1.0>,\n"
        "  \"faithfulness_score\": <float from 0.0 to 1.0>,\n"
        "  \"has_hallucinations\": <boolean>,\n"
        "  \"needs_revision\": <boolean: true if faithfulness or completeness < 0.85 or has_hallucinations is true>,\n"
        "  \"specificity_score\": <float from 0.0 to 1.0: how tailored is this report to the user's specific context>,\n"
        "  \"genericity_risk\": \"low | medium | high\",\n"
        "  \"critic_feedback\": \"Detailed constructive critique listing specific fixes needed, or empty string if perfect\"\n"
        "}"
    )

    user_content = (
        f"**Original User Question:**\n{prompt}\n\n"
        f"**Original Candidate Responses:**\n\n{responses_block}\n"
        f"**Draft Decision Report (JSON):**\n\n{draft_report_json}"
    )

    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_content},
    ]

    try:
        raw, call_usage = await call_llm_for_role(
            messages,
            role="Arena:SynthesisCritic",
            temperature=0.1,
            max_tokens=400,
            debate_id=debate_id,
        )
        if usage is not None and hasattr(usage, "add_call"):
            usage.add_call(call_usage)

        match = re.search(r"\{.*\}", raw, flags=re.S)
        raw_json = match.group(0) if match else raw
        
        data = json.loads(raw_json)
        
        completeness = float(data.get("completeness_score", 0.9))
        faithfulness = float(data.get("faithfulness_score", 0.9))
        has_hallucinations = bool(data.get("has_hallucinations", False))
        critic_feedback = str(data.get("critic_feedback", ""))
        specificity_score = float(data.get("specificity_score", 0.5))
        genericity_risk = str(data.get("genericity_risk", "medium"))
        if genericity_risk not in ("low", "medium", "high"):
            genericity_risk = "medium"
        
        # Override needs_revision logic to make it robust
        needs_revision = bool(data.get("needs_revision", False))
        if completeness < 0.85 or faithfulness < 0.85 or has_hallucinations:
            needs_revision = True

        # If genericity risk is high, flag in feedback
        if genericity_risk == "high":
            if critic_feedback:
                critic_feedback += " Report is too generic; needs user/project-specific context."
            else:
                critic_feedback = "Report is too generic; needs user/project-specific context."
            
        return {
            "completeness_score": completeness,
            "faithfulness_score": faithfulness,
            "has_hallucinations": has_hallucinations,
            "needs_revision": needs_revision,
            "critic_feedback": critic_feedback,
            "verification_error": False,
            "verification_source": "critic",
            "specificity_score": specificity_score,
            "genericity_risk": genericity_risk,
        }

    except Exception as exc:
        logger.warning("Synthesis verification pass failed: %s. Marking as unverified.", exc)
        return {
            "completeness_score": None,
            "faithfulness_score": None,
            "has_hallucinations": False,
            "needs_revision": False,
            "critic_feedback": "Verifier service temporarily unavailable.",
            "verification_error": True,
            "verification_source": "unavailable",
            "specificity_score": None,
            "genericity_risk": "medium",
        }
