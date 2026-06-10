"""Tests for the upgraded synthesis engine.

Verifies:
1. Blind rubric scoring
2. Semantic claims contradiction classification
3. Quality verification check
4. Full structured decision report generation & repair loops
"""

import json
from unittest.mock import AsyncMock, patch

import pytest
from reporting.claim_contradiction import classify_contradiction
from reporting.model_evaluator import evaluate_models_blind, redact_model_names
from reporting.synthesis_critic import verify_synthesis_report
from reporting.synthesizer import run_semantic_claims_analysis, generate_decision_report


def test_redact_model_names():
    model_mappings = {
        "GPT-4o": "Model_A",
        "Claude 3.5 Sonnet": "Model_B",
    }
    
    # Check exact replacements
    text1 = "GPT-4o thinks this is good, whereas Claude 3.5 Sonnet disagrees."
    redacted1 = redact_model_names(text1, model_mappings)
    assert "GPT-4o" not in redacted1
    assert "Claude 3.5 Sonnet" not in redacted1
    assert "Model_A" in redacted1
    assert "Model_B" in redacted1

    # Check case insensitivity
    text2 = "gpt-4o thinks this is good."
    redacted2 = redact_model_names(text2, model_mappings)
    assert "Model_A" in redacted2


@pytest.mark.asyncio
async def test_evaluate_models_blind():
    prompt = "Which approach is better for high-throughput messaging?"
    responses = [
        {"persona": "Model-1", "content": "Use Apache Kafka because it partitions logs and scales horizontally."},
        {"persona": "Model-2", "content": "Use Redis Streams for low-latency in-memory message queues."},
    ]

    mock_eval_response = {
        "evaluations": [
            {
                "candidate": "Model_A",
                "logic_score": 0.90,
                "completeness_score": 0.85,
                "conciseness_score": 0.95,
                "overall_score": 0.90,
                "rationale": "Clear and detailed Kafka explanation."
            },
            {
                "candidate": "Model_B",
                "logic_score": 0.80,
                "completeness_score": 0.75,
                "conciseness_score": 0.90,
                "overall_score": 0.82,
                "rationale": "Redis explanation is concise but lacks partition details."
            }
        ]
    }

    with patch("reporting.model_evaluator.settings") as mock_settings:
        mock_settings.USE_MOCK = False
        with patch("reporting.model_evaluator.call_llm_for_role", new_callable=AsyncMock) as mock_call:
            mock_call.return_value = (json.dumps(mock_eval_response), AsyncMock())
            
            scores = await evaluate_models_blind(prompt, responses)
            
            assert len(scores) == 2
            assert scores[0]["model"] in ("Model-1", "Model-2")
            assert scores[0]["logic_score"] == 0.90
            assert scores[1]["overall_score"] == 0.82


@pytest.mark.asyncio
async def test_classify_contradiction():
    claim_a = "Use asynchronous tasks for performance."
    claim_b = "Do not use asynchronous tasks, use sync execution."

    mock_contra_response = {
        "is_contradictory": True,
        "explanation": "Explicit contradiction: async vs sync."
    }

    with patch("reporting.claim_contradiction.settings") as mock_settings:
        mock_settings.USE_MOCK = False
        with patch("reporting.claim_contradiction.call_llm_for_role", new_callable=AsyncMock) as mock_call:
            mock_call.return_value = (json.dumps(mock_contra_response), AsyncMock())
            
            res = await classify_contradiction(claim_a, claim_b)
            assert res["is_contradictory"] is True
            assert "Explicit contradiction" in res["explanation"]


@pytest.mark.asyncio
async def test_verify_synthesis_report():
    prompt = "Kafka vs Redis Streams"
    responses = [{"persona": "M1", "content": "Kafka is persistent"}]
    draft_report = "{\"title\": \"Draft\"}"

    mock_critic_response = {
        "completeness_score": 0.95,
        "faithfulness_score": 0.92,
        "has_hallucinations": False,
        "needs_revision": False,
        "critic_feedback": ""
    }

    with patch("reporting.synthesis_critic.settings") as mock_settings:
        mock_settings.USE_MOCK = False
        with patch("reporting.synthesis_critic.call_llm_for_role", new_callable=AsyncMock) as mock_call:
            mock_call.return_value = (json.dumps(mock_critic_response), AsyncMock())
            
            res = await verify_synthesis_report(prompt, responses, draft_report)
            assert res["completeness_score"] == 0.95
            assert res["has_hallucinations"] is False
            assert res["needs_revision"] is False


