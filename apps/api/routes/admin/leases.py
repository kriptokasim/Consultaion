"""Admin lease-diagnostics endpoint — PS156 Track L.

Exposes active execution-lease state for all running debates so operators can
inspect owner identity, epoch, heartbeat age, and checkpoint progress without
querying the database directly.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Optional

from auth import get_current_admin
from database import session_scope
from fastapi import APIRouter, Depends
from models import Debate, DebateStageCheckpoint
from sqlalchemy import func
from sqlmodel import select

router = APIRouter()


def _safe_iso(dt: Optional[datetime]) -> Optional[str]:
    if dt is None:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.isoformat()


def _seconds_since(dt: Optional[datetime]) -> Optional[float]:
    if dt is None:
        return None
    now = datetime.now(timezone.utc)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return round((now - dt).total_seconds(), 1)


@router.get("/leases")
def admin_leases(
    _: Any = Depends(get_current_admin),
):
    """Return execution-lease state for all active (non-terminal) debates,
    plus summary counts."""

    with session_scope() as session:
        running = session.exec(
            select(Debate)
            .where(Debate.status.in_(["running", "queued", "scheduled"]))
            .order_by(Debate.updated_at.desc())
        ).all()

        items = []
        for d in running:
            # Latest checkpoint for this debate
            cp = session.exec(
                select(DebateStageCheckpoint)
                .where(DebateStageCheckpoint.debate_id == d.id)
                .order_by(
                    func.coalesce(
                        DebateStageCheckpoint.updated_at,
                        DebateStageCheckpoint.heartbeat_at,
                        DebateStageCheckpoint.completed_at,
                        DebateStageCheckpoint.started_at,
                    ).desc()
                )
            ).first()

            lease_age_s = _seconds_since(d.execution_started_at)
            heartbeat_age_s = _seconds_since(d.last_heartbeat_at)
            lease_remaining_s = None
            if d.lease_expires_at:
                exp = d.lease_expires_at
                if exp.tzinfo is None:
                    exp = exp.replace(tzinfo=timezone.utc)
                lease_remaining_s = round((exp - datetime.now(timezone.utc)).total_seconds(), 1)

            items.append({
                "debate_id": d.id,
                "status": d.status,
                "owner_id": d.runner_id,
                "epoch": d.lease_epoch,
                "run_attempt": d.run_attempt,
                "execution_started_at": _safe_iso(d.execution_started_at),
                "last_heartbeat_at": _safe_iso(d.last_heartbeat_at),
                "lease_expires_at": _safe_iso(d.lease_expires_at),
                "lease_age_s": lease_age_s,
                "heartbeat_age_s": heartbeat_age_s,
                "lease_remaining_s": lease_remaining_s,
                "current_checkpoint": {
                    "stage_key": cp.stage_key,
                    "status": cp.status,
                    "owner_id": cp.owner_id,
                    "attempt": cp.attempt,
                } if cp else None,
            })

        # Summary
        total_running = session.exec(
            select(func.count(Debate.id)).where(Debate.status == "running")
        ).one() or 0
        total_queued = session.exec(
            select(func.count(Debate.id)).where(Debate.status == "queued")
        ).one() or 0

    return {
        "summary": {
            "total_running": total_running,
            "total_queued": total_queued,
            "total_active": total_running + total_queued,
        },
        "debates": items,
    }
