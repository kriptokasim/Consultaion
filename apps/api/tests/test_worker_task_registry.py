import importlib


def test_worker_declares_every_production_task_module():
    from worker.celery_app import PRODUCTION_TASK_MODULES, celery_app

    required = {
        "worker.billing_tasks",
        "worker.debate_tasks",
        "worker.arena_tasks",
        "worker.coding_tasks",
        "worker.voting_tasks",
        "worker.terminal_tasks",
    }
    assert required.issubset(set(PRODUCTION_TASK_MODULES))
    assert required.issubset(set(celery_app.conf.imports or ()))


def test_production_task_modules_register_expected_task_names():
    from worker.celery_app import PRODUCTION_TASK_MODULES, celery_app

    for module_name in PRODUCTION_TASK_MODULES:
        importlib.import_module(module_name)

    required_tasks = {
        "debates.run",
        "arena.compute_divergence",
        "coding.execute_turn",
        "voting.extract_vote_reasons",
        "billing.reconcile_previous_day",
        "billing.reconcile_current_period",
        "billing.reconcile_terminal_hosted_credits",
        "maintenance.reconcile_terminal_summary_emails",
        "worker.heartbeat_tick",
    }
    assert required_tasks.issubset(set(celery_app.tasks.keys()))


def test_terminal_summary_reconciler_is_scheduled():
    from worker.celery_app import celery_app

    schedule = celery_app.conf.beat_schedule or {}
    entry = schedule.get("terminal-summary-email-reconcile")
    assert entry is not None
    assert entry["task"] == "maintenance.reconcile_terminal_summary_emails"
