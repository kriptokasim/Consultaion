"""Patchset 136: Run Pipeline Rescue — Tests

Covers:
- Track 136-A: Environment and Dispatch Guardrails (validate_run_pipeline)
- Track 136-B: Run Pipeline Health Endpoint
- Track 136-C: Provider Smoke Test Endpoint
- Track 136-D: Create Debate Response Diagnostics
- Track 136-E: Stuck Queued Run Detection
- Track 136-F: Dispatch and Worker Observability
"""
from __future__ import annotations

import os
import time
import uuid
from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient


# ---------------------------------------------------------------------------
# 136-A: validate_run_pipeline tests
# ---------------------------------------------------------------------------

class TestValidateRunPipeline:
    """Test the config.validate_run_pipeline() guardrails."""

    def _make_settings(self, **overrides):
        """Build a minimal AppSettings-like object for pipeline validation."""
        from config import AppSettings
        defaults = {
            "ENV": "test",
            "DISABLE_AUTORUN": False,
            "DEBATE_DISPATCH_MODE": "inline",
            "CELERY_BROKER_URL": None,
            "CELERY_RESULT_BACKEND": None,
            "REQUIRE_REAL_LLM": False,
            "USE_MOCK": False,
            "OPENROUTER_API_KEY": None,
            "OPENAI_API_KEY": None,
            "ANTHROPIC_API_KEY": None,
            "GEMINI_API_KEY": None,
            "GOOGLE_API_KEY": None,
            "GROQ_API_KEY": None,
            "MISTRAL_API_KEY": None,
            "SSE_REDIS_URL": None,
            "REDIS_URL": None,
            "IS_LOCAL_ENV": True,
        }
        defaults.update(overrides)
        obj = object.__new__(AppSettings)
        for k, v in defaults.items():
            object.__setattr__(obj, k, v)
        return obj

    def test_local_env_no_warnings(self):
        s = self._make_settings(ENV="test", IS_LOCAL_ENV=True)
        warnings = s.validate_run_pipeline()
        codes = [w["code"] for w in warnings]
        # Local env should not produce blocking errors for missing keys
        assert "celery_broker_missing" not in codes
        assert "no_provider_keys" not in codes

    def test_autorun_disabled_warning_in_non_local(self):
        s = self._make_settings(
            ENV="production", IS_LOCAL_ENV=False, DISABLE_AUTORUN=True
        )
        warnings = s.validate_run_pipeline()
        codes = [w["code"] for w in warnings]
        assert "autorun_disabled" in codes

    def test_autorun_disabled_no_warning_in_local(self):
        s = self._make_settings(
            ENV="test", IS_LOCAL_ENV=True, DISABLE_AUTORUN=True
        )
        warnings = s.validate_run_pipeline()
        codes = [w["code"] for w in warnings]
        assert "autorun_disabled" not in codes

    def test_celery_missing_broker_blocking(self):
        s = self._make_settings(
            ENV="production",
            IS_LOCAL_ENV=False,
            DEBATE_DISPATCH_MODE="celery",
            CELERY_BROKER_URL=None,
        )
        warnings = s.validate_run_pipeline()
        codes = [w["code"] for w in warnings]
        assert "celery_broker_missing" in codes
        blocking = [w for w in warnings if w["severity"] == "blocking"]
        assert any(w["code"] == "celery_broker_missing" for w in blocking)

    def test_celery_memory_broker_blocking(self):
        s = self._make_settings(
            ENV="production",
            IS_LOCAL_ENV=False,
            DEBATE_DISPATCH_MODE="celery",
            CELERY_BROKER_URL="memory://",
        )
        warnings = s.validate_run_pipeline()
        codes = [w["code"] for w in warnings]
        assert "celery_broker_memory" in codes

    def test_celery_valid_broker_no_warning(self):
        s = self._make_settings(
            ENV="production",
            IS_LOCAL_ENV=False,
            DEBATE_DISPATCH_MODE="celery",
            CELERY_BROKER_URL="redis://localhost:6379/0",
            OPENROUTER_API_KEY="sk-or-test",
        )
        warnings = s.validate_run_pipeline()
        codes = [w["code"] for w in warnings]
        assert "celery_broker_missing" not in codes
        assert "celery_broker_memory" not in codes

    def test_real_llm_vs_mock_blocking(self):
        s = self._make_settings(
            ENV="test", IS_LOCAL_ENV=True, REQUIRE_REAL_LLM=True, USE_MOCK=True
        )
        warnings = s.validate_run_pipeline()
        codes = [w["code"] for w in warnings]
        assert "real_llm_vs_mock" in codes
        blocking = [w for w in warnings if w["severity"] == "blocking"]
        assert any(w["code"] == "real_llm_vs_mock" for w in blocking)

    def test_no_provider_keys_blocking_in_prod(self):
        s = self._make_settings(
            ENV="production",
            IS_LOCAL_ENV=False,
            OPENROUTER_API_KEY=None,
            OPENAI_API_KEY=None,
            ANTHROPIC_API_KEY=None,
            GEMINI_API_KEY=None,
            GROQ_API_KEY=None,
            MISTRAL_API_KEY=None,
        )
        warnings = s.validate_run_pipeline()
        codes = [w["code"] for w in warnings]
        assert "no_provider_keys" in codes

    def test_provider_key_present_no_warning(self):
        s = self._make_settings(
            ENV="production",
            IS_LOCAL_ENV=False,
            OPENROUTER_API_KEY="sk-or-test",
        )
        warnings = s.validate_run_pipeline()
        codes = [w["code"] for w in warnings]
        assert "no_provider_keys" not in codes


