from billing.routes import _emit_post_commit_events


def test_checkout_completion_does_not_emit_subscription_activated(monkeypatch):
    emitted = []
    monkeypatch.setattr("integrations.events.emit_event", lambda name, payload: emitted.append((name, payload)))

    _emit_post_commit_events({
        "type": "checkout.session.completed",
        "data": {"object": {
            "metadata": {"user_id": "user-1", "plan_slug": "pro"},
        }},
    })

    assert emitted == []


def test_active_subscription_status_emits_activation(monkeypatch):
    emitted = []
    monkeypatch.setattr("integrations.events.emit_event", lambda name, payload: emitted.append((name, payload)))

    _emit_post_commit_events({
        "type": "customer.subscription.updated",
        "data": {"object": {
            "status": "active",
            "metadata": {"user_id": "user-1", "plan_slug": "pro"},
        }},
    })

    assert emitted == [(
        "subscription_activated",
        {"user_id": "user-1", "plan_slug": "pro", "provider": "stripe", "status": "active"},
    )]


def test_non_entitled_subscription_status_does_not_emit_activation(monkeypatch):
    emitted = []
    monkeypatch.setattr("integrations.events.emit_event", lambda name, payload: emitted.append((name, payload)))

    _emit_post_commit_events({
        "type": "customer.subscription.updated",
        "data": {"object": {
            "status": "past_due",
            "metadata": {"user_id": "user-1", "plan_slug": "pro"},
        }},
    })

    assert emitted == []
