"""Structured decision report schemas.

These Pydantic models define the shape of a professional decision report
returned by Arena and Debate synthesis.
"""

from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, Field


class Verdict(BaseModel):
    recommendation: str = Field(default="", description="One of: proceed, revise, defer, reject, mixed")
    confidence: float = Field(default=0.5, ge=0.0, le=1.0)
    decision_type: str = Field(default="mixed", description="proceed | revise | defer | reject | mixed")
    rationale: str = Field(default="")


class KeyFinding(BaseModel):
    title: str
    summary: str
    importance: str = Field(default="medium", description="critical | high | medium | low")


class OptionConsidered(BaseModel):
    option: str
    pros: list[str] = Field(default_factory=list)
    cons: list[str] = Field(default_factory=list)
    score: Optional[float] = None


class ModelPosition(BaseModel):
    model: str
    stance: str
    strongest_point: str
    concern: str


class RiskAssumption(BaseModel):
    item: str
    type: str = Field(default="risk", description="risk | assumption | unknown")
    severity: str = Field(default="medium", description="critical | high | medium | low")
    mitigation: Optional[str] = None


class RecommendationRow(BaseModel):
    criterion: str
    winner_or_answer: str
    evidence: str
    confidence: float = Field(default=0.5, ge=0.0, le=1.0)


class NextAction(BaseModel):
    action: str
    owner: Optional[str] = None
    priority: str = Field(default="next", description="now | next | later")


class DecisionReport(BaseModel):
    title: str = Field(default="Decision Report")
    executive_summary: str = Field(default="")
    verdict: Verdict = Field(default_factory=Verdict)
    key_findings: list[KeyFinding] = Field(default_factory=list)
    options_considered: list[OptionConsidered] = Field(default_factory=list)
    model_positions: list[ModelPosition] = Field(default_factory=list)
    risks_and_assumptions: list[RiskAssumption] = Field(default_factory=list)
    recommendation_table: list[RecommendationRow] = Field(default_factory=list)
    next_actions: list[NextAction] = Field(default_factory=list)
    caveats: list[str] = Field(default_factory=list)
