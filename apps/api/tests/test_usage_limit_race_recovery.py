from contextlib import nullcontext
from unittest.mock import MagicMock

from models import UsageCounter, UsageQuota
from sqlalchemy.exc import IntegrityError
from usage_limits import _get_or_create_quota, _get_or_reset_counter


class _Result:
    def __init__(self, value):
        self.value = value

    def first(self):
        return self.value


def _integrity_error() -> IntegrityError:
    return IntegrityError("insert", {}, Exception("duplicate key"))


def test_quota_creation_recovers_from_unique_race():
    winner = UsageQuota(user_id="u1", period="hour", max_runs=5)
    session = MagicMock()
    session.exec.side_effect = [_Result(None), _Result(winner)]
    session.begin_nested.return_value = nullcontext()
    session.flush.side_effect = _integrity_error()

    assert _get_or_create_quota(session, "u1", "hour") is winner


def test_counter_creation_recovers_from_unique_race():
    winner = UsageCounter(user_id="u1", period="hour", runs_used=1)
    session = MagicMock()
    session.exec.side_effect = [_Result(None), _Result(winner)]
    session.begin_nested.return_value = nullcontext()
    session.flush.side_effect = _integrity_error()

    assert _get_or_reset_counter(session, "u1", "hour") is winner