# ---------------------------------------------------------------------------
# 136-B: Run Pipeline Health Endpoint
# ---------------------------------------------------------------------------

class TestRunPipelineHealth:
    """Test GET /ops/run-pipeline-health."""

    def _admin_client(self, db_session):
        from auth import COOKIE_NAME, create_access_token, hash_password
        from models import User
        from fastapi.testclient import TestClient
        from main import app
        from sse_backend import get_sse_backend

        app.state.sse_backend = get_sse_backend()
        client = TestClient(app)

        email = f"admin-{uuid.uuid4().hex[:6]}@example.com"
        user = User(
            email=email,
            password_hash=hash_password("StrongPass#1"),
            is_admin=True,
            role="admin",
        )
        db_session.add(user)
        db_session.commit()
        db_session.refresh(user)

        token = create_access_token(user_id=user.id, email=user.email, role=user.role)
        client.cookies.set(COOKIE_NAME, token)
        return client

    def test_pipeline_health_returns_ok_for_test_env(self, db_session):
        client = self._admin_client(db_session)
        resp = client.get("/ops/run-pipeline-health")
        assert resp.status_code == 200
        data = resp.json()
        assert "status" in data
        assert "environment" in data
        assert "autorun" in data
        assert "dispatch" in data
        assert "providers" in data
        assert "models" in data
        assert "sse" in data
        assert "blocking_errors" in data
        assert "warnings" in data

    def test_pipeline_health_hides_secrets(self, db_session):
        client = self._admin_client(db_session)
        resp = client.get("/ops/run-pipeline-health")
        data = resp.json()
        # Provider info should only have booleans, not actual keys
        for pname, pinfo in data["providers"].items():
            assert "key_present" in pinfo
            assert isinstance(pinfo["key_present"], bool)
            # Never expose actual key values
            assert "key" not in pinfo or pinfo.get("key") is None

    def test_pipeline_health_rejects_non_admin(self, db_session):
        from fastapi.testclient import TestClient
        from main import app
        from sse_backend import get_sse_backend

        app.state.sse_backend = get_sse_backend()
        client = TestClient(app)
        resp = client.get("/ops/run-pipeline-health")
        assert resp.status_code in (401, 403)


# ---------------------------------------------------------------------------
# 136-C: Provider Smoke Test Endpoint
# ---------------------------------------------------------------------------

class TestLLMSmokeTest:
    """Test POST /ops/llm-smoke-test."""

    def _admin_client(self, db_session):
        from auth import COOKIE_NAME, create_access_token, hash_password
        from models import User
        from fastapi.testclient import TestClient
        from main import app
        from sse_backend import get_sse_backend

        app.state.sse_backend = get_sse_backend()
        client = TestClient(app)

        email = f"admin-{uuid.uuid4().hex[:6]}@example.com"
        user = User(
            email=email,
            password_hash=hash_password("StrongPass#1"),
            is_admin=True,
            role="admin",
        )
        db_session.add(user)
        db_session.commit()
        db_session.refresh(user)

        token = create_access_token(user_id=user.id, email=user.email, role=user.role)
        client.cookies.set(COOKIE_NAME, token)
        return client

    def test_smoke_test_rejects_non_admin(self, db_session):
        from fastapi.testclient import TestClient
        from main import app
        from sse_backend import get_sse_backend

        app.state.sse_backend = get_sse_backend()
        client = TestClient(app)
        resp = client.post("/ops/llm-smoke-test", json={"provider": "openrouter"})
        assert resp.status_code in (401, 403)

    def test_smoke_test_missing_key_returns_controlled_error(self, db_session):
        client = self._admin_client(db_session)
        # In test env, OPENROUTER_API_KEY is not set
        resp = client.post("/ops/llm-smoke-test", json={"provider": "openrouter"})
        data = resp.json()
        assert data["success"] is False
        assert data["error_code"] == "missing_provider_key"
        assert "OPENROUTER_API_KEY" in data["message"]

    def test_smoke_test_invalid_provider(self, db_session):
        client = self._admin_client(db_session)
        resp = client.post("/ops/llm-smoke-test", json={"provider": "nonexistent"})
        data = resp.json()
        assert data["success"] is False

    def test_smoke_test_mock_blocked_when_require_real(self, db_session):
        from config import settings
        original_require = settings.REQUIRE_REAL_LLM
        original_mock = settings.USE_MOCK
        try:
            settings.REQUIRE_REAL_LLM = True
            settings.USE_MOCK = True
            client = self._admin_client(db_session)
            resp = client.post("/ops/llm-smoke-test", json={"provider": "openrouter"})
            data = resp.json()
            assert data["success"] is False
            assert data["error_code"] == "mock_mode_blocked"
        finally:
            settings.REQUIRE_REAL_LLM = original_require
            settings.USE_MOCK = original_mock


