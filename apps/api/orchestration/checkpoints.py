import asyncio
import hashlib
import json
import logging
from datetime import datetime, timezone
from typing import Any, Callable, Dict

from database_async import async_session_scope
from models import DebateStageCheckpoint
from sqlmodel import select

logger = logging.getLogger(__name__)


async def run_with_checkpoint(
    debate_id: str,
    stage_key: str,
    input_data: Dict[str, Any],
    run_fn: Callable[[], Any],
    load_fn: Callable[[Any], Any],
) -> Any:
    """
    Executes a pipeline stage wrapped in a database checkpoint transaction.
    Ensures idempotency, skips completed runs with matching inputs, and handles retries.
    """
    # 1. Compute input hash
    serialized = json.dumps(input_data, sort_keys=True, default=str)
    input_hash = hashlib.sha256(serialized.encode("utf-8")).hexdigest()

    # 2. Check and manage status
    async with async_session_scope() as session:
        stmt = (
            select(DebateStageCheckpoint)
            .where(DebateStageCheckpoint.debate_id == debate_id)
            .where(DebateStageCheckpoint.stage_key == stage_key)
        )
        res = await session.execute(stmt)
        checkpoint = res.scalars().first()

        if checkpoint:
            # If completed and hash matches, skip execution and load output
            if checkpoint.status == "completed" and checkpoint.input_hash == input_hash:
                logger.info("Debate %s: stage %s already completed with matching hash. Skipping.", debate_id, stage_key)
                return await load_fn(session)

            # If running, wait briefly and retry checking
            if checkpoint.status == "running":
                logger.warning("Debate %s: stage %s is currently marked as running. Waiting...", debate_id, stage_key)
                for _ in range(3):
                    await asyncio.sleep(1.0)
                    stmt_retry = (
                        select(DebateStageCheckpoint)
                        .where(DebateStageCheckpoint.debate_id == debate_id)
                        .where(DebateStageCheckpoint.stage_key == stage_key)
                    )
                    res_retry = await session.execute(stmt_retry)
                    checkpoint = res_retry.scalars().first()
                    if checkpoint and checkpoint.status == "completed" and checkpoint.input_hash == input_hash:
                        logger.info("Debate %s: stage %s completed after wait. Skipping.", debate_id, stage_key)
                        return await load_fn(session)
                    if not checkpoint or checkpoint.status != "running":
                        break

            # Update status to running
            checkpoint.status = "running"
            checkpoint.input_hash = input_hash
            checkpoint.started_at = datetime.now(timezone.utc)
            checkpoint.error_message = None
            session.add(checkpoint)
            await session.commit()
        else:
            # Create a new checkpoint record
            checkpoint = DebateStageCheckpoint(
                debate_id=debate_id,
                stage_key=stage_key,
                status="running",
                input_hash=input_hash,
                started_at=datetime.now(timezone.utc),
            )
            session.add(checkpoint)
            await session.commit()

    # 3. Execute stage callback
    try:
        result = await run_fn()

        # 4. Mark checkpoint as completed
        async with async_session_scope() as session:
            res = await session.execute(stmt)
            checkpoint = res.scalars().first()
            if checkpoint:
                checkpoint.status = "completed"
                checkpoint.completed_at = datetime.now(timezone.utc)
                session.add(checkpoint)
                await session.commit()

        return result
    except Exception as exc:
        # Mark checkpoint as failed
        async with async_session_scope() as session:
            res = await session.execute(stmt)
            checkpoint = res.scalars().first()
            if checkpoint:
                checkpoint.status = "failed"
                checkpoint.error_message = str(exc)
                checkpoint.completed_at = datetime.now(timezone.utc)
                session.add(checkpoint)
                await session.commit()
        raise exc
