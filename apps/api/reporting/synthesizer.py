"""Structured decision report synthesizer.

Orchestrates:
1. Blind per-model scoring
2. Semantic claims similarity & contradiction classification
3. Structured DecisionReport generation
4. Quality verifier check
5. Optional self-healing revision loop
"""

from __future__ import annotations

import json
import logging
import re
from typing import Dict, Any, List, Optional

from agents import call_llm_for_role
from config import settings
from reporting.synthesis_schema import DecisionReport, QualityMeta, Verdict
from reporting.claim_similarity import get_claim_embeddings, compute_semantic_similarity
from reporting.claim_contradiction import classify_contradiction
from reporting.model_evaluator import evaluate_models_blind
from reporting.claim_quality import filter_claims
from worker.arena_tasks import _extract_claims_from_response

logger = logging.getLogger(__name__)


async def run_semantic_claims_analysis(
    prompt: str,
    responses: List[Dict[str, Any]],
    debate_id: str,
    usage: Any | None = None,
) -> Dict[str, Any]:
    """Extract claims semantically, group them into consensus/contested, and compute divergence breakdown."""
    if not responses:
        return {
            "consensus_claims": [],
            "contested_claims": [],
            "divergence_score": 0.0,
            "semantic_analysis_mode": "fallback_string",
            "embedding_success": False,
            "contradiction_pairs_classified": 0,
        }

    # Extract claims in parallel
    claims_tasks = []
    for resp in responses:
        content = resp.get("text", resp.get("content", ""))
        name = resp.get("persona", resp.get("model", "Model"))
        claims_tasks.append(_extract_claims_from_response(prompt, content, name, debate_id))
    
    import asyncio
    extracted_lists = await asyncio.gather(*claims_tasks)
    
    all_claims = []
    for resp, claims in zip(responses, extracted_lists, strict=False):
        model_name = resp.get("persona", resp.get("model", "Model"))
        # Phase 2: Apply claim quality filter before analysis
        cleaned_claims = filter_claims(claims)
        for c in cleaned_claims:
            all_claims.append({"claim": c, "model": model_name})

    # Fetch embeddings in batch for performance
    claim_texts = [item["claim"] for item in all_claims]
    embedding_success = True
    try:
        embeddings = await get_claim_embeddings(claim_texts, debate_id)
    except Exception as e:
        logger.warning(f"Failed to fetch claim embeddings: {e}. Falling back to string similarity.")
        embeddings = []
        embedding_success = False
    
    # Determine semantic analysis mode
    if settings.USE_MOCK:
        semantic_analysis_mode = "mock"
        embedding_success = False
    elif not embeddings or all(not e for e in embeddings):
        semantic_analysis_mode = "fallback_string"
        embedding_success = False
    else:
        semantic_analysis_mode = "embedding"

    processed = set()
    consensus_list = []
    contested_list = []

    # Consensus grouping
    for i, item1 in enumerate(all_claims):
        if i in processed:
            continue
        matching_indices = []
        matching_models = [item1["model"]]
        
        embed1 = embeddings[i] if i < len(embeddings) else None
        
        for j, item2 in enumerate(all_claims):
            if i != j and j not in processed:
                embed2 = embeddings[j] if j < len(embeddings) else None
                sim = await compute_semantic_similarity(
                    item1["claim"],
                    item2["claim"],
                    embed1,
                    embed2,
                )
                
                if sim >= 0.78:  # same_claim threshold
                    matching_indices.append(j)
                    matching_models.append(item2["model"])

        if matching_indices:
            processed.add(i)
            for idx in matching_indices:
                processed.add(idx)
            consensus_list.append({
                "claim": item1["claim"],
                "models": list(set(matching_models))
            })
        else:
            processed.add(i)
            # Phase 3: These are unique/single-model insights, not contested
            contested_list.append({
                "claim": item1["claim"],
                "model": item1["model"]
            })

    # Collect contradiction candidate pairs (similarity in [0.60, 0.78))
    candidate_pairs = []
    for i, item1 in enumerate(all_claims):
        embed1 = embeddings[i] if i < len(embeddings) else None
        for j, item2 in enumerate(all_claims):
            if i >= j:
                continue
            if item1["model"] == item2["model"]:
                # A model cannot contradict itself
                continue
            embed2 = embeddings[j] if j < len(embeddings) else None
            sim = await compute_semantic_similarity(
                item1["claim"],
                item2["claim"],
                embed1,
                embed2,
            )
            if 0.60 <= sim < 0.78:
                candidate_pairs.append({
                    "similarity": sim,
                    "item_a": item1,
                    "item_b": item2
                })

    # Sort candidates by similarity descending & cap to avoid O(n^2) LLM calls
    candidate_pairs.sort(key=lambda x: x["similarity"], reverse=True)
    limited_pairs = candidate_pairs[:25]  # Cap at 25 pairs maximum

    # Classify contradictions for limited pairs in parallel
    contradiction_tasks = []
    for pair in limited_pairs:
        claim_a = pair["item_a"]["claim"]
        claim_b = pair["item_b"]["claim"]
        contradiction_tasks.append(classify_contradiction(claim_a, claim_b, debate_id, usage))

    contra_results = await asyncio.gather(*contradiction_tasks)

    contradictions_count = 0
    contradiction_details = []
    for pair, res in zip(limited_pairs, contra_results, strict=False):
        if res.get("is_contradictory"):
            contradictions_count += 1
            contradiction_details.append({
                "claim_a": pair["item_a"]["claim"],
                "model_a": pair["item_a"]["model"],
                "claim_b": pair["item_b"]["claim"],
                "model_b": pair["item_b"]["model"],
                "reason": res.get("explanation", ""),
            })

    # Redesigned Divergence Score formula factoring in agreement, contradictions, and topic variance
    total_claims = len(all_claims)
    total_distinct = len(consensus_list) + len(contested_list)
    
    if total_claims > 0 and total_distinct > 0:
        contradiction_rate = contradictions_count / total_claims
        agreement_rate = len(consensus_list) / total_distinct
        topic_coverage_variance = len(contested_list) / total_claims
        
        divergence_score = (
            0.50 * contradiction_rate +
            0.30 * (1.0 - agreement_rate) +
            0.20 * topic_coverage_variance
        )
        divergence_score = min(1.0, max(0.0, divergence_score))
    else:
        divergence_score = 0.0

    return {
        "consensus_claims": consensus_list,
        "unique_insights": contested_list,
        "contested_claims": contested_list,  # legacy alias
        "active_contradictions": contradiction_details,
        "contradictions_count": contradictions_count,
        "contradiction_details": contradiction_details,
        "divergence_score": float(round(divergence_score, 2)),
        "semantic_analysis_mode": semantic_analysis_mode,
        "embedding_success": embedding_success,
        "contradiction_pairs_classified": len(limited_pairs),
    }


