"""Report builder — converts raw model answers into a structured DecisionReport.

Handles:
1. Parsing structured JSON from LLM responses
2. Heuristic fallback when JSON parsing fails
3. Redacting unsafe content
4. Merging multiple model positions
"""

from __future__ import annotations

import json
import logging
import re
from typing import Any, Optional

from reporting.synthesis_schema import (
    DecisionReport,
    KeyFinding,
    ModelPosition,
    NextAction,
    RiskAssumption,
    Verdict,
)

logger = logging.getLogger(__name__)


def build_report_from_synthesis(
    prompt: str,
    synthesis_text: str,
    model_responses: Optional[list[dict[str, Any]]] = None,
    scores: Optional[dict[str, float]] = None,
) -> DecisionReport:
    """Build a structured DecisionReport from raw synthesis text.

    Attempts JSON parsing first, then falls back to heuristic extraction.
    """
    # Try to parse structured JSON from the synthesis
    report = _try_parse_json_report(synthesis_text)
    if report:
        if not report.title or report.title == "Decision Report":
            report.title = prompt[:120] if prompt else report.title
        return report

    # Heuristic fallback: extract sections from markdown-style text
    report = _heuristic_extract(prompt, synthesis_text, model_responses, scores)
    return report


def _try_parse_json_report(text: str) -> Optional[DecisionReport]:
    """Attempt to parse a DecisionReport from JSON in the text."""
    # Look for JSON block in markdown code fence
    json_match = re.search(r"```json\s*(.*?)\s*```", text, re.DOTALL)
    if json_match:
        try:
            data = json.loads(json_match.group(1))
            return DecisionReport(**data)
        except (json.JSONDecodeError, Exception) as exc:
            logger.debug("JSON fence parse failed: %s", exc)

    # Try parsing the entire text as JSON
    try:
        data = json.loads(text)
        return DecisionReport(**data)
    except (json.JSONDecodeError, Exception):
        pass

    # Look for { ... } block
    brace_match = re.search(r"\{.*\}", text, re.DOTALL)
    if brace_match:
        try:
            data = json.loads(brace_match.group(0))
            return DecisionReport(**data)
        except (json.JSONDecodeError, Exception):
            pass

    return None


def _heuristic_extract(
    prompt: str,
    text: str,
    model_responses: Optional[list[dict[str, Any]]] = None,
    scores: Optional[dict[str, float]] = None,
) -> DecisionReport:
    """Extract a structured report from plain text using heuristics."""
    title = prompt[:120] if prompt else "Decision Report"

    # Extract sections by looking for markdown headers
    sections = _split_sections(text)

    executive_summary = _extract_summary(text, sections)
    verdict = _extract_verdict(text, sections)
    key_findings = _extract_key_findings(sections)
    model_positions = _build_model_positions(model_responses, scores)
    risks = _extract_risks(sections)
    next_actions = _extract_next_actions(sections)
    caveats = _extract_caveats(text)

    return DecisionReport(
        title=title,
        executive_summary=executive_summary,
        verdict=verdict,
        key_findings=key_findings,
        model_positions=model_positions,
        risks_and_assumptions=risks,
        next_actions=next_actions,
        caveats=caveats,
    )


def _split_sections(text: str) -> dict[str, str]:
    """Split markdown text into sections by headers."""
    sections = {}
    current_key = "intro"
    current_lines = []

    for line in text.split("\n"):
        header_match = re.match(r"^#{1,3}\s+(.*)", line)
        if header_match:
            if current_lines:
                sections[current_key] = "\n".join(current_lines).strip()
            current_key = header_match.group(1).strip().lower()
            current_lines = []
        else:
            current_lines.append(line)

    if current_lines:
        sections[current_key] = "\n".join(current_lines).strip()

    return sections


def _extract_summary(text: str, sections: dict[str, str]) -> str:
    """Extract executive summary from text."""
    for key in ["summary", "executive summary", "overview", "conclusion"]:
        if key in sections:
            return sections[key][:500]

    # Use first paragraph if no named section found
    paragraphs = [p.strip() for p in text.split("\n\n") if p.strip() and not p.strip().startswith("#")]
    if paragraphs:
        return paragraphs[0][:500]

    return text[:500]


def _extract_verdict(text: str, sections: dict[str, str]) -> Verdict:
    """Extract verdict from text."""
    verdict_text = ""
    for key in ["verdict", "recommendation", "conclusion", "decision"]:
        if key in sections:
            verdict_text = sections[key]
            break

    if not verdict_text:
        verdict_text = text[-500:] if len(text) > 500 else text

    # Determine decision type from keywords
    lower = verdict_text.lower()
    if any(w in lower for w in ["proceed", "go ahead", "recommended", "strong support"]):
        decision_type = "proceed"
    elif any(w in lower for w in ["revise", "modify", "adjust", "needs work"]):
        decision_type = "revise"
    elif any(w in lower for w in ["defer", "delay", "wait", "postpone"]):
        decision_type = "defer"
    elif any(w in lower for w in ["reject", "against", "not recommended", "avoid"]):
        decision_type = "reject"
    else:
        decision_type = "mixed"

    # Extract confidence if mentioned
    conf_match = re.search(r"(\d{1,3})\s*%", text)
    confidence = float(conf_match.group(1)) / 100.0 if conf_match else 0.65

    return Verdict(
        recommendation=verdict_text[:300],
        confidence=confidence,
        decision_type=decision_type,
        rationale=verdict_text[:500],
    )


