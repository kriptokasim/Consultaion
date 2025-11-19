import asyncio
import os
import sys
import uuid
from pathlib import Path

from fastapi import BackgroundTasks
from starlette.requests import Request

os.environ.setdefault("JWT_SECRET", "test-secret")
os.environ.setdefault("USE_MOCK", "1")
sys.path.append(str(Path(__file__).resolve().parents[1]))

from billing.models import BillingUsage  # noqa: E402
from billing.routes import get_model_usage  # noqa: E402
from billing.service import _current_period  # noqa: E402
from database import engine, init_db  # noqa: E402
from main import app  # noqa: E402
from model_registry import ModelConfig, ModelProvider, list_enabled_models  # noqa: E402
from models import User  # noqa: E402
from routes.debates import create_debate  # noqa: E402
import agents as agents_module  # noqa: E402
from schemas import DebateCreate  # noqa: E402
from sqlmodel import Session  # noqa: E402
from deps import get_optional_user  # noqa: E402


def _dummy_request(path: str = "/debates") -> Request:
    scope = {
        "type": "http",
        "asgi": {"version": "3.0"},
        "http_version": "1.1",
        "method": "POST",
        "path": path,
        "raw_path": path.encode(),
        "query_string": b"",
        "headers": [],
        "client": ("testclient", 0),
        "server": ("testserver", 80),
        "scheme": "http",
    }
    return Request(scope)


def test_models_endpoint_lists_entries(monkeypatch):
    monkeypatch.setenv("USE_MOCK", "1")
    models = list_enabled_models()
    assert len(models) >= 1


def test_create_debate_invalid_model(monkeypatch):
    monkeypatch.setenv("USE_MOCK", "1")
    monkeypatch.setenv("DISABLE_AUTORUN", "1")
    init_db()
    body = DebateCreate(prompt="This is a sufficiently long prompt text", model_id="nope")
    with Session(engine) as session:
        try:
            background_tasks = BackgroundTasks()
            request = _dummy_request()
            asyncio.run(create_debate(body, background_tasks, request, session, None))  # type: ignore[arg-type]
            assert False, "Expected HTTPException for invalid model id"
        except Exception as exc:
            assert "model" in str(exc)


def test_call_llm_uses_registry_model(monkeypatch):
    monkeypatch.setenv("USE_MOCK", "0")
    agents_module.USE_MOCK = False
    calls = {}

    async def fake_completion(**kwargs):
        calls.update(kwargs)

        class Response:
            def __init__(self):
                self.choices = [type("obj", (), {"message": {"content": "hello"}})]
                self.usage = {"prompt_tokens": 5, "completion_tokens": 3, "total_tokens": 8}
                self.response_cost = None
                self.provider = "test-provider"
                self.model = kwargs.get("model")

        return Response()

    monkeypatch.setattr(agents_module, "acompletion", fake_completion)
    monkeypatch.setenv("OPENAI_API_KEY", "test")
    monkeypatch.setattr(
        "model_registry.get_model",
        lambda model_id=None: ModelConfig(
            id="custom-model",
            display_name="Custom Model",
            provider=ModelProvider.OPENAI,
            litellm_model="openai/custom-model",
            tags=[],
            max_context=None,
            recommended=True,
        ),
    )
    messages = [{"role": "user", "content": "hi"}]
    text, usage = asyncio.run(
        agents_module._call_llm(
            messages,
            role="Tester",
            model_id="custom-model",
            debate_id="debate-1",
        )
    )
    assert text == "hello"
    assert usage.total_tokens == 8.0
    assert usage.provider == "test-provider"
    assert calls.get("model") == "openai/custom-model"


def test_billing_model_usage_endpoint(monkeypatch):
    monkeypatch.setenv("USE_MOCK", "1")
    init_db()
    with Session(engine) as session:
        user = User(id=str(uuid.uuid4()), email="usage@example.com", password_hash="x", role="user")
        session.add(user)
        session.commit()
        session.refresh(user)

        usage = BillingUsage(
            user_id=user.id,
            period=_current_period(),
            model_tokens={"router-smart": 1500, "claude-sonnet": 250},
        )
        session.add(usage)
        session.commit()

        payload = get_model_usage(session=session, current_user=user)

    assert payload["items"]
    first_entry = payload["items"][0]
    assert "model_id" in first_entry
    assert first_entry["tokens_used"] > 0
