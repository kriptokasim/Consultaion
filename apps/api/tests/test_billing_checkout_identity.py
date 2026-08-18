from types import SimpleNamespace

from billing.models import BillingPlan
from billing.routes import CheckoutRequest, create_checkout


def test_checkout_passes_exact_non_uuid_user_id(monkeypatch):
    class Result:
        def first(self):
            return BillingPlan(
                slug="pro",
                name="Pro",
                is_default_free=False,
                limits={},
            )

    class SessionStub:
        def exec(self, _statement):
            return Result()

    captured = {}

    class ProviderStub:
        def create_checkout_session(self, user_id, plan):
            captured["user_id"] = user_id
            captured["plan"] = plan.slug
            return "https://checkout.example/test"

    monkeypatch.setattr("billing.routes.get_billing_provider", lambda: ProviderStub())
    user = SimpleNamespace(id="legacy-user-42")

    response = create_checkout(
        CheckoutRequest(plan_slug="pro"),
        session=SessionStub(),
        current_user=user,
    )

    assert response["checkout_url"] == "https://checkout.example/test"
    assert captured == {"user_id": "legacy-user-42", "plan": "pro"}
