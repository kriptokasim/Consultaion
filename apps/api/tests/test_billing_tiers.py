from billing.models import BillingPlan
from models import User
from parliament.model_registry import ModelInfo
from sqlmodel import Session, select


def test_free_plan_restrictions(authenticated_client, db_session: Session, monkeypatch):
    # Ensure we are using the Free plan
    user = db_session.exec(select(User).where(User.email == "normal@example.com")).first()
    # The default user created by authenticated_client doesn't explicitly have a subscription,
    # so get_active_plan should fallback to the default free plan.
    
    # Mock list_enabled_models to ensure we have known standard and advanced models
    standard_model = ModelInfo(
        id="standard-model", 
        display_name="Standard", 
        provider="openai", 
        litellm_model="gpt-3.5", 
        tier="standard",
        cost_tier="low",
        latency_class="fast",
        quality_tier="baseline",
        safety_profile="normal",
        enabled=True
    )
    advanced_model = ModelInfo(
        id="advanced-model", 
        display_name="Advanced", 
        provider="openai", 
        litellm_model="gpt-4", 
        tier="advanced",
        cost_tier="high",
        latency_class="normal",
        quality_tier="flagship",
        safety_profile="strict",
        enabled=True
    )
    
    # We need to patch where it's used. 
    # In routes/debates.py: `from parliament.model_registry import list_enabled_models`
    # But it might be imported as `list_enabled_models` or used via `ALL_MODELS`.
    # Let's check routes/debates.py again.
    # It calls `list_enabled_models()` inside the module scope to create `enabled_models` dict?
    # No, it calls it inside the endpoint or uses a global?
    # Actually, `routes/debates.py` does:
    # `enabled_models = {m.id: m for m in list_enabled_models()}` at module level?
    # If so, we can't easily patch it without reloading the module.
    # Let's assume we can use the real models "gpt4o-mini" (standard) and "gpt4o-deep" (advanced).
    
    # Standard model (should succeed)
    payload_standard = {"prompt": "Test Standard", "model_id": "gpt4o-mini"}
    # We need to mock the actual debate dispatch to avoid running LLM
    monkeypatch.setattr("routes.debates.dispatch_debate_run", lambda *args, **kwargs: None)
    
    resp = authenticated_client.post("/debates", json=payload_standard)
    assert resp.status_code == 200, f"Standard model failed: {resp.text}"
    
    # Advanced model (should fail on Free plan)
    payload_advanced = {"prompt": "Test Advanced", "model_id": "gpt4o-deep"}
    resp = authenticated_client.post("/debates", json=payload_advanced)
    assert resp.status_code == 400, f"Advanced model should have failed but got {resp.status_code}"
    data = resp.json()
    assert data["error"]["code"] == "debate.model_tier_restricted"

def test_pro_plan_access(authenticated_client, db_session: Session, monkeypatch):
    # Upgrade user to Pro
    user = db_session.exec(select(User).where(User.email == "normal@example.com")).first()
    pro_plan = db_session.exec(select(BillingPlan).where(BillingPlan.slug == "pro")).first()
    
    from datetime import datetime, timedelta, timezone

    from billing.models import BillingSubscription
    
    sub = BillingSubscription(
        user_id=user.id,
        plan_id=pro_plan.id,
        status="active",
        current_period_start=datetime.now(timezone.utc),
        current_period_end=datetime.now(timezone.utc) + timedelta(days=30),
        provider="manual"
    )
    db_session.add(sub)
    db_session.commit()
    
    # Mock dispatch
    monkeypatch.setattr("routes.debates.dispatch_debate_run", lambda *args, **kwargs: None)
    
    # Advanced model (should succeed on Pro plan)
    payload_advanced = {"prompt": "Test Advanced Pro", "model_id": "gpt4o-deep"}
    resp = authenticated_client.post("/debates", json=payload_advanced)
    assert resp.status_code == 200, f"Advanced model failed for Pro user: {resp.text}"

