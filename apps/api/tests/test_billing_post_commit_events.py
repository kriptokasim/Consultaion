from billing.routes import _emit_post_commit_events


def _capture(monkeypatch):
    emitted = []
    monkeypatch.setattr(
        "integrations.events.emit_event",
        lambda name, payload: emitted.append((name, payload)),
    )
    return emitted


def test_checkout_completion_does_not_emit_subscription_activated(monkeypatch):
    emitted = _capture(monkeypatch)

    _emit_post_commit_events({
        "type": "checkout.session.completed",
        "data": {"object": {
            "metadata": {"user_id": "user-1", "plan_slug": "pro"},
        }},
    })

    assert emitted == []


def test_entering_active_subscription_emits_activation(monkeypatch):
    emitted = _capture(monkeypatch)

    _emit_post_commit_events({
        "type": "customer.subscription.updated",
        "_consultaion_previous_subscription_status": "pending",
        "data": {"object": {
            "status": "active",
            "metadata": {"user_id": "user-1", "plan_slug": "pro"},
        }},
    })

    assert emitted == [(
        "subscription_activated",
        {"user_id": "user-1", "plan_slug": "pro", "provider": "stripe", "status": "active"},
    )]


def test_new_active_subscription_emits_activation(monkeypatch):
    emitted = _capture(monkeypatch)

    _emit_post_commit_events({
        "type": "customer.subscription.created",
        "_consultaion_previous_subscription_status": None,
        "data": {"object": {
            "status": "active",
            "metadata": {"user_id": "user-1", "plan_slug": "pro"},
        }},
    })

    assert len(emitted) == 1
    assert emitted[0][0] == "subscription_activated"


def test_active_to_active_update_does_not_repeat_activation(monkeypatch):
    emitted = _capture(monkeypatch)

    _emit_post_commit_events({
        "type": "customer.subscription.updated",
        "_consultaion_previous_subscription_status": "active",
        "data": {"object": {
            "status": "active",
            "metadata": {"user_id": "user-1", "plan_slug": "pro"},
        }},
    })

    assert emitted == []


def test_duplicate_webhook_skips_all_external_side_effects(monkeypatch):
    emitted = _capture(monkeypatch)

    _emit_post_commit_events({
        "type": "customer.subscription.updated",
        "_consultaion_duplicate": True,
        "_consultaion_previous_subscription_status": "pending",
        "data": {"object": {
            "status": "active",
            "metadata": {"user_id": "user-1", "plan_slug": "pro"},
        }},
    })

    assert emitted == []


def test_non_entitled_subscription_status_does_not_emit_activation(monkeypatch):
    emitted = _capture(monkeypatch)

    _emit_post_commit_events({
        "type": "customer.subscription.updated",
        "_consultaion_previous_subscription_status": "active",
        "data": {"object": {
            "status": "past_due",
            "metadata": {"user_id": "user-1", "plan_slug": "pro"},
        }},
    })

    assert emitted == []


def test_subscription_deleted_emits_once_for_prior_non_cancelled_state(monkeypatch):
    emitted = _capture(monkeypatch)

    _emit_post_commit_events({
        "type": "customer.subscription.deleted",
        "_consultaion_previous_subscription_status": "active",
        "data": {"object": {"id": "sub-1"}},
    })

    assert emitted == [(
        "subscription_cancelled",
        {"subscription_id": "sub-1", "provider": "stripe"},
    )]
