"""Structured report integrity check utilities.

Detects raw JSON leak, fenced code blocks, and schema-key leakage
before structured decision reports are finalized.
"""

import json
import re
from typing import Any, List, Tuple


def contains_raw_json_leak(val: Any) -> bool:
    """Check if a string value contains raw JSON leakage or fenced code blocks."""
    if not isinstance(val, str):
        return False

    t = val.strip()

    # Check for markdown code fences (specifically json or generic ones)
    if t.startswith("```json") or t.startswith("```"):
        return True

    # Check for starting '{' combined with schema key containment
    if t.startswith("{") and any(k in t for k in ('"verdict"', '"executive_summary"', '"context_needed"', '"unique_insights"', '"quality_meta"')):
        return True

    # Check if at least 2 key schema markers are found within the text
    schema_markers = [
        '"verdict"',
        '"executive_summary"',
        '"context_needed"',
        '"unique_insights"',
        '"quality_meta"',
        '"risks_and_assumptions"',
        '"model_positions"',
        '"key_findings"',
    ]
    marker_count = sum(1 for m in schema_markers if m in t)
    if marker_count >= 2:
        return True

    return False


def looks_like_incomplete_json(text: str) -> bool:
    """Check if the raw content looks like incomplete or truncated JSON.
    
    Returns True if the content appears to contain JSON structures but is not valid JSON.
    """
    if not text:
        return False
        
    t = text.strip()
    
    # Try to parse it. If it parses successfully, it's not incomplete JSON.
    try:
        candidate = t
        if t.startswith("```json"):
            # Check if there is a matching ```
            if t.count("```") < 2:
                return True
            # Extract content between fences
            match = re.search(r"```json\s*(.*?)\s*```", t, re.DOTALL)
            if match:
                candidate = match.group(1)
                
        json.loads(candidate)
        return False  # parsed successfully
    except json.JSONDecodeError:
        # Failed to parse. Let's see if it looks like it was intended as JSON.
        if t.startswith("```json"):
            return True
        if t.startswith("{") or t.endswith("}"):
            return True
        # Or check if it contains typical JSON schema keys
        schema_markers = ['"verdict"', '"executive_summary"', '"key_findings"']
        if any(m in t for m in schema_markers):
            return True
        return False


def validate_report_integrity(report: Any) -> Tuple[bool, List[str]]:
    """Validate all string fields of a decision report for raw JSON leakages."""
    problems = []

    if hasattr(report, "model_dump"):
        data = report.model_dump()
    elif hasattr(report, "dict"):
        data = report.dict()
    elif isinstance(report, dict):
        data = report
    else:
        return True, []

    def walk_and_check(val: Any, path: str):
        if isinstance(val, str):
            if contains_raw_json_leak(val):
                problems.append(f"Field '{path}' contains raw JSON leak: {val[:100]}...")
        elif isinstance(val, dict):
            for k, v in val.items():
                walk_and_check(v, f"{path}.{k}" if path else k)
        elif isinstance(val, list):
            for idx, item in enumerate(val):
                walk_and_check(item, f"{path}[{idx}]")

    walk_and_check(data, "")

    return len(problems) == 0, problems
