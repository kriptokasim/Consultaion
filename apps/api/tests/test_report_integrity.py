"""Tests for structured report integrity check logic, including JSON leakage detection."""

import pytest
import json
from reporting.report_integrity import (
    contains_raw_json_leak,
    looks_like_incomplete_json,
    validate_report_integrity,
)
from reporting.synthesis_schema import DecisionReport, Verdict, QualityMeta


def test_contains_raw_json_leak_detects_markdown_code_fences():
    assert contains_raw_json_leak("```json\n{\n  \"verdict\": \"proceed\"\n}\n```") is True
    assert contains_raw_json_leak("```\n{\n  \"verdict\": \"proceed\"\n}\n```") is True
    assert contains_raw_json_leak("Just regular text.") is False


def test_contains_raw_json_leak_detects_braced_schema_markers():
    assert contains_raw_json_leak('{"verdict": "proceed", "executive_summary": "ok"}') is True
    assert contains_raw_json_leak('{"title": "Decision Report", "key_findings": []}') is False


def test_contains_raw_json_leak_detects_multiple_schema_keys():
    # Detects when at least two key schema markers leak into the text
    text = 'We must consider the "verdict" and review the "executive_summary".'
    assert contains_raw_json_leak(text) is True

    # One marker is allowed/ignored (e.g. referencing one section)
    text_one = 'We must consider the "verdict".'
    assert contains_raw_json_leak(text_one) is False


def test_looks_like_incomplete_json():
    # Valid JSON parses, so it does not look like incomplete JSON
    assert looks_like_incomplete_json('{"verdict": "proceed"}') is False
    assert looks_like_incomplete_json('{"executive_summary": "We suggest that..."}') is False

    # Incomplete/truncated JSON fails decoding and matches starting markers
    assert looks_like_incomplete_json('{"verdict": "proceed"') is True
    assert looks_like_incomplete_json('{"executive_summary": "We suggests..."') is True
    assert looks_like_incomplete_json("```json\n{\n  \"verdict\": \"proceed\"") is True


def test_validate_report_integrity_clean_report():
    report = DecisionReport(
        title="Valid Report",
        executive_summary="This is a clean summary with no raw JSON fields.",
        verdict=Verdict(
            recommendation="Proceed with caution.",
            confidence=0.8,
            decision_type="proceed",
            rationale="Rationale looks clean.",
        )
    )
    ok, problems = validate_report_integrity(report)
    assert ok is True
    assert len(problems) == 0


def test_validate_report_integrity_dirty_report():
    report = DecisionReport(
        title="Dirty Report",
        executive_summary="```json\n{\"verdict\": \"leak\"}\n```",
        verdict=Verdict(
            recommendation="Proceed.",
            confidence=0.8,
            decision_type="proceed",
            rationale="Here is the leaked JSON: {\"verdict\": \"leak\", \"executive_summary\": \"leak\"}",
        )
    )
    ok, problems = validate_report_integrity(report)
    assert ok is False
    assert len(problems) == 2
    assert any("executive_summary" in p for p in problems)
    assert any("verdict.rationale" in p for p in problems)
