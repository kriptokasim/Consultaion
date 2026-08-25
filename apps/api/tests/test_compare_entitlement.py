"""Prod-critical hardening — Compare mode model entitlement at create boundary.

Covers PC-CMP-002: every compare model must be canonical, enabled for the
user, tier-allowed, and unique; at least two valid UNIQUE models are required
after normalization. Free-plan runs containing advanced models must reserve a
hosted credit exactly like Arena runs (per-run reservation policy).
"""

import os
from unittest.mock import MagicMock, patch

import pytest
from models import Debate
from sqlmodel import Session

os.environ["RL_MAX_CALLS"] = "1000"
os.environ["AUTH_RL_MAX_CALLS"] = "1000"
os.environ["USE_MOCK"] = "1"


def _model(mid: str, tier: str = "standard") -> MagicMock:
    m = MagicMock()
    m.id = mid
    m.tier = tier
    m.display_name = mid.upper()
    return m


@pytest.fixture(autouse=True)
def mock_rate_limiter():
    with patch("routes.debates.crud.increment_ip_bucket", return_value=(True, 0)):
        yield


@pytest.fixture(autouse=True)
def mock_dispatch():
    with patch("routes.debates.crud.dispatch_debate_run"):
        yield


def _enabled(*models: MagicMock):
    return patch(
        "routes.debates.crud.list_enabled_models_for_user",
        return_value=list(models),
    )


def test_compare_rejects_single_model(authenticated_client):
    with _enabled(_model("m-a")):
        res = authenticated_client.post(
            "/debates",
            json={"prompt": "compare entitlement probe", "mode": "compare", "compare_models": ["m-a"]},
        )
    assert res.status_code in (400, 422)
    body = res.json()
    code = (body.get("code") or body.get("error", {}).get("code") or "")
    assert code.endswith("invalid_compare_models")


def test_compare_dedupes_and_requires_two_distinct(authenticated_client):
    with _enabled(_model("m-a"), _model("m-b")):
        res = authenticated_client.post(
            "/debates",
            json={
                "prompt": "compare entitlement probe",
                "mode": "compare",
                "compare_models": ["m-a", "m-a", "m-a"],
            },
        )
    assert res.status_code in (400, 422)


def test_compare_rejects_unknown_or_disabled_model(authenticated_client):
    with _enabled(_model("m-a"), _model("m-b")):
        res = authenticated_client.post(
            "/debates",
            json={
                "prompt": "compare entitlement probe",
                "mode": "compare",
                "compare_models": ["m-a", "not-in-registry"],
            },
        )
    assert res.status_code in (400, 422)


def test_compare_rejects_tier_restricted_for_free_plan(authenticated_client):
    """Free plan + advanced models + NO available hosted credit must fail at
    the boundary instead of executing paid provider work unreserved."""
    from exceptions import ValidationError

    with _enabled(
        _model("m-a", "standard"), _model("adv-x", "advanced")
    ), patch(
        "routes.debates.crud.choose_model"
    ) as mock_choose, patch(
        "billing.service.reserve_hosted_credit"
    ) as mock_reserve:
        mock_choose.return_value = ("m-a", [])
        mock_reserve.side_effect = ValidationError(
            message="No hosted credits remaining",
            code="hosted_credits.exhausted",
            status_code=402,
        )
        res = authenticated_client.post(
            "/debates",
            json={
                "prompt": "compare entitlement probe",
                "mode": "compare",
                "compare_models": ["m-a", "adv-x"],
            },
        )
    assert res.status_code in (400, 402)
    body = res.json()
    code = (body.get("code") or body.get("error", {}).get("code") or "")
    assert code in ("hosted_credits.exhausted", "debate.model_tier_restricted", "debate.invalid_model")


def test_compare_accepts_valid_unique_standard_pair(authenticated_client, db_session: Session):
    with _enabled(_model("m-a"), _model("m-b")), patch(
        "routes.debates.crud.choose_model"
    ) as mock_choose:
        mock_choose.return_value = ("m-a", [])
        res = authenticated_client.post(
            "/debates",
            json={
                "prompt": "compare entitlement probe",
                "mode": "compare",
                "compare_models": [" m-a ", "m-b"],
            },
        )
    assert res.status_code == 200, res.text
    debate = db_session.get(Debate, res.json()["id"])
    stored = debate.config.get("compare_models")
    assert stored == ["m-a", "m-b"], "models must be normalized (stripped) and deduplicated"


def test_compare_free_plan_with_advanced_reserves_hosted_credit(
    authenticated_client, db_session: Session
):
    """Free user + advanced compare models => run must carry a hosted credit
    reservation (same per-run policy as Arena)."""
    with _enabled(
        _model("m-a", "standard"), _model("adv-x", "advanced")
    ), patch("routes.debates.crud.choose_model") as mock_choose:
        mock_choose.return_value = ("m-a", [])
        res = authenticated_client.post(
            "/debates",
            json={"prompt": "compare entitlement probe", "mode": "compare", "compare_models": ["m-a", "adv-x"]},
        )
    assert res.status_code == 200, res.text
    debate = db_session.get(Debate, res.json()["id"])
    # Hosted credit reserved for the run (advanced execution must never be free)
    assert debate.credit_reservation_id, (
        "free-plan compare run with advanced models must reserve a hosted credit"
    )