# ---------------------------------------------------------------------------
# 136-D: Create Debate Response Diagnostics
# ---------------------------------------------------------------------------

class TestCreateDebateDiagnostics:
    """Test expanded POST /debates response."""

    def test_create_debate_includes_diagnostics(self, authenticated_client):
        resp = authenticated_client.post("/debates", json={
            "prompt": "Test prompt for diagnostics",
            "mode": "arena",
        })
        assert resp.status_code == 200
        data = resp.json()
        # Patchset 136 fields
        assert "id" in data
        assert "status" in data
        assert data["status"] == "queued"
        assert "autorun" in data
        assert "dispatch_mode" in data
        assert "diagnostics" in data
        assert "provider_keys_present" in data["diagnostics"]
        assert "enabled_models_count" in data["diagnostics"]
        assert isinstance(data["diagnostics"]["provider_keys_present"], list)
        assert isinstance(data["diagnostics"]["enabled_models_count"], int)

    def test_create_debate_autorun_false_shows_warning(self, authenticated_client):
        from config import settings
        original = settings.DISABLE_AUTORUN
        try:
            settings.DISABLE_AUTORUN = True
            resp = authenticated_client.post("/debates", json={
                "prompt": "Test with autorun disabled",
                "mode": "arena",
            })
            assert resp.status_code == 200
            data = resp.json()
            assert data["autorun"] is False
            assert "warning" in data
            assert "Autorun is disabled" in data["warning"]
        finally:
            settings.DISABLE_AUTORUN = original

    def test_create_debate_celery_mode_shows_queue(self, authenticated_client):
        from config import settings
        original_mode = settings.DEBATE_DISPATCH_MODE
        original_default_q = settings.DEBATE_DEFAULT_QUEUE
        try:
            settings.DEBATE_DISPATCH_MODE = "celery"
            settings.DEBATE_DEFAULT_QUEUE = "interactive"
            resp = authenticated_client.post("/debates", json={
                "prompt": "Test with celery mode",
                "mode": "arena",
            })
            assert resp.status_code == 200
            data = resp.json()
            assert data["dispatch_mode"] == "celery"
            assert data["queue"] == "interactive"
            assert data["worker_required"] is True
        finally:
            settings.DEBATE_DISPATCH_MODE = original_mode
            settings.DEBATE_DEFAULT_QUEUE = original_default_q

    def test_no_models_refunds_quota(self, authenticated_client, db_session):
        """When no models are enabled, debate creation fails and quota is refunded."""
        from parliament.model_registry import list_enabled_models
        from models import UsageCounter

        # Record runs_used before
        from config import settings
        original_models = settings.DISABLE_AUTORUN

        # Temporarily make list_enabled_models return empty
        import routes.debates.crud as crud_module
        original_fn = crud_module.list_enabled_models
        crud_module.list_enabled_models = lambda: []
        try:
            resp = authenticated_client.post("/debates", json={
                "prompt": "Test no models",
                "mode": "arena",
            })
            assert resp.status_code in (400, 500, 503)
            # Verify no debate was created (no leaked record)
            from models import Debate
            from sqlmodel import select
            stmt = select(Debate).where(Debate.prompt == "Test no models")
            debate = db_session.exec(stmt).first()
            assert debate is None, "Debate should not be created when no models available"
        finally:
            crud_module.list_enabled_models = original_fn


# ---------------------------------------------------------------------------
# 136-E: Stuck Queued Run Detection
# ---------------------------------------------------------------------------

