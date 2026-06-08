import asyncio
import json
import logging
from typing import Dict, Any, List
from agents import _call_llm, USE_MOCK

logger = logging.getLogger(__name__)

async def evaluate_synthesis_challenge(
    prompt: str,
    debate_transcript: str,
    current_synthesis: str,
    pushback_text: str
) -> Dict[str, Any]:
    """
    Evaluates a user challenge/pushback against the current debate synthesis.
    Returns a dict with: 'decision' ('defend' | 'concede' | 'revise'), 'reasoning', and 'revised_synthesis'.
    """
    if USE_MOCK:
        await asyncio.sleep(0.5)
        # Determine mock decision based on pushback content
        pushback_lower = pushback_text.lower()
        if "error" in pushback_lower or "wrong" in pushback_lower or "missing" in pushback_lower:
            decision = "concede"
            reasoning = "The user correctly points out a gap. The debate transcript supports the user's premise regarding local network sniffing risks."
            revised_synthesis = current_synthesis + "\n\n*Correction/Concession: Added explicit TLS requirement to address local network eavesdropping risks.*"
        elif "clarify" in pushback_lower or "add" in pushback_lower or "detail" in pushback_lower:
            decision = "revise"
            reasoning = "The user raises a helpful request for nuance. While the original recommendation holds, adding detail on rotation policy improves completeness."
            revised_synthesis = current_synthesis + "\n\n*Revision: Enforce a weekly API key rotation policy to minimize damage in case of key exposure.*"
        else:
            decision = "defend"
            reasoning = "The synthesis already accounts for this. The models in the debate evaluated federated sync and concluded local caching has superior offline performance."
            revised_synthesis = current_synthesis

        return {
            "decision": decision,
            "reasoning": reasoning,
            "revised_synthesis": revised_synthesis
        }

    # Real LLM execution
    system_msg = (
        "You are a debate coordinator and synthesis referee. The user is challenging the final synthesis "
        "of a multi-agent debate. Read the context (prompt, debate transcript, current synthesis) "
        "and the user's pushback. Determine the best course of action and respond in JSON with:\n"
        "1. 'decision': one of 'defend', 'concede', 'revise'\n"
        "2. 'reasoning': a clear response to the user's critique\n"
        "3. 'revised_synthesis': the new full synthesis text (must match input if 'defend')"
    )

    user_msg = (
        f"Debate Prompt: '{prompt}'\n\n"
        f"Debate Transcript:\n{debate_transcript}\n\n"
        f"Current Synthesis:\n{current_synthesis}\n\n"
        f"User Pushback/Critique: '{pushback_text}'\n\n"
        f"Analyze this pushback. Be objective: concede if the user is factually correct, "
        f"revise if nuance is needed, or defend if the current synthesis is correct. "
        f"Output raw JSON only."
    )

    messages = [
        {"role": "system", "content": system_msg},
        {"role": "user", "content": user_msg}
    ]

    try:
        text, _ = await _call_llm(
            messages,
            role="Challenge_Coordinator",
            temperature=0.3,
            max_tokens=1500
        )

        clean_text = text.strip()
        if clean_text.startswith("```"):
            lines = clean_text.splitlines()
            if lines[0].startswith("```"):
                lines = lines[1:]
            if lines and lines[-1].startswith("```"):
                lines = lines[:-1]
            clean_text = "\n".join(lines).strip()

        data = json.loads(clean_text)
        # Validate keys
        if data.get("decision") not in ["defend", "concede", "revise"]:
            data["decision"] = "defend"
        if "reasoning" not in data:
            data["reasoning"] = "No reasoning provided."
        if "revised_synthesis" not in data or data["decision"] == "defend":
            data["revised_synthesis"] = current_synthesis

        return data
    except Exception as exc:
        logger.error(f"Synthesis challenge evaluation failed: {exc}")
        return {
            "decision": "defend",
            "reasoning": f"Could not process challenge: {exc}",
            "revised_synthesis": current_synthesis
        }
