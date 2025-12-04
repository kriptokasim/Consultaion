from __future__ import annotations

from typing import List, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator


class BudgetConfig(BaseModel):
    max_tokens: Optional[int] = None
    max_cost_usd: Optional[float] = None
    early_stop_delta: Optional[float] = 1.0


class DebateSummary(BaseModel):
    debate_id: str
    title: str
    models_used: List[str]
    winner: str | None = None
    summary_text: str
    url: str | None = None  # deep link to debate in Consultaion UI


class AgentConfig(BaseModel):
    name: str
    persona: str
    model: Optional[str] = None
    tools: Optional[List[str]] = None


class JudgeConfig(BaseModel):
    name: str
    model: Optional[str] = None
    rubrics: List[str] = Field(
        default_factory=lambda: ["accuracy", "completeness", "citations", "actionability", "risk"]
    )


class DebateConfig(BaseModel):
    agents: List[AgentConfig] = Field(default_factory=list)
    judges: List[JudgeConfig] = Field(default_factory=list)
    budget: Optional[BudgetConfig] = None


class PanelSeat(BaseModel):
    seat_id: str
    display_name: str
    provider_key: str = Field(pattern=r"^[a-z0-9_\-]+$")
    model: str
    role_profile: str
    temperature: Optional[float] = Field(default=0.5, ge=0.0, le=2.0)


class PanelConfig(BaseModel):
    engine_version: str = "parliament-v1"
    seats: List[PanelSeat]
    max_seat_fail_ratio: Optional[float] = Field(
        None,
        description="Override for DEBATE_MAX_SEAT_FAIL_RATIO; fraction of seats allowed to fail before aborting.",
    )
    min_required_seats: Optional[int] = Field(
        None,
        description="Override for DEBATE_MIN_REQUIRED_SEATS; minimum successful seats per round.",
    )
    fail_fast: Optional[bool] = Field(
        None,
        description="Override for DEBATE_FAIL_FAST; when True, abort debate instead of limping along.",
    )


class DebateCreate(BaseModel):
    """Request schema for creating a new debate.
    
    Supports both explicit model selection and intelligent routing based on policies.
    """
    model_config = ConfigDict(protected_namespaces=())
    
    prompt: str = Field(..., description="The question or topic for the debate. Must be 10-5000 characters.")
    config: Optional[DebateConfig] = Field(None, description="Optional debate configuration with agents and judges.")
    model_id: Optional[str] = Field(
        None, 
        description="Explicit model ID to use. If provided, bypasses routing engine. Examples: 'gpt4o-mini', 'claude-sonnet'"
    )
    routing_policy: Optional[str] = Field(
        None,
        description="Routing policy for model selection. Options: 'router-smart' (balanced), 'router-deep' (quality-focused). Defaults to 'router-smart'."
    )
    panel_config: Optional[PanelConfig] = Field(None, description="Optional Parliament-style panel configuration.")

    @field_validator("prompt")
    @classmethod
    def validate_prompt(cls, value: str) -> str:
        text = (value or "").strip()
        if len(text) < 10:
            raise ValueError("Prompt must be at least 10 characters")
        if len(text) > 5000:
            raise ValueError("Prompt must be less than 5000 characters")
        return text


def default_agents() -> List[AgentConfig]:
    return [
        AgentConfig(
            name="Analyst",
            persona="Systems thinker focused on first-principles reasoning and trade-off analysis.",
            tools=["retrieval"],
        ),
        AgentConfig(
            name="Critic",
            persona="Adversarial reviewer who hunts for logical gaps, hallucinations, and policy risks.",
            tools=["web"],
        ),
        AgentConfig(
            name="Builder",
            persona="Execution-focused planner translating ideas into actionable sequences.",
            tools=["code"],
        ),
    ]


def default_judges() -> List[JudgeConfig]:
    return [
        JudgeConfig(name="JudgeAlpha", model="openai/gpt-4o-mini"),
        JudgeConfig(name="JudgeBeta", model="anthropic/claude-3-5-sonnet"),
    ]


def default_budget() -> BudgetConfig:
    return BudgetConfig(max_tokens=60000, max_cost_usd=1.5, early_stop_delta=1.0)


def default_debate_config() -> DebateConfig:
    return DebateConfig(
        agents=[agent.model_copy() for agent in default_agents()],
        judges=[judge.model_copy() for judge in default_judges()],
        budget=default_budget().model_copy(),
    )


def default_panel_config() -> PanelConfig:
    return PanelConfig(
        engine_version="parliament-v1",
        seats=[
            PanelSeat(
                seat_id="optimist",
                display_name="Optimist",
                provider_key="openai",
                model="gpt-4o-mini",
                role_profile="optimist",
                temperature=0.7,
            ),
            PanelSeat(
                seat_id="risk_officer",
                display_name="Risk Officer",
                provider_key="anthropic",
                model="claude-3-5-sonnet",
                role_profile="risk_officer",
                temperature=0.4,
            ),
            PanelSeat(
                seat_id="architect",
                display_name="Systems Architect",
                provider_key="openai",
                model="gpt-4.1-mini",
                role_profile="architect",
                temperature=0.5,
            ),
        ],
    )


class ModelPublic(BaseModel):
    id: str
    display_name: str
    provider: str
    capabilities: List[str] = Field(default_factory=list)
    cost_tier: str
    latency_class: str
    quality_tier: str
    safety_profile: str
    recommended: bool = False
    enabled: bool = True


class AuthRequest(BaseModel):
    email: str
    password: str


class UserProfile(BaseModel):
    id: str
    email: str
    display_name: Optional[str] = None
    avatar_url: Optional[str] = None
    bio: Optional[str] = None
    timezone: Optional[str] = None
    is_admin: bool = False
    created_at: str
    email_summaries_enabled: bool = False


class UserProfileUpdate(BaseModel):
    display_name: Optional[str] = Field(default=None, max_length=80)
    avatar_url: Optional[str] = Field(default=None)
    bio: Optional[str] = Field(default=None, max_length=1000)
    timezone: Optional[str] = Field(default=None)
    email_summaries_enabled: Optional[bool] = Field(default=None)
