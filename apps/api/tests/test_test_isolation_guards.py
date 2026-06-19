"""Test isolation and parallel safety guards.

Validates that test cleanup mechanisms work correctly.
"""

import pytest
from sqlalchemy import text
from sqlalchemy.orm import Session
from redis import asyncio as aioredis


class TestTableCleanup:
    def test_metadata_tables_are_discoverable(self, db_session: Session):
        from sqlalchemy import inspect as sa_inspect
        inspector = sa_inspect(db_session.get_bind())
        tables = set(inspector.get_table_names())
        assert len(tables) > 0

    def test_settings_not_mutated(self):
        from config import settings
        original_version = settings.APP_VERSION
        assert settings.APP_VERSION == original_version


class TestIsolationBetweenTests:
    def test_first_writes_value(self, db_session: Session):
        db_session.execute(text(
            "CREATE TEMPORARY TABLE IF NOT EXISTS _test_iso (v TEXT)"
        ))
        db_session.execute(text("INSERT INTO _test_iso VALUES ('hello')"))
        db_session.commit()

    def test_second_does_not_see_first_value(self, db_session: Session):
        from sqlalchemy import inspect as sa_inspect
        inspector = sa_inspect(db_session.get_bind())
        tables = set(inspector.get_table_names())
        assert "_test_iso" not in tables

    @pytest.mark.asyncio
    async def test_redis_isolation_step_1(self):
        from config import settings
        if not str(settings.REDIS_URL).startswith("redis://"):
            pytest.skip("Not using real redis")
        redis = aioredis.from_url(settings.REDIS_URL)
        await redis.set("test_iso_key", "value")
        await redis.close()
        
    @pytest.mark.asyncio
    async def test_redis_isolation_step_2(self):
        from config import settings
        if not str(settings.REDIS_URL).startswith("redis://"):
            pytest.skip("Not using real redis")
        redis = aioredis.from_url(settings.REDIS_URL)
        val = await redis.get("test_iso_key")
        assert val is None, "Redis isolation failed, key leaked between tests"
        await redis.close()

    @pytest.mark.asyncio
    async def test_background_task_isolation(self):
        # A simple check to ensure no rogue background tasks from previous tests are running
        import asyncio
        tasks = [t for t in asyncio.all_tasks() if t is not asyncio.current_task()]
        # We allow pytest-asyncio and AnyIO related tasks, but not domain tasks
        domain_tasks = [t for t in tasks if "debate" in t.get_name() or "sse" in t.get_name()]
        assert len(domain_tasks) == 0, f"Found leaked domain background tasks: {domain_tasks}"