@pytest.mark.asyncio
async def test_run_semantic_claims_analysis():
    prompt = "Kafka vs Redis"
    responses = [
        {"persona": "M1", "content": "Kafka partitions scale logs."},
        {"persona": "M2", "content": "Redis streams store messages in memory."}
    ]

    # Mock claim extraction, embedding, and semantic similarity
    with patch("reporting.synthesizer._extract_claims_from_response", new_callable=AsyncMock) as mock_extract, \
         patch("reporting.synthesizer.get_claim_embeddings", new_callable=AsyncMock) as mock_embeddings, \
         patch("reporting.synthesizer.compute_semantic_similarity", new_callable=AsyncMock) as mock_similarity, \
         patch("reporting.synthesizer.classify_contradiction", new_callable=AsyncMock) as mock_contra:
         
        mock_extract.side_effect = [
            ["Kafka scales logs"],
            ["Redis streams store messages in memory"]
        ]
        mock_embeddings.return_value = [None, None]
        mock_similarity.return_value = 0.50  # unrelated claims
        mock_contra.return_value = {"is_contradictory": False}
        
        analysis = await run_semantic_claims_analysis(prompt, responses, "test-debate-id")
        
        assert len(analysis["consensus_claims"]) == 0
        assert len(analysis["contested_claims"]) == 2
        # divergence score should reflect two contested claims with no consensus
        assert analysis["divergence_score"] > 0.0


@pytest.mark.asyncio
async def test_generate_decision_report_and_repair():
    prompt = "Should we adopt Kafka?"
    responses = [{"persona": "M1", "content": "Adopt Kafka for horizontal scaling."}]

    mock_evals = [
        {
            "model": "M1",
            "logic_score": 0.9,
            "completeness_score": 0.9,
            "conciseness_score": 0.9,
            "overall_score": 0.9,
            "rationale": "Great."
        }
    ]

    mock_report_json = {
        "title": "Adopting Kafka Decision Report",
        "executive_summary": "Horizontal scaling makes Kafka suitable.",
        "verdict": {
            "recommendation": "Adopt Kafka.",
            "confidence": 0.90,
            "decision_type": "proceed",
            "rationale": "High consensus on scaling."
        },
        "key_findings": [
            {"title": "Horizontal Scaling", "summary": "Supports massive throughput.", "importance": "critical"}
        ],
        "options_considered": [],
        "model_positions": [],
        "risks_and_assumptions": [],
        "recommendation_table": [],
        "next_actions": [],
        "caveats": [],
        "dissenting_views": [],
        "unique_insights": []
    }

    mock_critic_res = {
        "completeness_score": 0.95,
        "faithfulness_score": 0.98,
        "has_hallucinations": False,
        "needs_revision": False,
        "critic_feedback": ""
    }

    with patch("reporting.synthesizer.evaluate_models_blind", new_callable=AsyncMock) as mock_eval, \
         patch("reporting.synthesizer.run_semantic_claims_analysis", new_callable=AsyncMock) as mock_claims, \
         patch("reporting.synthesis_critic.verify_synthesis_report", new_callable=AsyncMock) as mock_critic, \
         patch("reporting.synthesizer.call_llm_for_role", new_callable=AsyncMock) as mock_call, \
         patch("reporting.synthesizer.settings") as mock_settings:
         
        mock_settings.USE_MOCK = False
        mock_settings.ENABLE_SYNTHESIS_REVISE = True
        
        mock_eval.return_value = mock_evals
        mock_claims.return_value = {
            "consensus_claims": [],
            "contested_claims": [],
            "contradictions_count": 0,
            "contradiction_details": [],
            "divergence_score": 0.0
        }
        mock_critic.return_value = mock_critic_res
        
        # Scenario 1: LLM returns corrupted JSON initially, then repair tool fixes it
        corrupted_raw = "INVALID_JSON_START { ... }"
        mock_call.side_effect = [
            (corrupted_raw, AsyncMock()),  # Initial synthesizer call
            (json.dumps(mock_report_json), AsyncMock())  # Repair tool call
        ]
        
        report = await generate_decision_report(prompt, responses, "test-debate")
        
        assert report.title == "Adopting Kafka Decision Report"
        assert report.verdict.confidence == 0.90
        assert report.quality_meta.completeness_score == 0.95
        assert report.quality_meta.needs_revision is False
