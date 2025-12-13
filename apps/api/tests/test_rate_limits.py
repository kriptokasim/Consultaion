import atexit
import importlib
import os
import sys
import tempfile
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace

import pytest
from sqlmodel import Session, select

fd, temp_path = tempfile.mkstemp(prefix="consultaion_rate_limits_", suffix=".db")
os.close(fd)
test_db_path = Path(temp_path)


def _cleanup():
    try:
        test_db_path.unlink()
    except OSError:
        pass


atexit.register(_cleanup)

os.environ["DATABASE_URL"] = f"sqlite:///{test_db_path}"
os.environ.setdefault("JWT_SECRET", "test-secret")
os.environ.setdefault("USE_MOCK", "1")
os.environ.setdefault("RATE_LIMIT_BACKEND", "memory")
os.environ.setdefault("RL_MAX_CALLS", "5")
os.environ.setdefault("RL_WINDOW", "60")
os.environ.setdefault("DEFAULT_MAX_RUNS_PER_HOUR", "5")
os.environ.setdefault("DEFAULT_MAX_TOKENS_PER_DAY", "1000")

sys.path.append(str(Path(__file__).resolve().parents[1]))

import config as config_module  # noqa: E402

config_module.settings.reload()

import ratelimit as ratelimit_module  # noqa: E402
from auth import hash_password  # noqa: E402
from database import engine, init_db  # noqa: E402
from models import UsageCounter, UsageQuota, User  # noqa: E402
from usage_limits import RateLimitError, record_token_usage, reserve_run_slot  # noqa: E402

init_db()


@pytest.fixture(autouse=True)
def ensure_memory_backend(monkeypatch):
    monkeypatch.setenv("RATE_LIMIT_BACKEND", "memory")
    monkeypatch.delenv("REDIS_URL", raising=False)
    import config as config_module  # noqa: WPS433

    config_module.settings.reload()
    importlib.reload(ratelimit_module)
    ratelimit_module.reset_rate_limiter_backend_for_tests()
    yield


@pytest.fixture
def db_session():
    with Session(engine) as session:
        yield session
        session.rollback()


@pytest.fixture
def test_user(db_session):
    user = User(
        id=str(uuid.uuid4()),
        email=f"quota-{uuid.uuid4()}@example.com",
        password_hash=hash_password("password"),
        role="user",
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


def test_increment_ip_bucket_memory_respects_limit():
    ip = "10.0.0.1"
    for _ in range(5):
        allowed, retry_after = ratelimit_module.increment_ip_bucket(ip, 60, 5)
        assert allowed
    allowed, retry_after = ratelimit_module.increment_ip_bucket(ip, 60, 5)
    assert not allowed
    assert retry_after is not None and retry_after > 0


def test_increment_ip_bucket_separate_ips():
    allowed1, _ = ratelimit_module.increment_ip_bucket("10.0.0.2", 60, 2)
    allowed2, _ = ratelimit_module.increment_ip_bucket("10.0.0.3", 60, 2)
    assert allowed1
    assert allowed2


def test_record_429_tracks_recent_events():
    before = len(ratelimit_module.get_recent_429_events())
    ratelimit_module.record_429("10.0.0.9", "/debates")
    events = ratelimit_module.get_recent_429_events()
    assert len(events) == before + 1
    assert events[-1]["ip"] == "10.0.0.9"


def test_reserve_run_slot_and_quota_reset(db_session, test_user):
    quota = UsageQuota(
        user_id=test_user.id,
        period="hour",
        max_runs=2,
        reset_at=datetime.now(timezone.utc) + timedelta(hours=1),
    )
    db_session.add(quota)
    counter = UsageCounter(
        user_id=test_user.id,
        period="hour",
        runs_used=2,
        window_start=datetime.now(timezone.utc) - timedelta(hours=2),
    )
    db_session.add(counter)
    db_session.commit()

    reserve_run_slot(db_session, test_user.id)
    refreshed = db_session.exec(
        select(UsageCounter).where(UsageCounter.user_id == test_user.id, UsageCounter.period == "hour")
    ).first()
    assert refreshed.runs_used == 1


def test_reserve_run_slot_raises_when_limit_hit(db_session, test_user):
    quota = UsageQuota(
        user_id=test_user.id,
        period="hour",
        max_runs=1,
        reset_at=datetime.now(timezone.utc) + timedelta(hours=1),
    )
    db_session.add(quota)
    counter = UsageCounter(
        user_id=test_user.id,
        period="hour",
        runs_used=1,
        window_start=datetime.now(timezone.utc),
    )
    db_session.add(counter)
    db_session.commit()

    with pytest.raises(RateLimitError) as exc:
        reserve_run_slot(db_session, test_user.id)
    assert exc.value.code == "runs_per_hour"


def test_record_token_usage_updates_daily_counter(db_session, test_user):
    record_token_usage(db_session, test_user.id, tokens_used=250, commit=True)
    counter = db_session.exec(
        select(UsageCounter).where(UsageCounter.user_id == test_user.id, UsageCounter.period == "day")
    ).first()
    assert counter.tokens_used == 250


def test_ensure_rate_limiter_ready_memory(monkeypatch):
    monkeypatch.setenv("RATE_LIMIT_BACKEND", "memory")
    monkeypatch.delenv("REDIS_URL", raising=False)
    import config as config_module
    config_module.settings.reload()
    module = importlib.reload(ratelimit_module)
    backend, redis_ok = module.ensure_rate_limiter_ready()
    assert backend == "memory"
    assert redis_ok is None


def test_ensure_rate_limiter_ready_handles_missing_redis(monkeypatch):
    monkeypatch.setenv("RATE_LIMIT_BACKEND", "redis")
    monkeypatch.delenv("REDIS_URL", raising=False)
    import config as config_module
    config_module.settings.reload()
    module = importlib.reload(ratelimit_module)
    backend, redis_ok = module.ensure_rate_limiter_ready()
    assert backend == "redis"
    assert redis_ok is False


def test_redis_backend_tracks_recent_events(monkeypatch):
    class FakeRedisClient:
        def __init__(self):
            self.counters: dict[str, int] = {}
            self.recent: list[str] = []

        def incr(self, key: str):
            self.counters[key] = self.counters.get(key, 0) + 1
            return self.counters[key]

        def expire(self, *_args, **_kwargs):
            return True

        def rpush(self, _key: str, value: str):
            self.recent.append(value)

        def ltrim(self, *_args):
            self.recent = self.recent[-5:]

        def lrange(self, *_args):
            return list(self.recent)

        def ping(self):
            return True

    fake_client = FakeRedisClient()

    class FakeRedisFactory:
        @staticmethod
        def from_url(_url: str):
            return fake_client

    monkeypatch.setenv("RATE_LIMIT_BACKEND", "redis")
    monkeypatch.setenv("REDIS_URL", "redis://test")
    import config as config_module  # noqa: WPS433

    importlib.reload(config_module)
    importlib.reload(ratelimit_module)
    ratelimit_module.redis = SimpleNamespace(Redis=FakeRedisFactory)
    ratelimit_module.reset_rate_limiter_backend_for_tests()

    backend = ratelimit_module.get_rate_limiter_backend()
    allowed1, _ = backend.allow("ip-1", 60, 1)
    assert allowed1
    allowed2, retry_after = backend.allow("ip-1", 60, 1)
    assert not allowed2
    backend.record_429("ip-1", "/debates")
    events = backend.recent_429()
    assert events and events[-1]["path"] == "/debates"
