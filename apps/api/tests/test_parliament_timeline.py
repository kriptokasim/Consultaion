import atexit
import os
import tempfile
from pathlib import Path
from datetime import datetime, timezone

from sqlmodel import Session

from database import engine, init_db
from models import Debate, Message
from parliament.timeline import build_debate_timeline
from schemas import default_panel_config
import uuid

fd, temp_path = tempfile.mkstemp(prefix="consultaion_timeline_", suffix=".db")
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
os.environ.setdefault("FAST_DEBATE", "1")

import importlib
import config as config_module
importlib.reload(config_module)
from database import reset_engine as _reset_engine  # noqa: E402

_reset_engine()
init_db()


def test_build_timeline_basic():
    panel = default_panel_config()
    debate_id = f"timeline-basic-{uuid.uuid4().hex[:6]}"
    with Session(engine) as session:
        debate = Debate(
            id=debate_id,
            prompt="Timeline prompt",
            status="completed",
            panel_config=panel.model_dump(),
            engine_version=panel.engine_version,
        )
        session.add(debate)
        session.commit()
        for idx, seat in enumerate(panel.seats):
            session.add(
                Message(
                    debate_id=debate_id,
                    round_index=idx,
                    role="seat",
                    persona=seat.display_name,
                    content=f"content {idx}",
                    meta={
                        "seat_id": seat.seat_id,
                        "role_profile": seat.role_profile,
                        "provider": seat.provider_key,
                        "model": seat.model,
                        "round_index": idx,
                        "phase": "explore",
                        "stance": "support",
                    },
                    created_at=datetime.now(timezone.utc),
                )
            )
        session.commit()

    with Session(engine) as session:
        debate = session.get(Debate, debate_id)
        events = build_debate_timeline(session, debate)
        assert len(events) == len(panel.seats)
        assert events[0].event_type == "seat_message"
        assert events[0].seat_id == panel.seats[0].seat_id
        assert events[0].phase == "explore"


def test_build_timeline_includes_failure_notice():
    panel = default_panel_config()
    debate_id = f"timeline-failure-{uuid.uuid4().hex[:6]}"
    with Session(engine) as session:
        debate = Debate(
            id=debate_id,
            prompt="Timeline failure",
            status="failed",
            final_meta={"failure": {"reason": "seat_failure_threshold_exceeded"}},
            panel_config=panel.model_dump(),
            engine_version=panel.engine_version,
        )
        session.add(debate)
        session.commit()

    with Session(engine) as session:
        debate = session.get(Debate, debate_id)
        events = build_debate_timeline(session, debate)
        assert any(evt.event_type == "system_notice" for evt in events)
