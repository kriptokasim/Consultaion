import asyncio
import logging
from typing import Any, Dict, List

from agents import USE_MOCK, _call_llm
from llm_errors import classify_provider_exception
from utils.json_utils import extract_and_parse_json

logger = logging.getLogger(__name__)


async def run_red_team_analysis(proposal_text: str, lenses: List[str]) -> List[Dict[str, Any]]:
    """
    Runs adversarial critiques on proposal_text for each selected risk lens.
    Returns a unified list of critique items, each having:
      - lens: str
      - title: str
      - severity: str ('high' | 'medium' | 'low')
      - description: str
      - remediation: str
    """
    if USE_MOCK:
        # Seed mock results to prevent external LLM dependencies in dev/tests
        issues = []
        for idx, lens in enumerate(lenses):
            severity = "high" if idx == 0 else ("medium" if idx == 1 else "low")
            issues.append({
                "lens": lens,
                "title": f"Vulnerability in {lens.capitalize()} controls",
                "severity": severity,
                "description": f"The proposal's design contains design gaps that may lead to operational failures under the {lens} lens.",
                "remediation": f"Implement validation rules, rate-limiting, and defensive architecture patterns for {lens} mitigation."
            })
        return issues

    async def _evaluate_lens(lens: str) -> List[Dict[str, Any]]:
        prompt = (
            f"You are a Senior Red Team Engineer and Adversarial Reviewer specializing in the '{lens}' risk lens.\n"
            f"Analyze the following user proposal:\n"
            f"---\n"
            f"{proposal_text}\n"
            f"---\n\n"
            f"Identify up to 3 distinct vulnerabilities, risks, or flaws under this '{lens}' perspective.\n"
            f"For each issue, assign a severity: 'high', 'medium', or 'low'.\n"
            f"Your output MUST be a valid JSON array of objects, where each object has these exact keys:\n"
            f"- 'title': short title of the issue\n"
            f"- 'severity': 'high' | 'medium' | 'low'\n"
            f"- 'description': detailed description of the risk\n"
            f"- 'remediation': actionable steps to resolve the risk\n\n"
            f"Do not include markdown tags (like ```json) in your response, output raw JSON only."
        )

        messages = [
            {"role": "system", "content": "You are a professional adversarial critique engine. Output strictly valid JSON arrays."},
            {"role": "user", "content": prompt}
        ]

        try:
            text, _ = await _call_llm(
                messages,
                role=f"RedTeam_{lens}",
                temperature=0.2,
                max_tokens=800
            )

            parsed = extract_and_parse_json(text)
            if parsed is None:
                raise ValueError("redteam model returned unparseable JSON")
            if not isinstance(parsed, list):
                logger.warning(
                    "RedTeam %s returned JSON with unexpected shape: %s",
                    lens,
                    type(parsed).__name__,
                )
                raise ValueError("redteam model returned JSON that is not a list")

            normalized: List[Dict[str, Any]] = []
            for raw_item in parsed:
                if not isinstance(raw_item, dict):
                    logger.warning(
                        "RedTeam %s returned a non-object list item: %s",
                        lens,
                        type(raw_item).__name__,
                    )
                    continue
                item = dict(raw_item)
                item["lens"] = lens
                sev = str(item.get("severity", "medium")).lower()
                if sev not in ["high", "medium", "low"]:
                    sev = "medium"
                item["severity"] = sev
                normalized.append(item)

            if not normalized and parsed:
                raise ValueError("redteam model returned no valid issue objects")
            return normalized
        except Exception as exc:
            # Safe message only — raw error stays server-side.
            logger.error("Failed red team evaluation for lens %s: %s", lens, exc)
            safe = classify_provider_exception(exc)
            return [{
                "lens": lens,
                "title": f"Incomplete {lens.capitalize()} review",
                "severity": "medium",
                "description": f"The adversarial review for this lens failed ({safe.code.value}); treat this lens as not yet reviewed.",
                "remediation": "Retry the review for this lens; if it keeps failing, inspect provider configuration."
            }]

    tasks = [_evaluate_lens(lens) for lens in lenses]
    results = await asyncio.gather(*tasks)

    # Flatten the list of lists
    flat_issues = []
    for res_list in results:
        flat_issues.extend(res_list)

    return flat_issues
