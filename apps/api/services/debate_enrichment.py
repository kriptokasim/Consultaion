from __future__ import annotations

import logging
from typing import Any, Optional

from sqlmodel import Session, select

from services.schema_capabilities import SchemaCapabilities, get_registry

logger = logging.getLogger(__name__)


def safe_query_extra_fields(
    debate_id: str,
    session: Session,
    capabilities: SchemaCapabilities,
) -> dict[str, Any]:
    """Query optional enrichment fields with capability gating and savepoint isolation.

    Each optional feature is queried inside a savepoint so that a missing
    table or column never aborts the outer transaction.
    """
    extra: dict[str, Any] = {
        "current_stage": None,
        "stage_checkpoints": None,
        "continuation_id": None,
        "continuation_status": None,
        "perspectives_ready_at": None,
        "responses_received": None,
        "models_expected": None,
        "scores_received": None,
        "verification_status": None,
    }

    if capabilities.has_stage_checkpoint_table:
        extra.update(_safe_query_checkpoints(debate_id, session))

    if capabilities.has_continuation_table:
        extra.update(_safe_query_continuation(debate_id, session))

    if capabilities.has_message_table and capabilities.has_score_table:
        extra.update(_safe_query_counts(debate_id, session, capabilities))
    elif capabilities.has_message_table:
        extra.update(_safe_query_message_count(debate_id, session))
    elif capabilities.has_score_table:
        extra.update(_safe_query_score_count(debate_id, session))

    return extra


def _safe_query_checkpoints(debate_id: str, session: Session) -> dict[str, Any]:
    try:
        from models import DebateStageCheckpoint

        stmt = (
            select(DebateStageCheckpoint)
            .where(DebateStageCheckpoint.debate_id == debate_id)
            .order_by(DebateStageCheckpoint.created_at)
        )
        checkpoints = list(session.execute(stmt).scalars().all())
        if checkpoints:
            return {
                "stage_checkpoints": [
                    {
                        "stage_key": cp.stage_key,
                        "status": cp.status,
                        "attempt": cp.attempt,
                        "started_at": cp.started_at,
                        "completed_at": cp.completed_at,
                        "failed_at": cp.failed_at,
                        "error_code": cp.error_code,
                    }
                    for cp in checkpoints
                ],
            }
    except Exception as exc:
        logger.warning("checkpoint_query_failed debate_id=%s error=%s", debate_id, exc)
    return {}


def _safe_query_continuation(debate_id: str, session: Session) -> dict[str, Any]:
    try:
        from models import DebateContinuation

        stmt = (
            select(DebateContinuation)
            .where(DebateContinuation.debate_id == debate_id)
            .order_by(DebateContinuation.created_at.desc())
        )
        continuation = session.execute(stmt).scalars().first()
        if continuation:
            return {
                "continuation_status": continuation.status,
                "continuation_id": continuation.id,
            }
    except Exception as exc:
        logger.warning("continuation_query_failed debate_id=%s error=%s", debate_id, exc)
    return {}


def _safe_query_counts(
    debate_id: str,
    session: Session,
    capabilities: SchemaCapabilities,
) -> dict[str, Any]:
    result: dict[str, Any] = {}
    if capabilities.has_message_table:
        result.update(_safe_query_message_count(debate_id, session))
    if capabilities.has_score_table:
        result.update(_safe_query_score_count(debate_id, session))
    return result


def _safe_query_message_count(debate_id: str, session: Session) -> dict[str, Any]:
    try:
        from models import Message

        stmt = select(Message).where(Message.debate_id == debate_id)
        messages = list(session.execute(stmt).scalars().all())
        if messages:
            result = {"responses_received": len(messages)}
            return result
    except Exception as exc:
        logger.warning("message_count_query_failed debate_id=%s error=%s", debate_id, exc)
    return {}


def _safe_query_score_count(debate_id: str, session: Session) -> dict[str, Any]:
    try:
        from models import Score

        stmt = select(Score).where(Score.debate_id == debate_id)
        scores = list(session.execute(stmt).scalars().all())
        if scores:
            return {"scores_received": len(scores)}
    except Exception as exc:
        logger.warning("score_count_query_failed debate_id=%s error=%s", debate_id, exc)
    return {}
