import asyncio
import os
from pathlib import Path
from unittest.mock import patch

import pytest
import sys

os.environ.setdefault("JWT_SECRET", "test-secret")
os.environ.setdefault("USE_MOCK", "1")

sys.path.append(str(Path(__file__).resolve().parents[1]))

import pytest

pytestmark = pytest.mark.anyio("asyncio")


@pytest.fixture
def anyio_backend():
    return "asyncio"

from agents import UsageAccumulator, UsageCall  # noqa: E402
from models import Debate  # noqa: E402
from orchestrator import (  # noqa: E402
    _check_budget,
    _compute_rankings,
    _select_candidates,
    run_debate,
)
from schemas import AgentConfig, BudgetConfig, DebateConfig, JudgeConfig  # noqa: E402


def _usage(tokens: int) -> UsageAccumulator:
    usage = UsageAccumulator()
    usage.add_call(
        UsageCall(
            prompt_tokens=tokens / 2,
            completion_tokens=tokens / 2,
            total_tokens=float(tokens),
            cost_usd=tokens * 0.000001,
            provider="mock",
            model="router-smart",
        )
    )
    return usage


def test_compute_rankings_prefers_higher_scores():
    scores = [
        {"persona": "A", "score": 9.0},
        {"persona": "B", "score": 7.5},
        {"persona": "C", "score": 8.2},
    ]
    ranking, details = _compute_rankings(scores)
    assert ranking[0] == "A"
    assert details["borda"]["A"] > details["borda"]["B"]


def test_check_budget_detects_token_and_cost_limits():
    usage = _usage(500)
    budget = BudgetConfig(max_tokens=400, max_cost_usd=0.0003)
    assert _check_budget(budget, usage) == "token_budget_exceeded"
    usage = _usage(200)
    usage.cost_usd = 0.01
    budget = BudgetConfig(max_cost_usd=0.0001)
    assert _check_budget(budget, usage) == "cost_budget_exceeded"


def test_select_candidates_respects_override():
    preferred = ["Builder"]
    candidates = [{"persona": "Analyst"}, {"persona": "Builder"}, {"persona": "Critic"}]
    selected = _select_candidates(preferred, candidates)
    assert len(selected) == 1 and selected[0]["persona"] == "Builder"


@pytest.mark.anyio("asyncio")
async def test_fast_debate_path_emits_final_event(monkeypatch):
    monkeypatch.setenv("FAST_DEBATE", "1")
    debate = Debate(
        id="fast-debate",
        prompt="Test prompt for FAST mode",
        status="queued",
        config=DebateConfig(
            agents=[AgentConfig(name="Analyst", persona="Systems thinker")],
            judges=[JudgeConfig(name="JudgeOne", rubrics=["accuracy"])],
        ).model_dump(),
    )

    async def collect():
        q: asyncio.Queue = asyncio.Queue()
        events = []

        class DummyScope:
            def __enter__(self):
                return None

            def __exit__(self, exc_type, exc, tb):
                return False

        def fake_scope():
            return DummyScope()

        with patch("orchestrator.session_scope", fake_scope), patch("orchestrator._complete_debate_record"):
            await run_debate(debate.id, debate.prompt, q, debate.config)
            while not q.empty():
                events.append(await q.get())
        return events

    events = await collect()
    assert any(evt.get("type") == "final" for evt in events)
    monkeypatch.setenv("FAST_DEBATE", "0")
