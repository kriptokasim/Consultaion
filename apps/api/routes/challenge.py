from __future__ import annotations

import logging
from typing import List, Dict, Any, Optional
from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlmodel import Session, select
from auth import get_current_user
from deps import get_session
from models import User, Debate, Message, ChallengeSession, ChallengeRound, DebateTurn, UserInteraction
from orchestration.challenge import evaluate_synthesis_challenge
from exceptions import NotFoundError, PermissionError

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/challenge", tags=["challenge"])

# Maximum characters for transcript to avoid excessive tokens
MAX_TRANSCRIPT_CHARS = 8000


def build_debate_transcript(session: Session, debate: Debate) -> str:
    """
    Build a debate transcript from Message rows, with fallback to Debate.final_content.
    Bounded to MAX_TRANSCRIPT_CHARS to avoid excessive token usage.
    """
    messages = session.exec(
        select(Message)
        .where(Message.debate_id == debate.id)
        .order_by(Message.round_index.asc(), Message.id.asc())
    ).all()

    if messages:
        parts = []
        for msg in messages:
            speaker = msg.persona or msg.role or "Agent"
            content = (msg.content or "").strip()
            if content:
                parts.append(f"{speaker}: {content}")
        transcript = "\n\n".join(parts)
        if len(transcript) > MAX_TRANSCRIPT_CHARS:
            transcript = transcript[:MAX_TRANSCRIPT_CHARS] + "\n\n[...truncated]"
        return transcript

    # Fallback 1: Use final_content if available
    if debate.final_content:
        content = debate.final_content.strip()
        if len(content) > MAX_TRANSCRIPT_CHARS:
            content = content[:MAX_TRANSCRIPT_CHARS] + "\n\n[...truncated]"
        return content

    # Fallback 2: Use DebateTurn claims_nodes as structured context
    turns = session.exec(
        select(DebateTurn)
        .where(DebateTurn.debate_id == debate.id)
        .order_by(DebateTurn.created_at.asc())
    ).all()

    if turns:
        parts = []
        for t in turns:
            if t.claims_nodes and isinstance(t.claims_nodes, dict):
                claims = t.claims_nodes.get("claims", [])
                for claim in claims:
                    if isinstance(claim, dict):
                        text = claim.get("content") or claim.get("text") or str(claim)
                        parts.append(f"Agent (round {t.round_index}): {text}")
        if parts:
            transcript = "\n\n".join(parts)
            if len(transcript) > MAX_TRANSCRIPT_CHARS:
                transcript = transcript[:MAX_TRANSCRIPT_CHARS] + "\n\n[...truncated]"
            return transcript

    # Fallback 3: Use the debate prompt as minimal context
    return f"Debate prompt: {debate.prompt}"

class ChallengeCreate(BaseModel):
    debate_id: str = Field(..., description="The ID of the completed debate to challenge")

class ChallengeRoundSubmit(BaseModel):
    pushback_text: str = Field(..., min_length=5, description="The critique or pushback on the synthesis")


@router.post("")
async def start_challenge_session(
    payload: ChallengeCreate,
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_session)
):
    """
    Starts a new Synthesis Challenge session linked to a specific debate run.
    """
    debate = session.get(Debate, payload.debate_id)
    if not debate:
        raise NotFoundError(message="Debate run not found", code="debate.not_found")

    if debate.status != "completed":
        raise PermissionError(message="Cannot challenge an uncompleted debate synthesis", code="challenge.debate_not_completed")

    # Create session
    challenge_sess = ChallengeSession(
        user_id=current_user.id,
        debate_id=payload.debate_id
    )
    session.add(challenge_sess)
    session.commit()
    session.refresh(challenge_sess)

    return {
        "id": challenge_sess.id,
        "debate_id": challenge_sess.debate_id,
        "created_at": challenge_sess.created_at
    }


