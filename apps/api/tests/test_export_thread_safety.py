import asyncio
import threading
from types import SimpleNamespace


def test_scores_csv_keeps_orm_and_session_on_request_thread(monkeypatch):
    """Regression: SQLModel Session/attached ORM state must never enter an executor."""
    from routes.debates import streaming

    owner_thread = threading.get_ident()

    class ThreadBoundScore:
        def _check(self):
            assert threading.get_ident() == owner_thread

        @property
        def persona(self):
            self._check()
            return "A"

        @property
        def judge(self):
            self._check()
            return "Judge"

        @property
        def score(self):
            self._check()
            return 9.0

        @property
        def rationale(self):
            self._check()
            return "Good"

        @property
        def created_at(self):
            self._check()
            return None

    score = ThreadBoundScore()

    class Result:
        def all(self):
            assert threading.get_ident() == owner_thread
            return [score]

    class ThreadBoundSession:
        def get(self, _model, _id):
            assert threading.get_ident() == owner_thread
            return SimpleNamespace(id=_id)

        def exec(self, _statement):
            assert threading.get_ident() == owner_thread
            return Result()

        def commit(self):
            assert threading.get_ident() == owner_thread

    session = ThreadBoundSession()
    user = SimpleNamespace(id="user-1")

    monkeypatch.setattr(
        streaming,
        "require_debate_access",
        lambda debate, _user, _session: debate,
    )

    import audit
    import billing.service
    import services.reporting
    import usage_limits

    monkeypatch.setattr(
        billing.service,
        "check_export_quota",
        lambda _session, _user_id: threading.get_ident() == owner_thread or (_ for _ in ()).throw(AssertionError()),
    )
    monkeypatch.setattr(
        billing.service,
        "increment_export_usage",
        lambda _session, _user_id: threading.get_ident() == owner_thread or (_ for _ in ()).throw(AssertionError()),
    )
    monkeypatch.setattr(
        usage_limits,
        "increment_export_usage_daily",
        lambda _session, _user_id: threading.get_ident() == owner_thread or (_ for _ in ()).throw(AssertionError()),
    )

    def generate_csv_content(scores):
        assert threading.get_ident() == owner_thread
        # Access attributes to emulate the real serializer and catch ORM thread drift.
        assert scores[0].persona == "A"
        assert scores[0].judge == "Judge"
        assert scores[0].score == 9.0
        return "persona,judge,score\nA,Judge,9.0\n"

    monkeypatch.setattr(services.reporting, "generate_csv_content", generate_csv_content)

    def record_audit(*_args, **kwargs):
        assert threading.get_ident() == owner_thread
        assert kwargs["session"] is session

    monkeypatch.setattr(audit, "record_audit", record_audit)

    response = asyncio.run(
        streaming.export_scores_csv(
            debate_id="debate-1",
            session=session,
            current_user=user,
        )
    )

    assert response.status_code == 200
    assert b"A,Judge,9.0" in response.body