async def generate_decision_report(
    prompt: str,
    responses: List[Dict[str, Any]],
    debate_id: str,
    locale: Optional[str] = None,
    model_override: Optional[str] = None,
    usage: Any | None = None,
) -> DecisionReport:
    """Generate a structured, verified decision report by aggregating candidate model responses."""
    # Step 1: Blind scoring
    logger.info("Running blind scoring for debate %s", debate_id)
    model_evals = await evaluate_models_blind(prompt, responses, debate_id, usage)
    
    # Step 2: Semantic claim analysis
    logger.info("Running semantic claim analysis for debate %s", debate_id)
    semantic_analysis = await run_semantic_claims_analysis(prompt, responses, debate_id, usage)
    
    # Format candidate answers block
    candidate_block = "\n\n---\n\n".join(
        f"### {r.get('persona', r.get('model', 'Model'))}\n{r.get('text', r.get('content', ''))}"
        for r in responses
    )
    
    # Format scores block
    scores_block = "\n".join(
        f"- {s['model']}: Logic={s['logic_score']}, Completeness={s['completeness_score']}, Conciseness={s['conciseness_score']}, Overall={s['overall_score']}. Rationale: {s['rationale']}"
        for s in model_evals
    )
    
    # Format consensus/contested block
    consensus_block = "\n".join(f"- \"{c['claim']}\" (Agreed by: {', '.join(c['models'])})" for c in semantic_analysis["consensus_claims"])
    contested_block = "\n".join(f"- \"{c['claim']}\" (Raised by: {c['model']})" for c in semantic_analysis["contested_claims"])
    contradiction_block = "\n".join(
        f"- \"{c['claim_a']}\" ({c['model_a']}) conflicts with \"{c['claim_b']}\" ({c['model_b']}). Reason: {c['reason']}"
        for c in semantic_analysis["contradiction_details"]
    )

    system_prompt = (
        "You are the Lead Decision Strategist. Synthesize the candidate model responses "
        "and logical analysis into a premium, professional Decision Report JSON object.\n"
        "Analyze consensus points, resolve disagreements, highlight critical risks/assumptions, "
        "and compile actionable next steps.\n\n"
        "CRITICAL SPECIFICITY RULES:\n"
        "- Do NOT generate a generic checklist. Tailor the report to the user's exact question, product, company stage, and available context.\n"
        "- If specific project context (ARR, users, ICP, retention, CAC/LTV, team, runway, etc.) is available in the prompt, USE IT.\n"
        "- If context is missing, label recommendations as generic and include a 'context_needed' list of items needed to make the report specific.\n"
        "- Avoid clichéd SaaS fundraising advice unless directly relevant.\n"
        "- Each risk must include a specific diagnostic or action, not just a category name.\n"
        "- Avoid generic-only risks like 'Market demand' or 'Team strength' unless paired with concrete diagnostics.\n\n"
        "You MUST output strictly in JSON format. Do not add markdown code fences, headers, or conversational text. "
        "Your response must be parseable by json.loads().\n"
        "Schema format:\n"
        "{\n"
        "  \"title\": \"Clear descriptive title\",\n"
        "  \"executive_summary\": \"High-level strategic summary...\",\n"
        "  \"verdict\": {\n"
        "    \"recommendation\": \"Actionable recommendation...\",\n"
        "    \"confidence\": <float 0.0 to 1.0>,\n"
        "    \"decision_type\": \"proceed | revise | defer | reject | mixed\",\n"
        "    \"rationale\": \"Reasoning for this verdict...\"\n"
        "  },\n"
        "  \"key_findings\": [\n"
        "    {\"title\": \"Finding title\", \"summary\": \"Details...\", \"importance\": \"critical | high | medium | low\"}\n"
        "  ],\n"
        "  \"options_considered\": [\n"
        "    {\"option\": \"Option name\", \"pros\": [\"pro1\"], \"cons\": [\"con1\"], \"score\": <optional float>}\n"
        "  ],\n"
        "  \"model_positions\": [\n"
        "    {\"model\": \"Model Name\", \"stance\": \"supportive | concerned | neutral | opposing\", "
        "\"distinct_contribution\": \"The unique, specific contribution this model provided\", "
        "\"blind_spot\": \"Specific limitation in this model's analysis. If none, write: No major limitation identified.\"}\n"
        "  ],\n"
        "  \"risks_and_assumptions\": [\n"
        "    {\"item\": \"Specific risk/assumption with concrete diagnostics\", \"type\": \"risk | assumption\", \"severity\": \"critical | high | medium | low\", \"mitigation\": \"Mitigation...\"}\n"
        "  ],\n"
        "  \"recommendation_table\": [\n"
        "    {\"criterion\": \"Criterion\", \"winner_or_answer\": \"Winner/Option\", \"evidence\": \"Evidence...\", \"confidence\": <float 0.0 to 1.0>}\n"
        "  ],\n"
        "  \"next_actions\": [\n"
        "    {\"action\": \"Action desc\", \"owner\": \"Owner\", \"priority\": \"now | next | later\"}\n"
        "  ],\n"
        "  \"caveats\": [\"Caveat 1\", \"Caveat 2\"],\n"
        "  \"dissenting_views\": [\"Dissenting view 1\"],\n"
        "  \"unique_insights\": [\"Unique insight 1\"],\n"
        "  \"context_needed\": [\"List of specific missing context items needed to make this report more specific, e.g. ARR, number of users, ICP, retention rate\"]\n"
        "}"
    )

    if locale and locale != "en":
        system_prompt += f"\nIMPORTANT: Respond and write all text values in the '{locale}' language.\n"

    user_content = (
        f"**Original User Prompt:**\n{prompt}\n\n"
        f"**Individual Model Answers:**\n\n{candidate_block}\n\n"
        f"**Evaluator Scores:**\n{scores_block}\n\n"
        f"**Consensus Claims:**\n{consensus_block or 'None'}\n\n"
        f"**Unique / Single-Model Insights:**\n{contested_block or 'None'}\n\n"
        f"**Active Contradictions / Disagreements:**\n{contradiction_block or 'None'}\n\n"
        f"Divergence Score: {semantic_analysis['divergence_score']}\n\n"
        "Synthesize the final structured JSON decision report. "
        "Remember: each model_positions entry must use 'distinct_contribution' and 'blind_spot' fields (not 'strongest_point'/'concern'). "
        "Each blind_spot must be specific to this answer, not generic like 'may not apply to all SaaS startups.' "
        "If no meaningful blind spot exists, write 'No major limitation identified.'"
    )

    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_content},
    ]

    # Configure provider-native structured output
    response_format = None
    tools = None
    tool_choice = None
    target_model_lower = (model_override or "").lower()
    provider = "unknown"

    if model_override:
        from model_gateway.model_map import MODEL_MAP
        if model_override in MODEL_MAP:
            provider = MODEL_MAP[model_override]["provider"]
        elif "gpt" in target_model_lower:
            provider = "openai"
        elif "claude" in target_model_lower:
            provider = "anthropic"
        elif "gemini" in target_model_lower:
            provider = "gemini"
    else:
        from parliament.model_registry import get_default_model
        try:
            model_cfg = get_default_model()
            provider = getattr(model_cfg.provider, "value", str(model_cfg.provider)) if hasattr(model_cfg, "provider") else "unknown"
        except Exception:
            pass

    schema = DecisionReport.model_json_schema()
    if not settings.USE_MOCK:
        if provider == "openai":
            response_format = {
                "type": "json_schema",
                "json_schema": {
                    "name": "DecisionReport",
                    "strict": True,
                    "schema": schema
                }
            }
        elif provider == "anthropic":
            tools = [{
                "type": "function",
                "function": {
                    "name": "submit_decision_report",
                    "description": "Submit the completed structured decision report",
                    "parameters": schema
                }
            }]
            tool_choice = {
                "type": "function",
                "function": {"name": "submit_decision_report"}
            }

    draft_report = None
    raw_content = ""
    report_validation_repaired = False

    # Call LLM for initial draft
    try:
        raw_content, call_usage = await call_llm_for_role(
            messages,
            role="Arena:Synthesizer",
            temperature=0.3,
            max_tokens=1500,
            model_id=model_override,
            debate_id=debate_id,
            response_format=response_format,
            tools=tools,
            tool_choice=tool_choice,
        )
        if usage is not None and hasattr(usage, "add_call"):
            usage.add_call(call_usage)
        
        match = re.search(r"\{.*\}", raw_content, flags=re.S)
        json_str = match.group(0) if match else raw_content
        
        draft_report = DecisionReport.model_validate_json(json_str)
    except Exception as exc:
        logger.warning("Failed initial structured synthesis JSON validation: %s. Initiating repair prompt.", exc)
        report_validation_repaired = True
        
        # Self-healing repair loop step 1: Repair Prompt
        repair_messages = [
            {"role": "system", "content": "You are a JSON repair tool. Correct the provided text to output strictly valid JSON matching the schema of a Decision Report. Do not include markdown fences or explanation."},
            {"role": "user", "content": f"Schema: {DecisionReport.model_json_schema()}\n\nError: {exc}\n\nInvalid Content:\n{raw_content or json_str}\n\nReturn repaired JSON:"}
        ]
        try:
            repaired_raw, call_usage = await call_llm_for_role(
                repair_messages,
                role="Arena:JSONRepair",
                temperature=0.1,
                max_tokens=1500,
                debate_id=debate_id,
            )
            if usage is not None and hasattr(usage, "add_call"):
                usage.add_call(call_usage)
            match = re.search(r"\{.*\}", repaired_raw, flags=re.S)
            repaired_json = match.group(0) if match else repaired_raw
            draft_report = DecisionReport.model_validate_json(repaired_json)
            raw_content = repaired_json
        except Exception as repair_exc:
            logger.error("JSON repair failed: %s. Falling back to heuristic parsing.", repair_exc)
            # Fallback to client/heuristic parser
            from reporting.report_builder import build_report_from_synthesis
            draft_report = build_report_from_synthesis(prompt, raw_content or candidate_block)

    # Step 3: Verify / Critic quality check pass
    from reporting.synthesis_critic import verify_synthesis_report
    logger.info("Running critic check for debate %s", debate_id)
    critic_res = await verify_synthesis_report(prompt, responses, raw_content, debate_id, usage)
    
    # Step 4: Revise loop (if enabled, limit to 1 loop)
    enable_revise = getattr(settings, "ENABLE_SYNTHESIS_REVISE", True)
    critic_revision_triggered = False
    
    if enable_revise and critic_res.get("needs_revision") and not settings.USE_MOCK:
        logger.info("Critic flagged revision loop for debate %s. Feedback: %s", debate_id, critic_res.get("critic_feedback"))
        critic_revision_triggered = True
        
        revise_messages = [
            {"role": "system", "content": system_prompt + "\n\nCRITICAL: Revise the draft JSON according to the verifier feedback. Fix any hallucinations, add missing critical evidence/dissenting views, and correct inaccuracies. Output strictly valid JSON."},
            {"role": "user", "content": f"Draft Report:\n{raw_content}\n\nVerifier Feedback:\n{critic_res.get('critic_feedback')}\n\nReturn revised JSON decision report:"}
        ]
        
        try:
            revised_raw, call_usage = await call_llm_for_role(
                revise_messages,
                role="Arena:Synthesizer",
                temperature=0.2,
                max_tokens=1500,
                model_id=model_override,
                debate_id=debate_id,
            )
            if usage is not None and hasattr(usage, "add_call"):
                usage.add_call(call_usage)
            match = re.search(r"\{.*\}", revised_raw, flags=re.S)
            revised_json = match.group(0) if match else revised_raw
            draft_report = DecisionReport.model_validate_json(revised_json)
            raw_content = revised_json
            
            # Run critic on the revised report to update the score
            critic_res = await verify_synthesis_report(prompt, responses, raw_content, debate_id, usage)
        except Exception as revise_exc:
            logger.warning("Revision pass failed: %s. Keeping original draft.", revise_exc)

    # Determine verification status
    verification_error = bool(critic_res.get("verification_error", False))
    verification_source = critic_res.get("verification_source", "critic")
    genericity_risk = critic_res.get("genericity_risk", "medium")

    if verification_error:
        verification_status = "unverified"
    elif critic_res.get("has_hallucinations"):
        verification_status = "failed"
    elif genericity_risk == "high":
        verification_status = "unverified"
    elif critic_res.get("needs_revision") or (critic_res.get("faithfulness_score") is not None and critic_res.get("faithfulness_score", 1.0) < 0.70) or (critic_res.get("completeness_score") is not None and critic_res.get("completeness_score", 1.0) < 0.70):
        verification_status = "unverified"
    else:
        verification_status = "verified"

    # Attach metadata to report object
    draft_report.quality_meta = QualityMeta(
        completeness_score=critic_res.get("completeness_score"),
        faithfulness_score=critic_res.get("faithfulness_score"),
        has_hallucinations=critic_res.get("has_hallucinations", False),
        needs_revision=critic_res.get("needs_revision", False),
        critic_feedback=critic_res.get("critic_feedback"),
        verification_status=verification_status,
        verification_error=verification_error,
        verification_source=verification_source,
        specificity_score=critic_res.get("specificity_score"),
        genericity_risk=genericity_risk,
    )
    draft_report.model_contributions = model_evals
    draft_report.divergence_breakdown = {
        "divergence_score": semantic_analysis["divergence_score"],
        "consensus_claims": semantic_analysis["consensus_claims"],
        "unique_insights": semantic_analysis.get("unique_insights", semantic_analysis.get("contested_claims", [])),
        "contested_claims": semantic_analysis.get("contested_claims", []),  # legacy
        "active_contradictions": semantic_analysis.get("active_contradictions", semantic_analysis.get("contradiction_details", [])),
        "contradictions_count": semantic_analysis["contradictions_count"],
        "contradiction_details": semantic_analysis["contradiction_details"],
        "semantic_analysis_mode": semantic_analysis.get("semantic_analysis_mode", "embedding"),
    }
    
    # Populate Telemetry
    draft_report.telemetry = {
        "embedding_success": semantic_analysis.get("embedding_success", False),
        "contradiction_pairs_classified": semantic_analysis.get("contradiction_pairs_classified", 0),
        "critic_revision_triggered": critic_revision_triggered,
        "report_validation_repaired": report_validation_repaired,
        "report_quality_scores": {
            "completeness": critic_res.get("completeness_score", 1.0),
            "faithfulness": critic_res.get("faithfulness_score", 1.0),
        }
    }
    
    return draft_report
