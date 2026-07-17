import asyncio
import hashlib
import json
import logging
import random
from datetime import datetime, timezone
from typing import Any, Callable, Dict, Optional

from database_async import async_session_scope
from models import Debate, DebateStageCheckpoint
from sqlmodel import select

logger = logging.getLogger(__name__)


class LeaseOwnershipLost(RuntimeError):
    """Raised when a worker no longer owns the debate execution lease."""


async def _assert_lease_owner(
    session,
    debate_id: str,
    owner_id: Optional[str],
    lease_epoch: Optional[int],
) -> None:
    """Lock and verify the debate lease for the surrounding transaction."""
    if owner_id is None and lease_epoch is None:
        return
    if not owner_id or lease_epoch is None:
        raise ValueError("owner_id and lease_epoch must be provided together")

    stmt = (
        select(Debate)
        .where(Debate.id == debate_id)
        .where(Debate.execution_owner_id == owner_id)
        .where(Debate.lease_epoch == lease_epoch)
        .with_for_update()
        .execution_options(populate_existing=True)
    )
    result = await session.execute(stmt)
    if result.scalars().first() is None:
        raise LeaseOwnershipLost(
            f"Debate {debate_id}: execution lease is no longer owned by "
            f"{owner_id} at epoch {lease_epoch}."
        )


async def run_with_checkpoint(
    debate_id: str,
    stage_key: str,
    input_data: Dict[str, Any],
    run_fn: Callable[[], Any],
    load_fn: Callable[[Any], Any],
    owner_id: Optional[str] = None,
    lease_epoch: Optional[int] = None,
) -> Any:
    """
    Execute a pipeline stage inside an owner-fenced checkpoint lifecycle.

    Orchestrated runs must provide both owner_id and lease_epoch. Legacy callers
    may omit both values, but partial fencing identities are rejected.
    """
    serialized = json.dumps(input_data, sort_keys=True, default=str)
    input_hash = hashlib.sha256(serialized.encode("utf-8")).hexdigest()

    async with async_session_scope() as session:
        await _assert_lease_owner(session, debate_id, owner_id, lease_epoch)

        stmt = (
            select(DebateStageCheckpoint)
            .where(DebateStageCheckpoint.debate_id == debate_id)
            .where(DebateStageCheckpoint.stage_key == stage_key)
        )
        res = await session.execute(stmt)
        checkpoint = res.scalars().first()

        if checkpoint:
            if checkpoint.status == "completed" and checkpoint.input_hash == input_hash:
                logger.info(
                    "Debate %s: stage %s already completed with matching hash. Skipping.",
                    debate_id,
                    stage_key,
                )
                return await load_fn(session)

            owned_by_superseded_worker = (
                checkpoint.status == "running"
                and owner_id is not None
                and checkpoint.owner_id != owner_id
            )
            if owned_by_superseded_worker:
                logger.warning(
                    "Debate %s: taking over stage %s from superseded owner %s.",
                    debate_id,
                    stage_key,
                    checkpoint.owner_id,
                )
            elif checkpoint.status == "running":
                logger.warning(
                    "Debate %s: stage %s is currently marked as running. Waiting...",
                    debate_id,
                    stage_key,
                )
                for attempt in range(5):
                    delay = min(8.0, (2 ** attempt) + random.uniform(0.1, 0.5))
                    await asyncio.sleep(delay)
                    await _assert_lease_owner(
                        session, debate_id, owner_id, lease_epoch
                    )
                    stmt_retry = stmt.execution_options(populate_existing=True)
                    res_retry = await session.execute(stmt_retry)
                    checkpoint = res_retry.scalars().first()
                    if (
                        checkpoint
                        and checkpoint.status == "completed"
                        and checkpoint.input_hash == input_hash
                    ):
                        logger.info(
                            "Debate %s: stage %s completed after wait. Skipping.",
                            debate_id,
                            stage_key,
                        )
                        return await load_fn(session)
                    if not checkpoint:
                        raise RuntimeError(
                            f"Debate {debate_id}: stage {stage_key} checkpoint "
                            "was deleted while waiting."
                        )
                    if checkpoint.status != "running":
                        break
                else:
                    raise RuntimeError(
                        f"Debate {debate_id}: stage {stage_key} is currently "
                        "locked by another worker."
                    )

            checkpoint.status = "running"
            checkpoint.input_hash = input_hash
            checkpoint.started_at = datetime.now(timezone.utc)
            checkpoint.error_message = None
            checkpoint.error_code = None
            checkpoint.failed_at = None
            checkpoint.attempt = (checkpoint.attempt or 0) + 1
            checkpoint.owner_id = owner_id
            session.add(checkpoint)
            await session.commit()
        else:
            checkpoint = DebateStageCheckpoint(
                debate_id=debate_id,
                stage_key=stage_key,
                status="running",
                input_hash=input_hash,
                started_at=datetime.now(timezone.utc),
                attempt=1,
                owner_id=owner_id,
            )
            session.add(checkpoint)
            await session.commit()

    try:
        result = await run_fn()

        output_ref = None
        if (
            isinstance(result, tuple)
            and len(result) == 2
            and isinstance(result[1], str)
            and stage_key in {"synthesis", "verification", "synthesis_draft"}
        ):
            actual_result, output_ref = result
        else:
            actual_result = result

        async with async_session_scope() as session:
            await _assert_lease_owner(session, debate_id, owner_id, lease_epoch)
            res = await session.execute(stmt)
            checkpoint = res.scalars().first()
            if not checkpoint:
                raise RuntimeError(
                    f"Debate {debate_id}: stage {stage_key} checkpoint disappeared."
                )
            if owner_id is not None and checkpoint.owner_id != owner_id:
                raise LeaseOwnershipLost(
                    f"Debate {debate_id}: stage {stage_key} is owned by "
                    f"{checkpoint.owner_id}, not {owner_id}."
                )

            checkpoint.status = "completed"
            checkpoint.completed_at = datetime.now(timezone.utc)
            if output_ref:
                checkpoint.output_reference = output_ref
            session.add(checkpoint)
            await session.commit()

        return actual_result
    except Exception as exc:
        if isinstance(exc, LeaseOwnershipLost):
            raise

        async with async_session_scope() as session:
            await _assert_lease_owner(session, debate_id, owner_id, lease_epoch)
            res = await session.execute(stmt)
            checkpoint = res.scalars().first()
            if checkpoint:
                if owner_id is not None and checkpoint.owner_id != owner_id:
                    raise LeaseOwnershipLost(
                        f"Debate {debate_id}: stage {stage_key} is owned by "
                        f"{checkpoint.owner_id}, not {owner_id}."
                    ) from exc

                checkpoint.status = "failed"
                checkpoint.error_message = str(exc)
                checkpoint.failed_at = datetime.now(timezone.utc)
                checkpoint.error_code = getattr(exc, "code", "EXECUTION_ERROR")
                checkpoint.completed_at = datetime.now(timezone.utc)
                session.add(checkpoint)
                await session.commit()
        raise
