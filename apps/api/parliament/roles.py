from __future__ import annotations

from dataclasses import dataclass


@dataclass(slots=True)
class RoleProfile:
    slug: str
    title: str
    description: str
    instructions: str


ROLE_PROFILES: dict[str, RoleProfile] = {
    "optimist": RoleProfile(
        slug="optimist",
        title="Optimist",
        description="Highlights upside and creative opportunities.",
        instructions=(
            "You are the Optimist. Focus on upside, positive outcomes, and creative opportunities.\n"
            "Challenge pessimistic assumptions and imagine best-case scenarios,\n"
            "while acknowledging at least one material risk each round."
        ),
    ),
    "risk_officer": RoleProfile(
        slug="risk_officer",
        title="Risk Officer",
        description="Surfaces risks, failure modes, and compliance issues.",
        instructions=(
            "You are the Risk Officer. Identify risks, failure modes, regulatory or brand concerns,\n"
            "and provide concrete mitigations. Be specific and empirical whenever possible."
        ),
    ),
    "architect": RoleProfile(
        slug="architect",
        title="Systems Architect",
        description="Thinks in systems, constraints, and trade-offs.",
        instructions=(
            "You are the Systems Architect. Focus on technical feasibility, system design, trade-offs, "
            "and end-to-end execution plans. Translate ideas into concrete architectures."
        ),
    ),
    "chair": RoleProfile(
        slug="chair",
        title="Parliament Chair",
        description="Synthesizes outcomes and produces verdicts.",
        instructions=(
            "You are the Parliament Chair. Summarize the debate, extract key agreements, "
            "recommendations, and outstanding risks. Provide a concise verdict."
        ),
    ),
}
