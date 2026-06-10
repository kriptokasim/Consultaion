"""Structured decision report synthesis schemas.

These Pydantic models define the shape of a professional, structured decision report
returned by Arena and Debate synthesis.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class Verdict(BaseModel):
    recommendation: str = Field(default="", description="The primary recommendation text")
    confidence: float = Field(default=0.5, ge=0.0, le=1.0, description="Confidence score between 0.0 and 1.0")
    decision_type: str = Field(default="mixed", description="One of: proceed | revise | defer | reject | mixed")
    rationale: str = Field(default="", description="The detailed reasoning behind the verdict")


class KeyFinding(BaseModel):
    title: str = Field(..., description="Short title of the finding")
    summary: str = Field(..., description="Summary of the finding details")
    importance: str = Field(default="medium", description="One of: critical | high | medium | low")


class OptionConsidered(BaseModel):
    option: str = Field(..., description="Description of the option considered")
    pros: List[str] = Field(default_factory=list, description="List of pros/advantages")
    cons: List[str] = Field(default_factory=list, description="List of cons/disadvantages")
    score: Optional[float] = Field(None, description="Optional numerical score for this option")


class ModelPosition(BaseModel):
    model: str = Field(..., description="The name/display name of the model")
    stance: str = Field(..., description="One of: supportive | concerned | neutral | opposing")
    strongest_point: str = Field(..., description="The strongest argument or point made by this model")
    concern: str = Field(..., description="The main concern, caveat, or risk raised by this model")


class RiskAssumption(BaseModel):
    item: str = Field(..., description="Description of the risk or assumption")
    type: str = Field(default="risk", description="One of: risk | assumption | unknown")
    severity: str = Field(default="medium", description="One of: critical | high | medium | low")
    mitigation: Optional[str] = Field(None, description="Optional mitigation strategy")


class RecommendationRow(BaseModel):
    criterion: str = Field(..., description="The evaluation criterion")
    winner_or_answer: str = Field(..., description="The winning option or answer for this criterion")
    evidence: str = Field(..., description="Evidence supporting this choice")
    confidence: float = Field(default=0.5, ge=0.0, le=1.0)


class NextAction(BaseModel):
    action: str = Field(..., description="Description of the action item")
    owner: Optional[str] = Field(None, description="Who is responsible for this action")
    priority: str = Field(default="next", description="One of: now | next | later")


class QualityMeta(BaseModel):
    completeness_score: float = Field(default=1.0, ge=0.0, le=1.0, description="Completeness rating")
    faithfulness_score: float = Field(default=1.0, ge=0.0, le=1.0, description="Faithfulness to source answers")
    has_hallucinations: bool = Field(default=False, description="Whether the report contains hallucinated content")
    needs_revision: bool = Field(default=False, description="Whether the critic flags this for revision")
    critic_feedback: Optional[str] = Field(None, description="Detailed feedback from the verifier pass")


class DecisionReport(BaseModel):
    title: str = Field(default="Decision Report", description="Title of the decision report")
    executive_summary: str = Field(default="", description="High-level executive summary")
    verdict: Verdict = Field(default_factory=Verdict, description="The synthesis verdict")
    key_findings: List[KeyFinding] = Field(default_factory=list, description="Key consensus or analytical findings")
    options_considered: List[OptionConsidered] = Field(default_factory=list, description="Options analyzed in the responses")
    model_positions: List[ModelPosition] = Field(default_factory=list, description="Consolidated stances of individual models")
    risks_and_assumptions: List[RiskAssumption] = Field(default_factory=list, description="Identified risks and key assumptions")
    recommendation_table: List[RecommendationRow] = Field(default_factory=list, description="Criterion-by-criterion evidence table")
    next_actions: List[NextAction] = Field(default_factory=list, description="Concrete next action items")
    caveats: List[str] = Field(default_factory=list, description="Any critical limitations or caveats")
    dissenting_views: List[str] = Field(default_factory=list, description="Points of strong model disagreement / dissenting arguments")
    unique_insights: List[str] = Field(default_factory=list, description="Distinct viewpoints or novel arguments found in individual models")
    model_contributions: List[Dict[str, Any]] = Field(default_factory=list, description="Rubric scoring analysis per model")
    divergence_breakdown: Dict[str, Any] = Field(default_factory=dict, description="Categorization of consensus vs contested claims")
    quality_meta: Optional[QualityMeta] = Field(None, description="Quality verification gate details")
