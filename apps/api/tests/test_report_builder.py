"""Tests for report builder — JSON parsing, heuristic fallback, and validation."""

import json

from reporting.report_builder import (
    _heuristic_extract,
    _try_parse_json_report,
    build_report_from_synthesis,
)
from reporting.schemas import DecisionReport, KeyFinding, Verdict


class TestDecisionReportSchema:
    def test_default_report(self):
        report = DecisionReport()
        assert report.title == "Decision Report"
        assert report.executive_summary == ""
        assert report.verdict.decision_type == "mixed"
        assert report.key_findings == []

    def test_verdict_confidence_bounds(self):
        v = Verdict(confidence=0.0)
        assert v.confidence == 0.0
        v = Verdict(confidence=1.0)
        assert v.confidence == 1.0

    def test_key_finding_importance(self):
        f = KeyFinding(title="Test", summary="Summary", importance="critical")
        assert f.importance == "critical"


class TestTryParseJsonReport:
    def test_valid_json(self):
        data = {
            "title": "Test Report",
            "executive_summary": "Summary text",
            "verdict": {"recommendation": "Proceed", "confidence": 0.8, "decision_type": "proceed", "rationale": "Because"},
        }
        text = json.dumps(data)
        report = _try_parse_json_report(text)
        assert report is not None
        assert report.title == "Test Report"
        assert report.verdict.confidence == 0.8

    def test_json_in_code_fence(self):
        data = {
            "title": "Fenced Report",
            "verdict": {"recommendation": "Defer", "confidence": 0.6, "decision_type": "defer", "rationale": "Need more info"},
        }
        text = f"Here is the report:\n\n```json\n{json.dumps(data)}\n```\n\nHope this helps."
        report = _try_parse_json_report(text)
        assert report is not None
        assert report.title == "Fenced Report"

    def test_invalid_json_returns_none(self):
        report = _try_parse_json_report("This is just plain text with no JSON.")
        assert report is None

    def test_partial_json_returns_none(self):
        report = _try_parse_json_report("Here is some { partial json } that is not valid.")
        assert report is None


class TestHeuristicExtract:
    def test_extracts_verdict_from_keywords(self):
        text = "## Conclusion\nWe recommend proceeding with the plan. The analysis supports a proceed decision."
        report = _heuristic_extract("Test prompt", text)
        assert report.verdict.decision_type == "proceed"

    def test_extracts_findings(self):
        text = "## Key Findings\n- Critical finding about security\n- Minor performance concern\n- Important architectural insight"
        report = _heuristic_extract("Test", text)
        assert len(report.key_findings) == 3
        assert report.key_findings[0].importance == "high"

    def test_extracts_next_actions(self):
        text = "## Next Steps\n- Deploy to staging\n- Run security audit\n- Schedule review"
        report = _heuristic_extract("Test", text)
        assert len(report.next_actions) == 3
        assert report.next_actions[0].priority == "now"

    def test_fallback_summary(self):
        text = "This is a long synthesis text that should be used as the executive summary when no named sections are found."
        report = _heuristic_extract("Test", text)
        assert "long synthesis text" in report.executive_summary

    def test_model_positions_from_responses(self):
        responses = [
            {"model": "GPT-4o", "content": "I agree with the approach but have concerns about cost."},
            {"model": "Claude", "content": "The plan looks solid."},
        ]
        report = _heuristic_extract("Test", "Some synthesis", model_responses=responses)
        assert len(report.model_positions) == 2
        assert report.model_positions[0].model == "GPT-4o"
        assert report.model_positions[0].stance == "concerned"
        assert report.model_positions[1].stance == "supportive"


class TestBuildReportFromSynthesis:
    def test_json_synthesis(self):
        data = {
            "title": "JSON Report",
            "verdict": {"recommendation": "Reject", "confidence": 0.9, "decision_type": "reject", "rationale": "Too risky"},
        }
        report = build_report_from_synthesis("My question", json.dumps(data))
        assert report.title == "JSON Report"
        assert report.verdict.decision_type == "reject"

    def test_markdown_synthesis(self):
        text = "## Conclusion\nProceed with caution. Confidence: 75%\n\n## Key Findings\n- Security is adequate\n- Cost is high"
        report = build_report_from_synthesis("Should we launch?", text)
        assert report.verdict.decision_type == "proceed"
        assert len(report.key_findings) >= 1

    def test_empty_synthesis(self):
        report = build_report_from_synthesis("Question", "")
        assert report is not None
        assert report.title == "Question"

    def test_prompt_used_as_title(self):
        report = build_report_from_synthesis("My specific question about AI", "Some synthesis text.")
        assert report.title == "My specific question about AI"


class TestContextNeededField:
    """Verify the context_needed field is available on the synthesis DecisionReport schema."""

    def test_context_needed_field_exists_on_decision_report(self):
        from reporting.synthesis_schema import DecisionReport as SynthesisDecisionReport
        report = SynthesisDecisionReport()
        assert hasattr(report, "context_needed")
        assert report.context_needed == []

    def test_context_needed_accepts_values(self):
        from reporting.synthesis_schema import DecisionReport as SynthesisDecisionReport
        report = SynthesisDecisionReport(context_needed=["ARR", "ICP", "retention rate"])
        assert len(report.context_needed) == 3
        assert "ARR" in report.context_needed

