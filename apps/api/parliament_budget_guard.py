from __future__ import annotations

import asyncio
import threading
from dataclasses import dataclass, field
from typing import Any

import sqlalchemy as sa
from agents import call_llm_for_role as _call_llm_for_role
from database_async import async_session_scope
from models import Debate, LLMUsageLog

_state_lock = threading.Lock()


class ParliamentBudgetExceeded(RuntimeError):
    pass


@dataclass
class _BudgetState:
    max_tokens: int | None
    max_cost_usd: float | None
    tokens: int = 0
    cost_usd: float = 0.0
    lock: threading.Lock = field(default_factory=threading.Lock)


_states: dict[str, _BudgetState | None] = {}
_init_locks: dict[str, asyncio.Lock] = {}


async def _load_state(debate_id: str) -> _BudgetState | None:
    with _state_lock:
        if debate_id in _states:
            return _states[debate_id]
        init_lock = _init_locks.setdefault(debate_id, asyncio.Lock())

    async with init_lock:
        with _state_lock:
            if debate_id in _states:
                return _states[debate_id]

        async with async_session_scope() as session:
            debate = await session.get(Debate, debate_id)
            budget = (debate.config or {}).get("budget") if debate else None
            if not isinstance(budget, dict) or (
                budget.get("max_tokens") is None and budget.get("max_cost_usd") is None
            ):
                state = None
            else:
                result = await session.execute(
                    sa.select(
                        sa.func.coalesce(sa.func.sum(LLMUsageLog.total_tokens), 0),
                        sa.func.coalesce(sa.func.sum(LLMUsageLog.cost_usd), 0.0),
                    ).where(LLMUsageLog.debate_id == debate_id)
                )
                row = result.first()
                state = _BudgetState(
                    max_tokens=(
                        int(budget["max_tokens"])
                        if budget.get("max_tokens") is not None
                        else None
                    ),
                    max_cost_usd=(
                        float(budget["max_cost_usd"])
                        if budget.get("max_cost_usd") is not None
                        else None
                    ),
                    tokens=int(row[0] if row else 0),
                    cost_usd=float(row[1] if row else 0.0),
                )

        with _state_lock:
            _states[debate_id] = state
            _init_locks.pop(debate_id, None)
        return state


def _assert_headroom(state: _BudgetState) -> None:
    if state.max_tokens is not None and state.tokens >= state.max_tokens:
        raise ParliamentBudgetExceeded("token_budget_exceeded")
    if state.max_cost_usd is not None and state.cost_usd >= state.max_cost_usd:
        raise ParliamentBudgetExceeded("cost_budget_exceeded")


async def call_llm_for_role_budgeted(*args: Any, **kwargs: Any):
    """Canonical Parliament provider boundary with durable budget accounting.

    Existing seat concurrency is preserved: calls already in flight may finish,
    while later seat groups/chair/judges are rejected before a new provider call.
    This bounds overshoot to the currently active concurrent group rather than
    serializing Structured Debate.
    """
    debate_id = kwargs.get("debate_id")
    state = await _load_state(str(debate_id)) if debate_id else None
    if state is not None:
        with state.lock:
            _assert_headroom(state)

    result = await _call_llm_for_role(*args, **kwargs)
    if state is not None and isinstance(result, tuple) and len(result) >= 2:
        usage = result[1]
        with state.lock:
            state.tokens += max(int(getattr(usage, "total_tokens", 0) or 0), 0)
            state.cost_usd += max(float(getattr(usage, "cost_usd", 0.0) or 0.0), 0.0)
    return result
