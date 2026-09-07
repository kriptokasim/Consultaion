"""Cost accounting must survive the hop through the LiteLLM proxy.

In proxy mode the model string handed to the SDK is a deployment name
("openai/seat_anthropic"), which litellm cannot price -- cost_per_token() raises
"This model isn't mapped yet". Every local cost path therefore returns 0.0 for a
call that genuinely cost money.

That zero is not harmless. attempt_tracker treats a zero cost alongside real
token counts as a *measured* zero -- the signature of a free route -- and
releases the reservation. So a paid proxy call would accrue nothing against the
monthly cap, and llm_usage_log would record a debate that cost nothing. It is
the dead free-model billing guard again, through a different door.
"""
from __future__ import annotations

import pytest

from model_gateway.adapters import _proxy_reported_cost, _stream_cost

COST_HEADER = "llm_provider-x-litellm-response-cost"


class FakeResponse:
    """Stands in for a litellm ModelResponse carrying proxy hidden params."""

    def __init__(self, hidden=None, response_cost=None):
        if hidden is not None:
            self._hidden_params = hidden
        if response_cost is not None:
            self.response_cost = response_cost


def _with_proxy_cost(value):
    return FakeResponse(hidden={"additional_headers": {COST_HEADER: value}})


def test_the_sdk_cannot_price_a_proxy_deployment_name():
    """The premise. If this ever stops raising, the fix below is redundant."""
    import litellm

    with pytest.raises(Exception):
        litellm.cost_per_token(
            model="openai/seat_openai_fast", prompt_tokens=1000, completion_tokens=500
        )


def test_proxy_reported_cost_is_read_from_the_header():
    assert _proxy_reported_cost(_with_proxy_cost("0.0042")) == pytest.approx(0.0042)
    assert _proxy_reported_cost(_with_proxy_cost(0.0042)) == pytest.approx(0.0042)


@pytest.mark.parametrize(
    "response",
    [
        FakeResponse(),
        FakeResponse(hidden={}),
        FakeResponse(hidden={"additional_headers": {}}),
        FakeResponse(hidden={"additional_headers": None}),
        FakeResponse(hidden="not-a-dict"),
        _with_proxy_cost(None),
        _with_proxy_cost("not-a-number"),
        _with_proxy_cost(0),
        _with_proxy_cost(-1),
    ],
)
def test_absent_or_unusable_header_reports_nothing(response):
    """None, not 0.0 -- so callers fall through to their other sources.

    Returning 0.0 here would look like a measured free call, which is exactly
    the confusion this whole module exists to prevent.
    """
    assert _proxy_reported_cost(response) is None


def test_stream_cost_prefers_the_proxy_figure():
    chunk = FakeResponse(
        hidden={"additional_headers": {COST_HEADER: "0.0100"}, "response_cost": 0.0},
        response_cost=0.0,
    )
    assert _stream_cost(chunk, {"total_cost": 0.0}) == pytest.approx(0.0100)


def test_stream_cost_unchanged_on_the_direct_path():
    """A direct-mode chunk has no proxy header; behaviour must not shift."""
    chunk = FakeResponse(response_cost=0.005)
    assert _stream_cost(chunk, {}) == pytest.approx(0.005)

    chunk_usage_only = FakeResponse()
    assert _stream_cost(chunk_usage_only, {"total_cost": 0.007}) == pytest.approx(0.007)

    assert _stream_cost(FakeResponse(), {}) == 0.0


def test_a_zero_cost_proxy_call_is_not_treated_as_a_free_route():
    """Bounds the blast radius of the bug, so nobody overstates it later.

    A proxy deployment slug does not match a free route, so attempt_tracker
    keeps the conservative reservation rather than refunding it. The monthly cap
    therefore still binds even with the cost reading zero: this is a reporting
    and reconciliation defect, not a spend-control hole. Worth pinning, because
    the natural assumption is the scarier one.
    """
    from model_gateway.attempt_tracker import _result_has_measured_zero_cost
    from model_gateway.types import GatewayModelCallResult

    def result(cost):
        return GatewayModelCallResult(
            content="x",
            model_used="openai/seat_anthropic",
            provider="litellm_proxy",
            prompt_tokens=1200,
            completion_tokens=340,
            total_tokens=1540,
            cost_usd=cost,
            success=True,
            model_pool="arena_primary_pool",
            routing_policy="proxy",
        )

    assert _result_has_measured_zero_cost(result(0.0), "openai/seat_anthropic") is False
    assert _result_has_measured_zero_cost(result(0.0042), "openai/seat_anthropic") is False

    # The contrast: a genuinely free slug is still recognised as one.
    free = result(0.0)
    free.model_used = "openrouter/openrouter/free"
    assert _result_has_measured_zero_cost(free, "router-smart") is True


def test_interrupted_proxy_stream_estimates_against_the_real_slug():
    """The estimator must never see a deployment name.

    _estimate_stream_usage() calls token_counter() and cost_per_token(), both of
    which raise on "openai/seat_anthropic". The whole body is wrapped in a bare
    except, so the failure was silent: an interrupted proxy stream recorded zero
    tokens and zero cost for work that had actually been done. Pricing off the
    pre-override slug keeps the estimate real.
    """
    from model_gateway.adapters import _estimate_stream_usage

    messages = [{"role": "user", "content": "hello " * 200}]

    real = _estimate_stream_usage(
        model="openai/gpt-4o-mini", messages=messages, content="a reply " * 50
    )
    deployment = _estimate_stream_usage(
        model="openai/seat_openai_fast", messages=messages, content="a reply " * 50
    )

    prompt_tokens, completion_tokens, total_tokens, cost = real
    assert prompt_tokens > 0 and completion_tokens > 0 and total_tokens > 0
    assert cost > 0

    # The failure mode being guarded against: everything silently zero.
    assert deployment == (0, 0, 0, 0.0)


def test_every_estimate_call_prices_off_the_real_slug():
    """Structural guard over the source, since the methods are decorated.

    ``target_model`` is still correct for the acompletion call -- that one *must*
    carry the deployment name -- so this checks only the estimator call sites.
    """
    import re
    from pathlib import Path

    import model_gateway.adapters as adapters_module

    src = Path(adapters_module.__file__).read_text()

    # Capture is before the override, so it holds the pre-proxy slug.
    assert "pricing_model = target_model" in src
    assert src.index("pricing_model = target_model") < src.index("proxy_overrides(")

    calls = re.findall(r"_estimate_stream_usage\(\s*\n\s*model=(\w+),", src)
    assert calls, "no estimate call sites found -- has the helper been renamed?"

    # DirectProviderAdapter's three sites must use pricing_model. OpenRouterAdapter
    # has no proxy override, so target_model is already the real slug there.
    assert calls.count("pricing_model") == 3, (
        f"expected 3 estimate calls priced off pricing_model, got {calls}"
    )
