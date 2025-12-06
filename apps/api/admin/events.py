from typing import Any, Optional

from models import AdminEvent
from sqlmodel import Session


def record_admin_event(
    session: Session,
    level: str,
    message: str,
    trace_id: Optional[str] = None,
    debate_id: Optional[str] = None,
    meta: Optional[dict[str, Any]] = None
) -> AdminEvent:
    """
    Record an admin event (error, warning, info).
    """
    event = AdminEvent(
        level=level,
        message=message,
        trace_id=trace_id,
        debate_id=debate_id,
        meta=meta
    )
    session.add(event)
    session.commit()
    session.refresh(event)
    return event
