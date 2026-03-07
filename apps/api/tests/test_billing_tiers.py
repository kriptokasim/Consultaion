from billing.models import BillingPlan
from models import User
from parliament.model_registry import ModelInfo
from sqlmodel import Session, select

def test_free_plan_restrictions(authenticated_client, db_session: Session, monkeypatch):
    user = db_session.exec(select(User).where(User.email == 'normal@example.com')).first()
    standard_model = ModelInfo(id='standard-model', display_name='Standard', provider='openai', litellm_model='gpt-3.5', tier='standard', cost_tier='low', latency_class='fast', quality_tier='baseline', safety_profile='normal', enabled=True)
    advanced_model = ModelInfo(id='advanced-model', display_name='Advanced', provider='openai', litellm_model='gpt-4', tier='advanced', cost_tier='high', latency_class='normal', quality_tier='flagship', safety_profile='strict', enabled=True)
    payload_standard = {'prompt': 'Test Standard', 'model_id': 'gpt4o-mini', 'mode': 'debate'}
    monkeypatch.setattr('routes.debates.dispatch_debate_run', lambda *args, **kwargs: None)
    resp = authenticated_client.post('/debates', json=payload_standard)
    assert resp.status_code == 200, f'Standard model failed: {resp.text}'
    payload_advanced = {'prompt': 'Test Advanced', 'model_id': 'gpt4o-deep'}
    resp = authenticated_client.post('/debates', json=payload_advanced)
    assert resp.status_code == 400, f'Advanced model should have failed but got {resp.status_code}'
    data = resp.json()
    assert data['error']['code'] == 'debate.model_tier_restricted'

def test_pro_plan_access(authenticated_client, db_session: Session, monkeypatch):
    user = db_session.exec(select(User).where(User.email == 'normal@example.com')).first()
    pro_plan = db_session.exec(select(BillingPlan).where(BillingPlan.slug == 'pro')).first()
    from datetime import datetime, timedelta, timezone
    from billing.models import BillingSubscription
    sub = BillingSubscription(user_id=user.id, plan_id=pro_plan.id, status='active', current_period_start=datetime.now(timezone.utc), current_period_end=datetime.now(timezone.utc) + timedelta(days=30), provider='manual')
    db_session.add(sub)
    db_session.commit()
    monkeypatch.setattr('routes.debates.dispatch_debate_run', lambda *args, **kwargs: None)
    payload_advanced = {'prompt': 'Test Advanced Pro', 'model_id': 'gpt4o-deep', 'mode': 'debate'}
    resp = authenticated_client.post('/debates', json=payload_advanced)
    assert resp.status_code == 200, f'Advanced model failed for Pro user: {resp.text}'