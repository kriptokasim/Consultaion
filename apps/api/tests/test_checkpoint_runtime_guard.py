import pytest


def test_staging_active_checkpoint_requires_execution_lease(monkeypatch):
    import orchestration.checkpoints as checkpoints
    from checkpoint_runtime_guard import install_checkpoint_runtime_guard
    from config import settings

    install_checkpoint_runtime_guard()
    monkeypatch.setattr(settings, "APP_ENV", "staging")

    with pytest.raises(RuntimeError, match="ExecutionLease"):
        checkpoints._resolve_lease(None, allow_unfenced=False)


def test_staging_explicit_post_terminal_unfenced_stage_remains_allowed(monkeypatch):
    import orchestration.checkpoints as checkpoints
    from checkpoint_runtime_guard import install_checkpoint_runtime_guard
    from config import settings

    install_checkpoint_runtime_guard()
    monkeypatch.setattr(settings, "APP_ENV", "staging")

    assert checkpoints._resolve_lease(None, allow_unfenced=True) is None


def test_local_checkpoint_without_execution_lease_remains_testable(monkeypatch):
    import orchestration.checkpoints as checkpoints
    from checkpoint_runtime_guard import install_checkpoint_runtime_guard
    from config import settings

    install_checkpoint_runtime_guard()
    monkeypatch.setattr(settings, "APP_ENV", "local")

    assert checkpoints._resolve_lease(None, allow_unfenced=False) is None
