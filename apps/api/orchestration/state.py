import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from database import session_scope
from models import Debate, DebateRound, Message, Score, Vote
from usage_limits import record_token_usage

logger = logging.getLogger(__name__)


class DebateStateManager:
    """
    Manages persistence of debate state to the database.
    """
    def __init__(self, debate_id: str, user_id: Optional[str] = None):
        self.debate_id = debate_id
        self.user_id = user_id

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
            
            if self.user_id:
                try:
                    record_token_usage(session, self.user_id, tokens_total, commit=False)
                except Exception:
                    logger.exception("Failed to record token usage for debate %s", self.debate_id)
            session.commit()
