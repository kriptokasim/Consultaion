"""
Patchset 66.0: Stale Debate Cleanup Job

Periodically marks stale debates as failed/degraded and
ensures no debate remains in 'queued' or 'running' state indefinitely.
"""
import asyncio
import logging
from datetime import datetime, timedelta, timezone
from typing import List, Tuple

from config import settings
from database import session_scope
from models import Debate, DebateCheckpoint, DebateError, Vote
from sqlmodel import select
from sse_backend import get_sse_backend

logger = logging.getLogger(__name__)


async def cleanup_stale_debates() -> Tuple[int, int]:
    """
    Find and mark stale debates as failed or degraded.
    
    Returns (failed_count, degraded_count).
    """
    now = datetime.now(timezone.utc)
    running_cutoff = now - timedelta(seconds=settings.DEBATE_STALE_RUNNING_SECONDS)
    queued_cutoff = now - timedelta(seconds=settings.DEBATE_STALE_QUEUED_SECONDS)
    
    stale_debates: List[Tuple[Debate, str, int]] = []  # (debate, reason, age_seconds)
    
    with session_scope() as session:
        # Find stale queued debates
        stmt_queued = select(Debate).where(
            Debate.status == "queued",
            Debate.created_at < queued_cutoff
        )
        for debate in session.exec(stmt_queued).all():
            age = int((now - debate.created_at).total_seconds())
            stale_debates.append((debate, "queued_timeout", age))
        
        # Find stale running debates using checkpoint
        stmt_running = select(Debate).where(Debate.status == "running")
        for debate in session.exec(stmt_running).all():
            # Check checkpoint for last activity
            ckpt_stmt = select(DebateCheckpoint).where(
                DebateCheckpoint.debate_id == debate.id
            )
            ckpt = session.exec(ckpt_stmt).first()
            
            if ckpt:
                last_activity = ckpt.last_checkpoint_at
            else:
                # No checkpoint - use debate updated_at
                last_activity = debate.updated_at
            
            if last_activity < running_cutoff:
                age = int((now - last_activity).total_seconds())
                stale_debates.append((debate, "running_timeout", age))
    
    if not stale_debates:
        return 0, 0
    
    failed_count = 0
    degraded_count = 0
    backend = get_sse_backend()
    
    for debate, reason, age in stale_debates:
        # Determine if degraded (has partial output) or failed
        has_output = _debate_has_output(debate.id)
        final_status = "degraded" if has_output else "failed"
        
        with session_scope() as session:
            db_debate = session.get(Debate, debate.id)
            if not db_debate or db_debate.status not in {"queued", "running"}:
                # Status changed while we were processing
                continue
            
            # Update debate status
            db_debate.status = final_status
            db_debate.updated_at = now
            if not db_debate.final_meta:
                db_debate.final_meta = {}
            db_debate.final_meta["stale_cleanup"] = {
                "reason": reason,
                "age_seconds": age,
                "cleaned_at": now.isoformat(),
            }
            session.add(db_debate)
            
            # Create DebateError record
            error = DebateError(
                debate_id=debate.id,
                user_id=debate.user_id,
                status=final_status,
                error_summary=f"stale_debate_timeout: {reason}",
                participant_errors={
                    "reason": reason,
                    "age_seconds": age,
                    "last_known_step": _get_last_step(session, debate.id),
                },
            )
            session.add(error)
            
            # Update checkpoint if exists
            ckpt_stmt = select(DebateCheckpoint).where(
                DebateCheckpoint.debate_id == debate.id
            )
            ckpt = session.exec(ckpt_stmt).first()
            if ckpt:
                ckpt.status = final_status
                session.add(ckpt)
            
            session.commit()
        
        # Emit SSE event for observability
        try:
            await backend.publish(
                f"debate:{debate.id}",
                {
                    "type": "debate.failed",
                    "debate_id": debate.id,
                    "reason": "stale_timeout",
                    "stale_reason": reason,
                    "age_seconds": age,
                    "final_status": final_status,
                },
            )
        except Exception as e:
            logger.warning("Failed to publish stale cleanup SSE event: %s", e)
        
        if final_status == "degraded":
            degraded_count += 1
        else:
            failed_count += 1
        
        logger.info(
            "Stale debate cleanup: debate_id=%s status=%s reason=%s age_seconds=%d",
            debate.id,
            final_status,
            reason,
            age,
        )
    
    return failed_count, degraded_count


def _debate_has_output(debate_id: str) -> bool:
    """Check if debate has any persisted output (judge scores, votes, etc.)."""
    with session_scope() as session:
        # Check for vote (final ranking)
        vote_stmt = select(Vote).where(Vote.debate_id == debate_id)
        if session.exec(vote_stmt).first():
            return True
        
        # Check for final_content in debate
        debate = session.get(Debate, debate_id)
        if debate and debate.final_content:
            return True
        
        return False


def _get_last_step(session, debate_id: str) -> str:
    """Get the last known step from checkpoint or 'unknown'."""
    stmt = select(DebateCheckpoint).where(DebateCheckpoint.debate_id == debate_id)
    ckpt = session.exec(stmt).first()
    return ckpt.step if ckpt else "unknown"


async def cleanup_loop():
    """
    Background task that periodically runs stale debate cleanup.
    
    Should be started in main.py lifespan.
    """
    logger.info(
        "Starting stale debate cleanup loop (interval=%ds, running_ttl=%ds, queued_ttl=%ds)",
        settings.DEBATE_CLEANUP_LOOP_SECONDS,
        settings.DEBATE_STALE_RUNNING_SECONDS,
        settings.DEBATE_STALE_QUEUED_SECONDS,
    )
    
    while True:
        try:
            await asyncio.sleep(settings.DEBATE_CLEANUP_LOOP_SECONDS)
            failed, degraded = await cleanup_stale_debates()
            if failed or degraded:
                logger.info(
                    "Stale debate cleanup completed: failed=%d degraded=%d",
                    failed,
                    degraded,
                )
        except asyncio.CancelledError:
            logger.info("Stale debate cleanup loop shutting down")
            break
        except Exception:
            logger.exception("Error in stale debate cleanup loop")
            # Continue running despite errors
            await asyncio.sleep(5)


# Exported task reference for lifespan management
cleanup_task = None


def start_cleanup_loop() -> asyncio.Task:
    """Start the cleanup loop as a background task."""
    global cleanup_task
    cleanup_task = asyncio.create_task(cleanup_loop())
    return cleanup_task


def stop_cleanup_loop():
    """Stop the cleanup loop gracefully."""
    global cleanup_task
    if cleanup_task and not cleanup_task.done():
        cleanup_task.cancel()
