from __future__ import annotations

from typing import List, Optional

from pydantic import BaseModel, Field, field_validator, ConfigDict

class BudgetConfig(BaseModel):
    max_tokens: Optional[int] = None
    max_cost_usd: Optional[float] = None
    early_stop_delta: Optional[float] = 1.0


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


class DebateCreate(BaseModel):
    model_config = ConfigDict(protected_namespaces=())
    prompt: str
    config: Optional[DebateConfig] = None
    model_id: Optional[str] = None

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


class ModelPublic(BaseModel):
    id: str
    display_name: str
    provider: str
    tags: List[str] = Field(default_factory=list)
    max_context: Optional[int] = None
    recommended: bool = False


class UserProfile(BaseModel):
    id: str
    email: str
    display_name: Optional[str] = None
    avatar_url: Optional[str] = None
    bio: Optional[str] = None
    timezone: Optional[str] = None
    is_admin: bool = False
    created_at: str


class UserProfileUpdate(BaseModel):
    display_name: Optional[str] = Field(default=None, max_length=80)
    avatar_url: Optional[str] = Field(default=None)
    bio: Optional[str] = Field(default=None, max_length=1000)
    timezone: Optional[str] = Field(default=None)
