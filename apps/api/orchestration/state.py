import logging
import secrets
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

from config import settings
from database import session_scope
from models import Debate, DebateCheckpoint, DebateRound, Message, Score, Vote
from usage_limits import record_token_usage

logger = logging.getLogger(__name__)


class DebateStateManager:
    """
    Manages persistence of debate state to the database.
    
    Patchset 66.0: Enhanced with checkpoint methods for resumability.
    """
    def __init__(self, debate_id: str, user_id: Optional[str] = None):
        self.debate_id = debate_id
        self.user_id = user_id
        self._resume_token: Optional[str] = None

    def set_status(self, status: str, meta: Optional[Dict[str, Any]] = None) -> None:
        """Update the debate status and metadata."""
        with session_scope() as session:
            debate = session.get(Debate, self.debate_id)
            if debate:
                debate.status = status
                debate.updated_at = datetime.now(timezone.utc)
                if meta:
                    # Merge or overwrite meta? Overwrite for now as per existing logic
                    debate.final_meta = meta
                session.add(debate)
                session.commit()

    def start_round(self, index: int, label: str, note: str) -> int:
        """Create a new round record."""
        with session_scope() as session:
            round_record = DebateRound(
                debate_id=self.debate_id,
                index=index,
                label=label,
                note=note
            )
            session.add(round_record)
            session.commit()
            session.refresh(round_record)
            return round_record.id  # type: ignore[return-value]

    def end_round(self, round_id: int) -> None:
        """Mark a round as ended."""
        with session_scope() as session:
            round_record = session.get(DebateRound, round_id)
            if round_record:
                round_record.ended_at = datetime.now(timezone.utc)
                session.add(round_record)
                session.commit()

    def save_messages(self, round_index: int, messages: List[Dict[str, Any]], role: str) -> None:
        """Persist a batch of messages."""
        with session_scope() as session:
            for payload in messages:
                session.add(
                    Message(
                        debate_id=self.debate_id,
                        round_index=round_index,
                        role=role,
                        persona=payload.get("persona"),
                        content=payload.get("text", ""),
                        meta={k: v for k, v in payload.items() if k not in {"persona", "text"}},
                    )
                )
            session.commit()

    def save_scores(self, scores: List[Dict[str, Any]]) -> None:
        """Persist judge scores."""
        with session_scope() as session:
            for detail in scores:
                session.add(
                    Score(
                        debate_id=self.debate_id,
                        persona=detail["persona"],
                        judge=detail["judge"],
                        score=detail["score"],
                        rationale=detail["rationale"],
                    )
                )
            session.commit()

    def save_vote(self, method: str, ranking: List[str], details: Dict[str, Any]) -> None:
        """Persist the final vote/ranking."""
        with session_scope() as session:
            session.add(
                Vote(
                    debate_id=self.debate_id,
                    method=method,
                    rankings={"order": ranking},
                    weights={"borda_weight": 1.0, "condorcet_weight": 1.0},
                    result=details,
                )
            )
            session.commit()

    def complete_debate(
        self,
        final_content: str,
        final_meta: Dict[str, Any],
        status: str,
        tokens_total: float = 0.0
    ) -> None:
        """Finalize the debate record and record usage."""
        with session_scope() as session:
            debate = session.get(Debate, self.debate_id)
            if not debate:
                return
            debate.final_content = final_content
            debate.final_meta = final_meta
            debate.status = status
            debate.updated_at = datetime.now(timezone.utc)
            session.add(debate)
            
            # Also mark checkpoint as done
            self._update_checkpoint_in_session(
                session,
                step="done",
                status=status,
            )
            
            if self.user_id:
                try:
                    record_token_usage(session, self.user_id, tokens_total, commit=False)
                except Exception:
                    logger.exception("Failed to record token usage for debate %s", self.debate_id)
            session.commit()

    # ========== Patchset 66.0: Checkpoint Methods ==========

    def checkpoint_load(self) -> Optional[DebateCheckpoint]:
        """Load the checkpoint for this debate if one exists."""
        from sqlmodel import select
        with session_scope() as session:
            stmt = select(DebateCheckpoint).where(DebateCheckpoint.debate_id == self.debate_id)
            return session.exec(stmt).first()

    def checkpoint_create(
        self,
        step: str,
        step_index: int = 0,
        round_index: int = 0,
        context_meta: Optional[Dict[str, Any]] = None,
    ) -> DebateCheckpoint:
        """Create a new checkpoint for this debate."""
        now = datetime.now(timezone.utc)
        self._resume_token = secrets.token_urlsafe(16)
        
        with session_scope() as session:
            ckpt = DebateCheckpoint(
                debate_id=self.debate_id,
                step=step,
                step_index=step_index,
                round_index=round_index,
                status="running",
                attempt_count=1,
                resume_token=self._resume_token,
                resume_claimed_at=now,
                last_checkpoint_at=now,
                last_event_at=now,
                context_meta=context_meta,
            )
            session.add(ckpt)
            session.commit()
            session.refresh(ckpt)
            return ckpt

    def checkpoint_update(
        self,
        step: str,
        step_index: int = 0,
        round_index: int = 0,
        status: str = "running",
        context_meta: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Update checkpoint after completing an atomic step."""
        with session_scope() as session:
            self._update_checkpoint_in_session(
                session,
                step=step,
                step_index=step_index,
                round_index=round_index,
                status=status,
                context_meta=context_meta,
            )
            session.commit()

    def _update_checkpoint_in_session(
        self,
        session,
        step: str,
        step_index: int = 0,
        round_index: int = 0,
        status: str = "running",
        context_meta: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Internal helper to update checkpoint within an existing session."""
        from sqlmodel import select
        stmt = select(DebateCheckpoint).where(DebateCheckpoint.debate_id == self.debate_id)
        ckpt = session.exec(stmt).first()
        if ckpt:
            ckpt.step = step
            ckpt.step_index = step_index
            ckpt.round_index = round_index
            ckpt.status = status
            ckpt.last_checkpoint_at = datetime.now(timezone.utc)
            if context_meta is not None:
                ckpt.context_meta = context_meta
            session.add(ckpt)

    def checkpoint_touch_event(self) -> None:
        """Update last_event_at when streaming any SSE event."""
        from sqlmodel import select
        with session_scope() as session:
            stmt = select(DebateCheckpoint).where(DebateCheckpoint.debate_id == self.debate_id)
            ckpt = session.exec(stmt).first()
            if ckpt:
                ckpt.last_event_at = datetime.now(timezone.utc)
                session.add(ckpt)
                session.commit()

    def try_claim_ownership(self) -> bool:
        """
        Attempt to claim ownership for resuming this debate.
        
        Returns True if ownership was claimed, False if another worker owns it.
        Uses a short TTL to prevent permanent lock-outs.
        """
        from sqlmodel import select
        
        now = datetime.now(timezone.utc)
        ttl = timedelta(seconds=settings.DEBATE_RESUME_TOKEN_TTL_SECONDS)
        
        with session_scope() as session:
            stmt = select(DebateCheckpoint).where(DebateCheckpoint.debate_id == self.debate_id)
            ckpt = session.exec(stmt).first()
            
            if not ckpt:
                # No checkpoint exists - will be created by caller
                return True
            
            # Check if claimed recently by another worker
            if ckpt.resume_token and ckpt.resume_claimed_at:
                if now - ckpt.resume_claimed_at < ttl:
                    # Still owned by another worker
                    logger.info(
                        "Debate %s: ownership claimed by another worker (token=%s...)",
                        self.debate_id,
                        ckpt.resume_token[:8] if ckpt.resume_token else "none"
                    )
                    return False
            
            # Claim ownership
            self._resume_token = secrets.token_urlsafe(16)
            ckpt.resume_token = self._resume_token
            ckpt.resume_claimed_at = now
            ckpt.attempt_count += 1
            session.add(ckpt)
            session.commit()
            
            logger.info(
                "Debate %s: claimed ownership (attempt=%d, token=%s...)",
                self.debate_id,
                ckpt.attempt_count,
                self._resume_token[:8]
            )
            return True

    def should_resume(self) -> tuple[bool, Optional[str]]:
        """
        Check if this debate should be resumed and from which step.
        
        Returns (should_resume, step_to_resume_from).
        """
        from sqlmodel import select
        
        with session_scope() as session:
            debate = session.get(Debate, self.debate_id)
            if not debate:
                return False, None
            
            # Only resume queued or running debates
            if debate.status not in {"queued", "running"}:
                return False, None
            
            stmt = select(DebateCheckpoint).where(DebateCheckpoint.debate_id == self.debate_id)
            ckpt = session.exec(stmt).first()
            
            if not ckpt:
                # No checkpoint - start fresh from draft
                return True, "draft"
            
            if ckpt.status in {"completed", "failed", "degraded", "done"}:
                # Already finished
                return False, None
            
            # Resume from the recorded step
            return True, ckpt.step

