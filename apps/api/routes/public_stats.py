"""
Public-safe aggregate stats endpoint for the landing page.
Returns only non-sensitive aggregate metrics.
"""

import time
from typing import Optional

import sqlalchemy as sa
from config import settings
from deps import get_session
from fastapi import APIRouter, Depends
from models import Debate
from parliament.model_registry import list_enabled_models
from pydantic import BaseModel
from sqlmodel import Session, select

router = APIRouter(prefix="/public", tags=["public"])

# Simple in-memory TTL cache
_cache: dict = {"data": None, "ts": 0}
_CACHE_TTL = 60  # seconds


class PublicStats(BaseModel):
    completed_runs: int = 0
    reports_generated: int = 0
    active_models: int = 0
    avg_divergence_score: Optional[float] = None


@router.get("/stats", response_model=PublicStats)
def get_public_stats(session: Session = Depends(get_session)) -> PublicStats:
    """
    Return aggregate, public-safe platform statistics.
    No private data (emails, prompts, run IDs) is exposed.
    Cached for 60 seconds to avoid excessive DB load.
    """
    now = time.time()
    is_test = getattr(settings, "ENV", "development") == "test"
    if not is_test and _cache["data"] is not None and (now - _cache["ts"]) < _CACHE_TTL:
        return _cache["data"]

    # Count completed runs
    completed_runs = session.exec(
        select(sa.func.count()).select_from(Debate).where(Debate.status == "completed")
    ).one()

    # Count runs that have final_meta with report data (reports generated)
    reports_generated = session.exec(
        select(sa.func.count())
        .select_from(Debate)
        .where(Debate.status == "completed")
        .where(Debate.final_meta.isnot(None))
        .where(sa.cast(Debate.final_meta, sa.String) != "null")
    ).one()

    # Active models from the model registry
    try:
        enabled = list_enabled_models()
        active_models = len(enabled) if enabled else 0
    except Exception:
        active_models = 0

    stats = PublicStats(
        completed_runs=completed_runs or 0,
        reports_generated=reports_generated or 0,
        active_models=active_models,
        avg_divergence_score=None,  # TODO: compute when divergence scoring is aggregated
    )

    _cache["data"] = stats
    _cache["ts"] = now
    return stats
