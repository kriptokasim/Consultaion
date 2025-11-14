from __future__ import annotations

import math
from collections import defaultdict
import os
import logging
from typing import Dict, Iterable, List, Optional, Tuple

from sqlalchemy import delete
from sqlmodel import Session, select

from database import session_scope
from models import Debate, PairwiseVote, RatingPersona, Score, utcnow

logger = logging.getLogger(__name__)

K_BASE = 24
K_NOVICE = 32
NOVICE_THRESHOLD = 15


def wilson_interval(wins: int, n: int, z: float = 1.96) -> Tuple[float, float]:
    if n <= 0:
        return (0.0, 0.0)
    p_hat = wins / n
    denominator = 1 + (z**2) / n
    center = p_hat + (z**2) / (2 * n)
    margin = z * math.sqrt((p_hat * (1 - p_hat) + (z**2) / (4 * n)) / n)
    low = max(0.0, (center - margin) / denominator)
    high = min(1.0, (center + margin) / denominator)
    return (low, high)


def _expected(elo_a: float, elo_b: float) -> float:
    return 1.0 / (1.0 + pow(10.0, (elo_b - elo_a) / 400.0))


def _initial_rating() -> Dict[str, float]:
    return {"elo": 1500.0, "wins": 0, "matches": 0}


def _collect_pairwise_from_scores(scores: List[Score]) -> List[dict]:
    per_judge: Dict[str, Dict[str, Score]] = defaultdict(dict)
    for score in scores:
        per_judge[score.judge][score.persona] = score

    pairwise: List[dict] = []
    for judge, bucket in per_judge.items():
        personas = list(bucket.keys())
        for i in range(len(personas)):
            for j in range(i + 1, len(personas)):
                a = personas[i]
                b = personas[j]
                score_a = bucket[a].score
                score_b = bucket[b].score
                if score_a == score_b:
                    continue
                winner = "A" if score_a > score_b else "B"
                pairwise.append(
                    {
                        "candidate_a": a,
                        "candidate_b": b,
                        "winner": winner,
                        "judge_id": judge,
                        "created_at": max(bucket[a].created_at, bucket[b].created_at),
                    }
                )
    return pairwise


def _upsert_pairwise_votes(session: Session, debate_id: str, category: Optional[str], votes: Iterable[dict]) -> List[PairwiseVote]:
    session.exec(delete(PairwiseVote).where(PairwiseVote.debate_id == debate_id))
    created: List[PairwiseVote] = []
    for vote in votes:
        row = PairwiseVote(
            debate_id=debate_id,
            category=category,
            candidate_a=vote["candidate_a"],
            candidate_b=vote["candidate_b"],
            winner=vote["winner"],
            judge_id=vote.get("judge_id"),
            user_id=vote.get("user_id"),
            created_at=vote.get("created_at") or utcnow(),
        )
        session.add(row)
        created.append(row)
    session.commit()
    return created


def _recompute_ratings(session: Session, category: Optional[str], personas: Iterable[str]) -> None:
    personas_set = set(personas)
    if not personas_set:
        return
    if category is None:
        votes_query = select(PairwiseVote).where(PairwiseVote.category.is_(None))
    else:
        votes_query = select(PairwiseVote).where(PairwiseVote.category == category)
    votes_query = votes_query.where(
        (PairwiseVote.candidate_a.in_(personas_set))
        | (PairwiseVote.candidate_b.in_(personas_set))
    )
    votes = session.exec(votes_query.order_by(PairwiseVote.created_at.asc())).all()
    if not votes:
        return

    state: Dict[str, Dict[str, float]] = defaultdict(_initial_rating)
    for vote in votes:
        a = vote.candidate_a
        b = vote.candidate_b
        if a not in state:
            state[a] = _initial_rating().copy()
        if b not in state:
            state[b] = _initial_rating().copy()

        elo_a = state[a]["elo"]
        elo_b = state[b]["elo"]
        expected_a = _expected(elo_a, elo_b)
        expected_b = 1.0 - expected_a
        result_a = 1.0 if vote.winner == "A" else 0.0
        result_b = 1.0 - result_a

        k_a = K_NOVICE if state[a]["matches"] < NOVICE_THRESHOLD else K_BASE
        k_b = K_NOVICE if state[b]["matches"] < NOVICE_THRESHOLD else K_BASE

        state[a]["elo"] = elo_a + k_a * (result_a - expected_a)
        state[b]["elo"] = elo_b + k_b * (result_b - expected_b)

        state[a]["matches"] += 1
        state[b]["matches"] += 1
        state[a]["wins"] += result_a
        state[b]["wins"] += result_b

    for persona, snapshot in state.items():
        matches = int(snapshot["matches"])
        wins = int(snapshot["wins"])
        win_rate = wins / matches if matches else 0.0
        ci_low, ci_high = wilson_interval(wins, matches) if matches else (0.0, 0.0)
        rating = session.exec(
            select(RatingPersona).where(RatingPersona.persona == persona, RatingPersona.category == category)
        ).first()
        if not rating:
            rating = RatingPersona(persona=persona, category=category)
        rating.elo = snapshot["elo"]
        rating.n_matches = matches
        rating.win_rate = win_rate
        rating.ci_low = ci_low
        rating.ci_high = ci_high
        rating.stdev = 0.0
        rating.last_updated = utcnow()
        session.add(rating)
    session.commit()


def update_ratings_for_debate(debate_id: str) -> None:
    if os.getenv("DISABLE_RATINGS", "0") == "1":
        logger.debug("Ratings disabled; skipping update for debate %s", debate_id)
        return
    with session_scope() as session:
        debate = session.exec(select(Debate).where(Debate.id == debate_id)).first()
        if not debate:
            return
        scores = session.exec(select(Score).where(Score.debate_id == debate_id)).all()
        if not scores:
            session.exec(delete(PairwiseVote).where(PairwiseVote.debate_id == debate_id))
            session.commit()
            return
        category = None
        if isinstance(debate.final_meta, dict):
            category = debate.final_meta.get("category")
        pairwise_records = _collect_pairwise_from_scores(scores)
        inserted = _upsert_pairwise_votes(session, debate_id, category, pairwise_records)
        personas = {vote.candidate_a for vote in inserted} | {vote.candidate_b for vote in inserted}
        if not personas:
            return
        _recompute_ratings(session, category, personas)


__all__ = ["wilson_interval", "update_ratings_for_debate"]