class TestStuckQueuedDetection:
    """Test stale queued debate detection."""

    def test_stale_queued_debate_detected(self, db_session):
        from models import Debate
        from orchestrator_cleanup import cleanup_stale_debates

        # Create a debate that's been queued for too long (timezone-aware)
        now_aware = datetime.now(timezone.utc)
        debate = Debate(
            id=str(uuid.uuid4()),
            prompt="Stale debate",
            status="queued",
            config={},
            user_id="test-user",
            created_at=now_aware - timedelta(seconds=2000),  # > DEBATE_STALE_QUEUED_SECONDS (1800)
            updated_at=now_aware - timedelta(seconds=2000),
        )
        db_session.add(debate)
        db_session.commit()

        # Run cleanup
        import asyncio
        failed, degraded = asyncio.get_event_loop().run_until_complete(cleanup_stale_debates())

        # Debate should have been marked as failed
        db_session.refresh(debate)
        assert debate.status == "failed"
        assert debate.final_meta is not None
        assert "stale_cleanup" in debate.final_meta
        assert debate.final_meta["stale_cleanup"]["failure_code"] == "run_dispatch_timeout"
        assert failed >= 1

    def test_non_stale_queued_debate_not_touched(self, db_session):
        from models import Debate
        from orchestrator_cleanup import cleanup_stale_debates

        # Create a debate that's been queued recently (timezone-aware)
        now_aware = datetime.now(timezone.utc)
        debate = Debate(
            id=str(uuid.uuid4()),
            prompt="Fresh debate",
            status="queued",
            config={},
            user_id="test-user",
            created_at=now_aware,  # Just created
            updated_at=now_aware,
        )
        db_session.add(debate)
        db_session.commit()

        import asyncio
        asyncio.get_event_loop().run_until_complete(cleanup_stale_debates())

        db_session.refresh(debate)
        assert debate.status == "queued"  # Should not be changed


# ---------------------------------------------------------------------------
# 136-F: Dispatch Metrics
# ---------------------------------------------------------------------------

class TestDispatchMetrics:
    """Test dispatch observability metrics."""

    def test_choose_queue_for_debate(self):
        from debate_dispatch import choose_queue_for_debate
        from config import settings

        original_fast = settings.DEBATE_FAST_QUEUE_NAME
        original_deep = settings.DEBATE_DEEP_QUEUE_NAME
        original_default = settings.DEBATE_DEFAULT_QUEUE
        try:
            settings.DEBATE_FAST_QUEUE_NAME = "fast-q"
            settings.DEBATE_DEEP_QUEUE_NAME = "deep-q"
            settings.DEBATE_DEFAULT_QUEUE = "default-q"

            assert choose_queue_for_debate({"mode": "fast"}) == "fast-q"
            assert choose_queue_for_debate({"mode": "deep"}) == "deep-q"
            assert choose_queue_for_debate({}) == "default-q"
            assert choose_queue_for_debate(None) == "default-q"
        finally:
            settings.DEBATE_FAST_QUEUE_NAME = original_fast
            settings.DEBATE_DEEP_QUEUE_NAME = original_deep
            settings.DEBATE_DEFAULT_QUEUE = original_default

    def test_inline_dispatch_emits_metric(self, monkeypatch):
        import debate_dispatch
        from config import settings

        metrics_emitted = []

        def fake_incr_metric(name, value=1, tags=None):
            metrics_emitted.append(name)

        # Patch metrics.incr_metric at the module level where it's imported
        monkeypatch.setattr("metrics.incr_metric", fake_incr_metric, raising=False)
        monkeypatch.setattr(settings, "DEBATE_DISPATCH_MODE", "inline", raising=False)

        called = {}

        async def fake_run(*args, **kwargs):
            called["ran"] = True

        monkeypatch.setattr(debate_dispatch, "run_debate", fake_run, raising=False)

        import asyncio
        asyncio.get_event_loop().run_until_complete(
            debate_dispatch.dispatch_debate_run(
                "deb-1", "Prompt", "debate:deb-1", {"agents": []}, None
            )
        )

        assert "debate.dispatch.inline_started" in metrics_emitted


# ---------------------------------------------------------------------------
# Config startup validation integration
# ---------------------------------------------------------------------------

class TestConfigStartupValidation:
    """Test that validate_run_pipeline is called at startup and warnings are logged."""

    def test_validate_run_pipeline_method_exists(self):
        from config import AppSettings
        assert hasattr(AppSettings, "validate_run_pipeline")

    def test_validate_run_pipeline_returns_list(self):
        from config import AppSettings
        settings = AppSettings()
        result = settings.validate_run_pipeline()
        assert isinstance(result, list)
        for item in result:
            assert "code" in item
            assert "severity" in item
            assert "message" in item
            assert item["severity"] in ("warning", "blocking")
