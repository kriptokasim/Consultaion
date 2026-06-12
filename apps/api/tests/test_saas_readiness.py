import pytest
from unittest.mock import patch, AsyncMock
from httpx import ASGITransport, AsyncClient
from sqlmodel import Session, select

from main import app
from models import User, UserProviderKey, UserInteraction, utcnow

pytestmark = pytest.mark.anyio


@pytest.fixture
async def client():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as test_client:
        yield test_client


async def _register_and_login(client: AsyncClient, email: str, password: str) -> None:
    await client.post("/auth/register", json={"email": email, "password": password})
    res = await client.post("/auth/login", json={"email": email, "password": password})
    assert res.status_code == 200


async def test_provider_keys_crud_flow(client: AsyncClient):
    # Register and login a test user
    email = "byok-user@example.com"
    await _register_and_login(client, email, "Password123!")

    # 1. Initially user should have no provider keys configured
    res = await client.get("/provider-keys")
    assert res.status_code == 200
    assert len(res.json()) == 0

    # 2. Add a new OpenAI provider key with mock validation success
    with patch("routes.provider_keys.validate_key_with_provider", new_callable=AsyncMock) as mock_validate:
        mock_validate.return_value = True
        
        payload = {
            "provider": "openai",
            "key": "sk-1234567890abcdefghijklmnopqrstuvwxyz"
        }
        res = await client.post("/provider-keys", json=payload, headers={"X-CSRF-Token": client.cookies.get("csrf_token", "")})
        assert res.status_code == 200
        data = res.json()
        assert data["provider"] == "openai"
        assert "masked_key" in data
        assert data["masked_key"] == "sk-...wxyz"
        mock_validate.assert_called_once_with("openai", "sk-1234567890abcdefghijklmnopqrstuvwxyz")

    # 3. List keys again to ensure it exists
    res = await client.get("/provider-keys")
    assert res.status_code == 200
    keys = res.json()
    assert len(keys) == 1
    assert keys[0]["provider"] == "openai"
    assert keys[0]["masked_key"] == "sk-...wxyz"

    # 4. Try validating only (without saving)
    with patch("routes.provider_keys.validate_key_with_provider", new_callable=AsyncMock) as mock_validate:
        mock_validate.return_value = True
        
        validate_payload = {
            "provider": "openai",
            "key": "sk-newkeytest123"
        }
        res = await client.post("/provider-keys/validate", json=validate_payload, headers={"X-CSRF-Token": client.cookies.get("csrf_token", "")})
        assert res.status_code == 200
        assert res.json()["valid"] is True

    # 5. Delete the provider key
    res = await client.delete("/provider-keys/openai", headers={"X-CSRF-Token": client.cookies.get("csrf_token", "")})
    assert res.status_code == 200
    assert res.json() == {"provider": "openai", "deleted": True}

    # 6. Verify keys list is empty again
    res = await client.get("/provider-keys")
    assert res.status_code == 200
    assert len(res.json()) == 0


async def test_audit_logs_and_exports(client: AsyncClient, db_session: Session):
    # Register and login a test user
    email = "audit-user@example.com"
    await _register_and_login(client, email, "Password123!")

    # Find the newly created user in db to insert test audit logs manually
    user = db_session.exec(select(User).where(User.email == email)).first()
    assert user is not None
    
    # Add a couple of mock interactions
    log1 = UserInteraction(
        user_id=user.id,
        interaction_type="run_created",
        debate_id="debate-uuid-1",
        details={"prompt": "Test Prompt 1"},
        created_at=utcnow()
    )
    log2 = UserInteraction(
        user_id=user.id,
        interaction_type="key_added",
        debate_id=None,
        details={"provider": "anthropic"},
        created_at=utcnow()
    )
    db_session.add(log1)
    db_session.add(log2)
    db_session.commit()

    # 1. Fetch audit logs from GET /audit-logs
    res = await client.get("/audit-logs")
    assert res.status_code == 200
    logs = res.json()
    assert len(logs) == 2
    
    # Assert logs are ordered desc by created_at (log2 is newest/most recently created)
    types = [log["interaction_type"] for log in logs]
    assert "run_created" in types
    assert "key_added" in types

    # 2. Export CSV
    res = await client.get("/audit-logs/export/csv")
    assert res.status_code == 200
    assert res.headers["content-type"].startswith("text/csv")
    assert "attachment; filename=" in res.headers["content-disposition"]
    csv_content = res.text
    assert "ID,Timestamp,Event Type,Debate ID,Details JSON" in csv_content
    assert "run_created" in csv_content
    assert "key_added" in csv_content

    # 3. Export JSON
    res = await client.get("/audit-logs/export/json")
    assert res.status_code == 200
    assert res.headers["content-type"].startswith("application/json")
    assert "attachment; filename=" in res.headers["content-disposition"]
    json_data = res.json()
    assert len(json_data) == 2
    assert json_data[0]["interaction_type"] in ["run_created", "key_added"]