def _extract_key_findings(sections: dict[str, str]) -> list[KeyFinding]:
    """Extract key findings from sections."""
    findings = []
    finding_keys = ["findings", "key findings", "insights", "analysis", "results"]

    for key in finding_keys:
        if key in sections:
            content = sections[key]
            # Split by numbered items or bullet points
            items = re.split(r"\n(?:\d+[\.\)]\s+|\-\s+|\*\s+)", content)
            for item in items:
                item = item.strip()
                if len(item) > 10:
                    # Determine importance
                    importance = "medium"
                    lower = item.lower()
                    if any(w in lower for w in ["critical", "essential", "key", "important"]):
                        importance = "high"
                    elif any(w in lower for w in ["minor", "low", "secondary"]):
                        importance = "low"

                    findings.append(KeyFinding(
                        title=item[:80],
                        summary=item[:300],
                        importance=importance,
                    ))
            break

    # Limit to 6 findings
    return findings[:6]


def _build_model_positions(
    model_responses: Optional[list[dict[str, Any]]],
    scores: Optional[dict[str, float]],
) -> list[ModelPosition]:
    """Build model positions from responses and scores."""
    positions = []

    if model_responses:
        for resp in model_responses:
            model_name = resp.get("model", resp.get("persona", "Unknown"))
            content = resp.get("content", resp.get("text", ""))
            stance = "supportive"
            lower = content.lower()
            if any(w in lower for w in ["disagree", "however", "but", "concern", "risk"]):
                stance = "concerned"
            elif any(w in lower for w in ["neutral", "depends", "mixed"]):
                stance = "neutral"

            positions.append(ModelPosition(
                model=model_name,
                stance=stance,
                strongest_point=content[:200] if content else "No response captured",
                concern="See full response for details",
            ))

    if not positions and scores:
        for model, score in scores.items():
            positions.append(ModelPosition(
                model=model,
                stance="supportive" if score >= 0.7 else "neutral" if score >= 0.4 else "concerned",
                strongest_point=f"Scored {score:.1f}/1.0",
                concern="Low score may indicate concerns",
            ))

    return positions


def _extract_risks(sections: dict[str, str]) -> list[RiskAssumption]:
    """Extract risks and assumptions from sections."""
    risks = []
    risk_keys = ["risks", "risks and assumptions", "concerns", "challenges"]

    for key in risk_keys:
        if key in sections:
            content = sections[key]
            items = re.split(r"\n(?:\d+[\.\)]\s+|\-\s+|\*\s+)", content)
            for item in items:
                item = item.strip()
                if len(item) > 10:
                    severity = "medium"
                    lower = item.lower()
                    if any(w in lower for w in ["critical", "severe", "major"]):
                        severity = "critical"
                    elif any(w in lower for w in ["high", "significant"]):
                        severity = "high"
                    elif any(w in lower for w in ["low", "minor"]):
                        severity = "low"

                    risk_type = "risk"
                    if any(w in lower for w in ["assume", "assuming", "assumption"]):
                        risk_type = "assumption"

                    risks.append(RiskAssumption(
                        item=item[:200],
                        type=risk_type,
                        severity=severity,
                    ))
            break

    return risks[:10]


def _extract_next_actions(sections: dict[str, str]) -> list[NextAction]:
    """Extract next actions from sections."""
    actions = []
    action_keys = ["next steps", "next actions", "actions", "recommendations", "what to do"]

    for key in action_keys:
        if key in sections:
            content = sections[key]
            items = re.split(r"\n(?:\d+[\.\)]\s+|\-\s+|\*\s+)", content)
            for i, item in enumerate(items):
                item = item.strip()
                if len(item) > 5:
                    priority = "now" if i < 2 else "next" if i < 4 else "later"
                    actions.append(NextAction(
                        action=item[:200],
                        priority=priority,
                    ))
            break

    return actions[:6]


def _extract_caveats(text: str) -> list[str]:
    """Extract caveats/disclaimers from text."""
    caveats = []
    caveat_patterns = [
        r"(?:caveat|note|disclaimer|warning)[:\s]*(.*?)(?:\n|$)",
        r"(?:important to note)[:\s]*(.*?)(?:\n|$)",
    ]
    for pattern in caveat_patterns:
        matches = re.findall(pattern, text, re.IGNORECASE)
        for match in matches:
            if len(match.strip()) > 5:
                caveats.append(match.strip()[:200])

    return caveats[:5]
