from __future__ import annotations

import logging
from typing import Any, Optional

from sqlmodel import Session, select
from sqlalchemy import func

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
        "_checkpoint_query_failed": False,
        "_continuation_query_failed": False,
        "_message_query_failed": False,
        "_score_query_failed": False,
    }

    if capabilities.has_stage_checkpoint_table:
        ck_result = _safe_query_checkpoints(debate_id, session)
        if not ck_result and capabilities.has_stage_checkpoint_table:
            pass  # Table exists but no rows — valid empty result
        extra.update(ck_result)
    else:
        extra["_checkpoint_query_failed"] = True

    if capabilities.has_continuation_table:
        cont_result = _safe_query_continuation(debate_id, session)
        extra.update(cont_result)
    else:
        extra["_continuation_query_failed"] = True

    if capabilities.has_message_table and capabilities.has_score_table:
        extra.update(_safe_query_counts(debate_id, session, capabilities))
    elif capabilities.has_message_table:
        extra.update(_safe_query_message_count(debate_id, session))
    else:
        extra["_message_query_failed"] = True

    if capabilities.has_score_table:
        extra.update(_safe_query_score_count(debate_id, session))
    else:
        extra["_score_query_failed"] = True

    return extra


def _safe_query_checkpoints(debate_id: str, session: Session) -> dict[str, Any]:
    try:
        from models import DebateStageCheckpoint

        with session.begin_nested():
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
        return {"_checkpoint_query_failed": True}
    return {}


def _safe_query_continuation(debate_id: str, session: Session) -> dict[str, Any]:
    try:
        from models import DebateContinuation

        with session.begin_nested():
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
        return {"_continuation_query_failed": True}
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
        from sqlalchemy import func, select as sa_select

        with session.begin_nested():
            stmt = sa_select(func.count()).where(Message.debate_id == debate_id)
            count = session.execute(stmt).scalar() or 0
        return {"responses_received": count}
    except Exception as exc:
        logger.warning("message_count_query_failed debate_id=%s error=%s", debate_id, exc)
        return {"_message_query_failed": True}
    return {}


def _safe_query_score_count(debate_id: str, session: Session) -> dict[str, Any]:
    try:
        from models import Score
        from sqlalchemy import func, select as sa_select

        with session.begin_nested():
            stmt = sa_select(func.count()).where(Score.debate_id == debate_id)
            count = session.execute(stmt).scalar() or 0
        return {"scores_received": count}
    except Exception as exc:
        logger.warning("score_count_query_failed debate_id=%s error=%s", debate_id, exc)
        return {"_score_query_failed": True}
    return {}
