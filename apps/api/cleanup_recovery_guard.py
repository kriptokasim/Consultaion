"""Production-safe stale debate recovery.

The legacy cleanup loop had three execution-contract violations:

* an expired running lease was changed to ``queued`` without dispatching any
  worker, creating a dead-end that later timed out;
* ``run_attempt`` (the logical product-attempt identity) was incorrectly used
  as a crash-retry counter;
* partially populated stale runs were written with the non-canonical Debate
  status ``degraded``.

This module replaces only ``cleanup_stale_debates`` at runtime. Recovery is
bounded per logical attempt using metadata, preserves the same run_attempt,
clears stale ownership, and performs a real redispatch. A live, unexpired lease
is never cleaned up merely because a stage checkpoint is old.
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from typing import Any

from database import session_scope
from models import (
    Debate,
    DebateAttempt,
    DebateCheckpoint,
    DebateContinuation,
    DebateError,
    DebateStageCheckpoint,
    Message,
    Score,
    Vote,
)
from sqlmodel import select

from config import settings

logger = logging.getLogger(__name__)

_MAX_RECOVERY_DISPATCHES = 3
_ACTIVE_CONTINUATION_STATUSES = ("preflight_passed", "dispatched", "running")

_installed = False


def _utc(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    return value if value.tzinfo is not None else value.replace(tzinfo=timezone.utc)


def _active_continuation(session, debate_id: str) -> DebateContinuation | None:
    return session.exec(
        select(DebateContinuation)
        .where(DebateContinuation.debate_id == debate_id)
        .where(DebateContinuation.status.in_(_ACTIVE_CONTINUATION_STATUSES))
        .order_by(DebateContinuation.updated_at.desc())
    ).first()


def _current_attempt(session, debate: Debate) -> DebateAttempt | None:
    attempt_number = max(int(debate.run_attempt or 0), 1)
    return session.exec(
        select(DebateAttempt).where(
            DebateAttempt.debate_id == debate.id,
            DebateAttempt.attempt_number == attempt_number,
        )
    ).first()


def _has_persisted_output(session, debate_id: str) -> bool:
    debate = session.get(Debate, debate_id)
    if debate and debate.final_content:
        return True
    for model in (Message, Score, Vote):
        if session.exec(select(model).where(model.debate_id == debate_id).limit(1)).first():
            return True
    return False


def _recovery_meta(debate: Debate) -> tuple[dict[str, Any], dict[str, Any]]:
    final_meta = dict(debate.final_meta or {})
    recovery = dict(final_meta.get("recovery_dispatch") or {})
    attempt_number = max(int(debate.run_attempt or 0), 1)
    if int(recovery.get("attempt_number", -1) or -1) != attempt_number:
        recovery = {"attempt_number": attempt_number, "count": 0}
    return final_meta, recovery


def _is_live_owner(debate: Debate, now: datetime) -> bool:
    expiry = _utc(debate.lease_expires_at)
    return bool(debate.runner_id and expiry and expiry > now)


def _last_running_activity(session, debate: Debate) -> datetime:
    candidates: list[datetime] = []
    for value in (debate.last_heartbeat_at, debate.updated_at, debate.execution_started_at):
        normalized = _utc(value)
        if normalized is not None:
            candidates.append(normalized)

    checkpoint = session.exec(
        select(DebateCheckpoint)
        .where(DebateCheckpoint.debate_id == debate.id)
        .order_by(DebateCheckpoint.last_checkpoint_at.desc())
    ).first()
    if checkpoint:
        normalized = _utc(checkpoint.last_checkpoint_at)
        if normalized is not None:
            candidates.append(normalized)

    if candidates:
        return max(candidates)
    return _utc(debate.created_at) or datetime.now(timezone.utc)


def _classify_candidate(session, debate: Debate, now: datetime) -> tuple[str, int] | None:
    """Return (reason, age_seconds) only when cleanup may take ownership."""
    queued_cutoff = now - timedelta(seconds=settings.DEBATE_STALE_QUEUED_SECONDS)
    running_cutoff = now - timedelta(seconds=settings.DEBATE_STALE_RUNNING_SECONDS)

    if debate.status == "queued":
        # Queued is intentionally stable when autorun is disabled; users may
        # start those runs manually later.
        if settings.DISABLE_AUTORUN:
            return None
        created = _utc(debate.created_at) or now
        if created < queued_cutoff:
            return "queued_timeout", int((now - created).total_seconds())
        return None

    if debate.status == "scheduled":
        updated = _utc(debate.updated_at) or _utc(debate.created_at) or now
        if updated < queued_cutoff:
            return "scheduled_dispatch_stale", int((now - updated).total_seconds())
        return None

    if debate.status != "running":
        return None

    # A live lease is the ownership authority. Stage checkpoints can remain
    # unchanged throughout a legitimately long provider call.
    if _is_live_owner(debate, now):
        return None

    expiry = _utc(debate.lease_expires_at)
    if expiry is not None and expiry <= now:
        return "lease_expired", int((now - expiry).total_seconds())

    last_activity = _last_running_activity(session, debate)
    if last_activity < running_cutoff:
        return "running_without_live_lease", int((now - last_activity).total_seconds())
    return None


def _mark_terminal_failure(
    session,
    debate: Debate,
    *,
    now: datetime,
    reason: str,
    age_seconds: int,
    recovery_count: int,
) -> tuple[bool, bool]:
    """Terminalize an exhausted/unrecoverable run.

    Returns ``(never_executed_current_attempt, has_partial_output)`` for quota
    compensation and observability.
    """
    from billing.service import get_or_create_usage, refund_hosted_credit

    attempt = _current_attempt(session, debate)
    never_executed_current_attempt = bool(attempt and attempt.status == "queued")
    has_partial_output = _has_persisted_output(session, debate.id)
    continuation = _active_continuation(session, debate.id)

    failure_code = (
        "run_dispatch_timeout"
        if reason in {"queued_timeout", "scheduled_dispatch_stale"}
        else "recovery_dispatches_exhausted"
    )

    final_meta, recovery = _recovery_meta(debate)
    recovery.update(
        {
            "count": recovery_count,
            "terminal": True,
            "terminal_reason": reason,
            "failed_at": now.isoformat(),
        }
    )
    final_meta["recovery_dispatch"] = recovery
    final_meta["stale_cleanup"] = {
        "reason": reason,
        "failure_code": failure_code,
        "age_seconds": age_seconds,
        "cleaned_at": now.isoformat(),
        "partial_output_available": has_partial_output,
    }

    debate.status = "failed"
    debate.updated_at = now
    debate.final_meta = final_meta
    debate.runner_id = None
    debate.execution_owner_id = None
    debate.lease_expires_at = None
    session.add(debate)

    if attempt is not None and attempt.status not in {"completed", "failed", "cancelled"}:
        attempt.status = "failed"
        attempt.completed_at = now
        attempt.error_summary = failure_code
        session.add(attempt)

    legacy_checkpoint = session.exec(
        select(DebateCheckpoint)
        .where(DebateCheckpoint.debate_id == debate.id)
        .order_by(DebateCheckpoint.last_checkpoint_at.desc())
    ).first()
    if legacy_checkpoint is not None:
        legacy_checkpoint.status = "failed"
        session.add(legacy_checkpoint)

    for stage in session.exec(
        select(DebateStageCheckpoint)
        .where(DebateStageCheckpoint.debate_id == debate.id)
        .where(DebateStageCheckpoint.status == "running")
    ).all():
        stage.status = "failed"
        stage.failed_at = now
        stage.error_code = failure_code
        stage.error_message = "Execution recovery was exhausted."
        stage.updated_at = now
        session.add(stage)

    if continuation is not None:
        continuation.status = "failed"
        continuation.failed_at = now
        continuation.updated_at = now
        continuation.failure_code = failure_code
        continuation.failure_detail_safe = "Execution recovery was exhausted."
        session.add(continuation)

    session.add(
        DebateError(
            debate_id=debate.id,
            user_id=debate.user_id,
            status="failed",
            error_summary=f"stale_debate_timeout: {reason}",
            participant_errors={
                "reason": reason,
                "failure_code": failure_code,
                "age_seconds": age_seconds,
                "partial_output_available": has_partial_output,
            },
        )
    )

    reservation_id = (
        continuation.credit_reservation_id
        if continuation is not None and continuation.credit_reservation_id
        else debate.credit_reservation_id
    )
    if debate.user_id and reservation_id:
        refund_hosted_credit(
            session,
            debate.user_id,
            reservation_id=reservation_id,
            debate_id=debate.id,
        )

    # Only the initial never-executed attempt consumed monthly debate usage.
    # Full retries intentionally do not increment this counter.
    if (
        debate.user_id
        and never_executed_current_attempt
        and max(int(debate.run_attempt or 0), 1) == 1
    ):
        usage = get_or_create_usage(session, debate.user_id)
        usage.debates_created = max(0, int(usage.debates_created or 0) - 1)
        session.add(usage)

    return never_executed_current_attempt, has_partial_output


def _prepare_recovery(debate_id: str, reason: str, age_seconds: int, now: datetime):
    """Atomically claim one bounded recovery dispatch or terminalize it."""
    with session_scope() as session:
        debate = session.exec(
            select(Debate).where(Debate.id == debate_id).with_for_update()
        ).first()
        if debate is None:
            return None

        candidate = _classify_candidate(session, debate, now)
        if candidate is None:
            return None
        current_reason, current_age = candidate
        reason = current_reason
        age_seconds = current_age

        final_meta, recovery = _recovery_meta(debate)
        recovery_count = int(recovery.get("count", 0) or 0)

        # A stale queued initial request means the original dispatch never took
        # ownership. It is safe to fail/compensate directly rather than invent
        # a hidden recovery after the user has already waited the full queue TTL.
        if reason == "queued_timeout":
            never_executed, partial = _mark_terminal_failure(
                session,
                debate,
                now=now,
                reason=reason,
                age_seconds=age_seconds,
                recovery_count=recovery_count,
            )
            session.commit()
            return {
                "action": "failed",
                "debate_id": debate.id,
                "reason": reason,
                "failure_code": "run_dispatch_timeout",
                "refund_run_slot": never_executed,
                "partial_output_available": partial,
            }

        if recovery_count >= _MAX_RECOVERY_DISPATCHES:
            never_executed, partial = _mark_terminal_failure(
                session,
                debate,
                now=now,
                reason=reason,
                age_seconds=age_seconds,
                recovery_count=recovery_count,
            )
            session.commit()
            return {
                "action": "failed",
                "debate_id": debate.id,
                "reason": reason,
                "failure_code": "recovery_dispatches_exhausted",
                "refund_run_slot": never_executed,
                "partial_output_available": partial,
            }

        continuation = _active_continuation(session, debate.id)
        attempt_number = max(int(debate.run_attempt or 0), 1)
        recovery_count += 1
        recovery.update(
            {
                "attempt_number": attempt_number,
                "count": recovery_count,
                "last_reason": reason,
                "last_dispatch_at": now.isoformat(),
            }
        )
        final_meta["recovery_dispatch"] = recovery

        # Clear the expired owner before redispatch. The new worker increments
        # lease_epoch atomically when it acquires the same logical attempt.
        debate.status = "scheduled"
        debate.runner_id = None
        debate.execution_owner_id = None
        debate.lease_expires_at = None
        debate.last_heartbeat_at = None
        debate.updated_at = now
        debate.final_meta = final_meta
        session.add(debate)
        session.commit()

        return {
            "action": "dispatch",
            "debate_id": debate.id,
            "prompt": debate.prompt,
            "channel_id": f"debate:{debate.id}",
            "config": debate.config or {},
            "model_id": debate.model_id,
            "continuation_id": continuation.id if continuation else None,
            # Attempt >1 is a user-requested full retry. A continuation also
            # resumes the synthesis side of staged execution. Initial-attempt
            # crash recovery must keep resume=False so STAGED_DECISION_PIPELINE
            # still pauses at perspectives_ready after recovering perspectives.
            "resume": bool(continuation is not None or attempt_number > 1),
            "recovery_count": recovery_count,
            "reason": reason,
        }


async def cleanup_stale_debates_hardened() -> tuple[int, int]:
    """Recover stale ownership safely; terminalize only bounded failures.

    Return shape remains compatible with the legacy cleanup loop:
    ``(failed_count, degraded_count)``. Canonical Debate rows never use a
    ``degraded`` status, so the second value is always zero.
    """
    from debate_dispatch import dispatch_debate_run
    from sse_backend import get_sse_backend

    now = datetime.now(timezone.utc)
    candidate_ids: list[tuple[str, str, int]] = []

    with session_scope() as session:
        for debate in session.exec(
            select(Debate).where(Debate.status.in_(["queued", "scheduled", "running"]))
        ).all():
            candidate = _classify_candidate(session, debate, now)
            if candidate is not None:
                candidate_ids.append((debate.id, candidate[0], candidate[1]))

    if not candidate_ids:
        return 0, 0

    failed_count = 0
    backend = get_sse_backend()

    for debate_id, reason, age_seconds in candidate_ids:
        prepared = _prepare_recovery(debate_id, reason, age_seconds, now)
        if prepared is None:
            continue

        if prepared["action"] == "dispatch":
            try:
                await dispatch_debate_run(
                    prepared["debate_id"],
                    prepared["prompt"],
                    prepared["channel_id"],
                    prepared["config"],
                    prepared["model_id"],
                    trace_id=None,
                    resume=prepared["resume"],
                    continuation_id=prepared["continuation_id"],
                )
                logger.warning(
                    "debate.recovery_dispatched debate_id=%s reason=%s count=%s resume=%s continuation_id=%s",
                    debate_id,
                    prepared["reason"],
                    prepared["recovery_count"],
                    prepared["resume"],
                    prepared["continuation_id"],
                )
            except Exception as exc:
                # Keep ``scheduled`` and the incremented bounded recovery count.
                # The next cleanup cycle may retry; after the limit the run is
                # terminalized and compensated.
                logger.exception(
                    "debate.recovery_dispatch_failed debate_id=%s count=%s error=%s",
                    debate_id,
                    prepared["recovery_count"],
                    exc,
                )
            continue

        failed_count += 1
        if prepared.get("refund_run_slot"):
            try:
                from usage_limits import refund_run_slot

                with session_scope() as session:
                    debate = session.get(Debate, debate_id)
                    if debate is not None:
                        refund_run_slot(session, debate.user_id)
            except Exception:
                logger.exception("Run-slot compensation failed for stale debate %s", debate_id)

        try:
            await backend.publish(
                f"debate:{debate_id}",
                {
                    "type": "debate_failed",
                    "debate_id": debate_id,
                    "status": "failed",
                    "reason": "stale_timeout",
                    "failure_code": prepared["failure_code"],
                    "stale_reason": prepared["reason"],
                    "partial_output_available": prepared.get(
                        "partial_output_available", False
                    ),
                },
            )
        except Exception:
            logger.exception("Failed to publish stale terminal event for %s", debate_id)

    return failed_count, 0


def install_cleanup_recovery_guard() -> None:
    """Replace the legacy stale cleanup implementation once."""
    global _installed
    if _installed:
        return

    import orchestrator_cleanup

    orchestrator_cleanup.cleanup_stale_debates = cleanup_stale_debates_hardened
    _installed = True
