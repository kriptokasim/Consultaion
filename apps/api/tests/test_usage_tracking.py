from agents import UsageAccumulator, UsageCall
from orchestrator import _check_budget
from schemas import BudgetConfig


def test_usage_tracker_isolated_per_run():
    tracker_one = UsageAccumulator()
    tracker_two = UsageAccumulator()

    tracker_one.add_call(
        UsageCall(prompt_tokens=60, completion_tokens=40, total_tokens=100, cost_usd=0.02, provider="mock", model="mock")
    )
    tracker_two.add_call(
        UsageCall(prompt_tokens=5, completion_tokens=5, total_tokens=10, cost_usd=0.001, provider="mock", model="mock")
    )

    assert tracker_one.total_tokens == 100
    assert tracker_two.total_tokens == 10
    assert tracker_one.cost_usd > tracker_two.cost_usd


def test_budget_checks_apply_to_each_run():
    budget = BudgetConfig(max_tokens=100, max_cost_usd=1.0)
    over_tracker = UsageAccumulator()
    over_tracker.add_call(
        UsageCall(prompt_tokens=80, completion_tokens=30, total_tokens=110, cost_usd=0.5, provider="mock", model="mock")
    )
    assert _check_budget(budget, over_tracker) == "token_budget_exceeded"

    ok_tracker = UsageAccumulator()
    ok_tracker.add_call(
        UsageCall(prompt_tokens=20, completion_tokens=10, total_tokens=30, cost_usd=0.05, provider="mock", model="mock")
    )
    assert _check_budget(budget, ok_tracker) is None
