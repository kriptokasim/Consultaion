import asyncio
import json
import logging
from typing import Any, Dict, List

from agents import USE_MOCK, _call_llm

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

            # Strip markdown if any
            clean_text = text.strip()
            if clean_text.startswith("```"):
                lines = clean_text.splitlines()
                if lines[0].startswith("```"):
                    lines = lines[1:]
                if lines and lines[-1].startswith("```"):
                    lines = lines[:-1]
                clean_text = "\n".join(lines).strip()

            parsed = json.loads(clean_text)
            if isinstance(parsed, list):
                for item in parsed:
                    item["lens"] = lens
                    # Normalize severity
                    sev = str(item.get("severity", "medium")).lower()
                    if sev not in ["high", "medium", "low"]:
                        sev = "medium"
                    item["severity"] = sev
                return parsed
            else:
                logger.warning(f"RedTeam {lens} returned JSON that is not a list: {clean_text}")
                return []
        except Exception as exc:
            logger.error(f"Failed red team evaluation for lens {lens}: {exc}")
            # Fallback single issue
            return [{
                "lens": lens,
                "title": f"Incomplete {lens.capitalize()} review",
                "severity": "medium",
                "description": f"The adversarial review for this lens encountered a parser error: {exc}",
                "remediation": "Review proposal manual controls for standard security compliance."
            }]

    tasks = [_evaluate_lens(lens) for lens in lenses]
    results = await asyncio.gather(*tasks)
    
    # Flatten the list of lists
    flat_issues = []
    for res_list in results:
        flat_issues.extend(res_list)

    return flat_issues
