
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from checks import check_db_readiness, check_sse_readiness


def test_check_db_readiness_success(db_session, monkeypatch):
    # check_db_readiness uses 'engine' from 'database' module.
    # conftest 'db_session' fixture ensures 'database.engine' is set to test DB.
    # So we can just call it.
    
    # We need to mock alembic config part because we might not have alembic.ini or migrations in test env
    # OR we assume test DB is migrated by conftest (it is).
    # But check_db_readiness reads "alembic.ini" from CWD.
    # We might need to mock successful migration check if alembic.ini is missing.
    
    with patch("checks.alembic_config.Config") as MockConfig:
        with patch("checks.script.ScriptDirectory.from_config") as MockScriptDir:
             with patch("checks.migration.MigrationContext.configure") as MockContext:
                 # Setup mocks for success
                 mock_script_dir = MockScriptDir.return_value
                 mock_script_dir.get_current_head.return_value = "head_rev"
                 
                 mock_context_instance = MockContext.return_value
                 mock_context_instance.get_current_revision.return_value = "head_rev"
                 
                 ok, details = check_db_readiness()
                 
                 assert ok is True
                 assert details["ping"] is True
                 assert details["revision"]["current"] == "head_rev"

def test_check_db_readiness_failure(monkeypatch):
    # Simulate DB connection failure
    # We can patch engine.connect to raise
    
    with patch("checks.engine.connect", side_effect=Exception("DB Down")):
        ok, details = check_db_readiness()
        assert ok is False
        assert "DB Down" in details["error"]

@pytest.mark.asyncio
async def test_check_sse_readiness_success():
    # uses get_sse_backend()
    # conftest resets backend to Memory
    ok, details = await check_sse_readiness()
    assert ok is True
    assert details["backend"] == "MemoryRateLimiterBackend" or details["backend"] == "MemoryChannelBackend"
    # Actually SSEBackend is likely MemoryChannelBackend.
    # checks.py calls type(backend).__name__

@pytest.mark.asyncio
async def test_check_sse_readiness_failure():
    # Mock get_sse_backend to return a backend whose ping fails
    
    mock_backend = MagicMock()
    mock_backend.ping = AsyncMock(return_value=False)
    
    with patch("checks.get_sse_backend", return_value=mock_backend):
        ok, details = await check_sse_readiness()
        assert ok is False
        assert "failure" in details.get("error", "").lower() or details["error"] == "Backend ping failed"
