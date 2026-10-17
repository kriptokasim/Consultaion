"""Decision-report pipeline: token budget, repair model, honest scores, ownership."""

import json
from unittest.mock import AsyncMock, patch

import pytest
from reporting.synthesizer import StructuredSynthesisError, generate_decision_report

from tests.utils import seed_debate

pytestmark = pytest.mark.anyio

REPORT = {
    "title": "Kafka Decision Report",
    "executive_summary": "Kafka fits the scaling need.",
    "verdict": {
        "recommendation": "Adopt Kafka.",
        "confidence": 0.9,
        "decision_type": "proceed",
        "rationale": "Consensus on scaling.",
    },
    "key_findings": [
        {"title": "Scaling", "summary": "Supports high throughput.", "importance": "critical"}
    ],
    "options_considered": [],
    "model_positions": [],
    "risks_and_assumptions": [],
    "recommendation_table": [],
    "next_actions": [],
    "caveats": [],
    "dissenting_views": [],
    "unique_insights": [],
}

ANALYSIS = {
    "consensus_claims": [],
    "contested_claims": [],
    "contradictions_count": 0,
    "contradiction_details": [],
    "divergence_score": 0.0,
}


def _patches(critic):
    return (
        patch("reporting.synthesizer.evaluate_models_blind", new_callable=AsyncMock, return_value=[]),
        patch(
            "reporting.synthesizer.run_semantic_claims_analysis",
            new_callable=AsyncMock,
            return_value=ANALYSIS,
        ),
        patch("reporting.synthesis_critic.verify_synthesis_report", critic),
        patch("reporting.synthesizer.call_llm_for_role", new_callable=AsyncMock),
        patch("reporting.synthesizer.settings"),
    )


async def test_draft_and_repair_use_the_synthesis_budget_and_model():
    seed_debate("report-budget")
    critic = AsyncMock(return_value={"needs_revision": False, "has_hallucinations": False})
    p_eval, p_claims, p_critic, p_call, p_settings = _patches(critic)
    with p_eval, p_claims, p_critic, p_call as call, p_settings as settings:
        settings.USE_MOCK = False
        settings.ENABLE_SYNTHESIS_REVISE = True
        settings.SYNTHESIS_MAX_TOKENS = 3200
        call.side_effect = [("not json", AsyncMock()), (json.dumps(REPORT), AsyncMock())]

        report = await generate_decision_report(
            "Adopt Kafka?", [{"persona": "M1", "content": "Yes."}], "report-budget",
            model_override="synth-model",
        )

    draft_kwargs = call.await_args_list[0].kwargs
    repair_kwargs = call.await_args_list[1].kwargs
    assert draft_kwargs["max_tokens"] == 3200
    assert repair_kwargs["max_tokens"] == 3200
    assert repair_kwargs["model_id"] == "synth-model"
    # The critic returned no scores: telemetry must not invent perfect ones.
    assert report.telemetry["report_quality_scores"] == {"completeness": None, "faithfulness": None}


async def test_ownership_loss_is_not_wrapped_as_a_synthesis_failure():
    from orchestration.execution_lease import ExecutionSupersededError

    seed_debate("report-ownership")
    critic = AsyncMock(side_effect=ExecutionSupersededError("taken over"))
    p_eval, p_claims, p_critic, p_call, p_settings = _patches(critic)
    with p_eval, p_claims, p_critic, p_call as call, p_settings as settings:
        settings.USE_MOCK = False
        settings.SYNTHESIS_MAX_TOKENS = 2000
        call.return_value = (json.dumps(REPORT), AsyncMock())

        with pytest.raises(ExecutionSupersededError):
            await generate_decision_report(
                "Adopt Kafka?", [{"persona": "M1", "content": "Yes."}], "report-ownership"
            )


async def test_other_verification_errors_still_become_structured_failures():
    seed_debate("report-other-error")
    critic = AsyncMock(side_effect=RuntimeError("critic down"))
    p_eval, p_claims, p_critic, p_call, p_settings = _patches(critic)
    with p_eval, p_claims, p_critic, p_call as call, p_settings as settings:
        settings.USE_MOCK = False
        settings.SYNTHESIS_MAX_TOKENS = 2000
        call.return_value = (json.dumps(REPORT), AsyncMock())

        with pytest.raises(StructuredSynthesisError):
            await generate_decision_report(
                "Adopt Kafka?", [{"persona": "M1", "content": "Yes."}], "report-other-error"
            )