@router.get("/{session_id}")
async def get_challenge_session(
    session_id: str,
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_session)
):
    """
    Retrieves the details, original debate context, and history of challenge rounds.
    """
    challenge_sess = session.get(ChallengeSession, session_id)
    if not challenge_sess:
        raise NotFoundError(message="Challenge session not found", code="challenge.not_found")

    if not (current_user.role == "admin" or challenge_sess.user_id == current_user.id):
        raise PermissionError(message="Insufficient permissions", code="permission.denied")

    debate = session.get(Debate, challenge_sess.debate_id)
    if not debate:
        raise NotFoundError(message="Linked debate not found", code="debate.not_found")

    # Fetch rounds
    rounds_res = session.exec(
        select(ChallengeRound)
        .where(ChallengeRound.session_id == session_id)
        .order_by(ChallengeRound.round_index.asc())
    ).all()

    rounds = []
    for r in rounds_res:
        rounds.append({
            "id": r.id,
            "round_number": r.round_index,
            "pushback_text": r.user_pushback,
            "decision": r.action_taken,
            "response_reasoning": r.model_response,
            "revised_synthesis": r.revised_synthesis or "",
            "created_at": r.created_at
        })

    return {
        "id": challenge_sess.id,
        "debate_id": challenge_sess.debate_id,
        "original_prompt": debate.prompt,
        "original_synthesis": debate.final_content or "",
        "rounds": rounds,
        "created_at": challenge_sess.created_at
    }


@router.post("/{session_id}/round")
async def submit_challenge_round(
    session_id: str,
    payload: ChallengeRoundSubmit,
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_session)
):
    """
    Submits a user pushback/challenge, runs coordinator evaluation, and saves the round response.
    """
    challenge_sess = session.get(ChallengeSession, session_id)
    if not challenge_sess:
        raise NotFoundError(message="Challenge session not found", code="challenge.not_found")

    if not (current_user.role == "admin" or challenge_sess.user_id == current_user.id):
        raise PermissionError(message="Insufficient permissions", code="permission.denied")

    debate = session.get(Debate, challenge_sess.debate_id)
    if not debate:
        raise NotFoundError(message="Linked debate not found", code="debate.not_found")

    # Get rounds
    existing_rounds = session.exec(
        select(ChallengeRound)
        .where(ChallengeRound.session_id == session_id)
        .order_by(ChallengeRound.round_index.asc())
    ).all()

    next_round_index = len(existing_rounds) + 1

    # Determine current synthesis text
    if not existing_rounds:
        current_synthesis = debate.final_content or ""
    else:
        current_synthesis = existing_rounds[-1].revised_synthesis or ""

    # Build transcript from real data sources
    debate_transcript = build_debate_transcript(session, debate)

    # Evaluate challenge
    result = await evaluate_synthesis_challenge(
        prompt=debate.prompt,
        debate_transcript=debate_transcript,
        current_synthesis=current_synthesis,
        pushback_text=payload.pushback_text
    )

    # Save new round
    new_round = ChallengeRound(
        session_id=session_id,
        round_index=next_round_index,
        user_pushback=payload.pushback_text,
        action_taken=result["decision"],
        model_response=result["reasoning"],
        revised_synthesis=result["revised_synthesis"]
    )
    session.add(new_round)
    session.commit()
    session.refresh(new_round)

    # Log interaction for participation tracking
    interaction = UserInteraction(
        user_id=current_user.id,
        debate_id=challenge_sess.debate_id,
        interaction_type="challenge_pushback",
        details={
            "entity_id": new_round.id,
            "label": f"round_{next_round_index}",
            "summary": payload.pushback_text[:200],
            "status": result["decision"]
        }
    )
    session.add(interaction)
    session.commit()

    return {
        "id": new_round.id,
        "round_number": new_round.round_index,
        "decision": new_round.action_taken,
        "response_reasoning": new_round.model_response,
        "revised_synthesis": new_round.revised_synthesis or "",
        "created_at": new_round.created_at
    }

# Alias for router inclusion
challenge_router = router
