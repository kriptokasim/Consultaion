import os
from datetime import datetime, timedelta
from typing import Any, Optional

import sqlalchemy as sa
from fastapi import APIRouter, Depends, HTTPException, Query, Response
from pydantic import BaseModel
from sqlalchemy import func
from sqlmodel import Session, select

from deps import get_optional_user, get_session, require_admin
from metrics import get_metrics_snapshot
from models import Debate, DebateRound, Message, RatingPersona, Score
from model_registry import list_enabled_models
from ratelimit import ensure_rate_limiter_ready, get_recent_429_events
from routes.common import (
    avg_scores_for_debate,
    champion_for_debate,
    excerpt,
    members_from_config,
)
from schemas import DebateConfig, default_debate_config

router = APIRouter(tags=["stats"])


class HealthSnapshot(BaseModel):
    db_ok: bool
    rate_limit_backend: str
    redis_ok: Optional[bool] = None
    enable_csrf: bool
    enable_sec_headers: bool
    mock_mode: bool
    models_available: bool | None = None
    enabled_model_count: int | None = None


class RateLimitSnapshot(BaseModel):
    backend: str
    window: int
    max_calls: int
    recent_429s: list[dict]
    total_429s: int | None = None


class DebateSummary(BaseModel):
    total: int
    last_24h: int
    last_7d: int
    fast_debate: int


class ModelStatsSummary(BaseModel):
    model: str
    total_debates: int
    wins: int
    win_rate: float
    avg_champion_score: Optional[float] = None
    avg_score_overall: Optional[float] = None


class ModelStatsDetail(BaseModel):
    model: str
    total_debates: int
    wins: int
    win_rate: float
    avg_champion_score: Optional[float] = None
    avg_score_overall: Optional[float] = None
    recent_debates: list[dict]
    champion_samples: list[dict]


class HallOfFameItem(BaseModel):
    id: str
    prompt: str
    champion: Optional[str] = None
    champion_score: Optional[float] = None
    runner_up_score: Optional[float] = None
    margin: Optional[float] = None
    created_at: Optional[str] = None
    champion_excerpt: Optional[str] = None


class HallOfFameResponse(BaseModel):
    items: list[HallOfFameItem]


@router.get("/healthz")
def healthz():
    backend, redis_ok = ensure_rate_limiter_ready()
    models_enabled = list_enabled_models()
    return {
        "status": "ok",
        "rate_limit_backend": backend,
        "redis_ok": redis_ok,
        "models_available": bool(models_enabled),
        "enabled_model_count": len(models_enabled),
    }


@router.get("/readyz")
def readyz(session: Session = Depends(get_session)):
    session.exec(sa.text("SELECT 1"))
    models_enabled = list_enabled_models()
    if not models_enabled:
        raise HTTPException(status_code=503, detail="no models enabled")
    return {"db": "ok", "models_available": True, "enabled_model_count": len(models_enabled)}


if os.getenv("ENABLE_METRICS", "1").lower() not in {"0", "false", "no"}:

    @router.get("/metrics")
    def metrics():
        payload = get_metrics_snapshot()
        payload["total_429s"] = len(get_recent_429_events())
        return payload


@router.get("/version")
def version():
    return {"app": "consultaion", "version": os.getenv("APP_VERSION", "0.2.0")}


@router.get("/stats/models", response_model=list[ModelStatsSummary])
async def get_model_leaderboard_stats(session: Session = Depends(get_session)):
    rows = session.exec(select(Score.persona, func.count(Score.id), func.avg(Score.score)).group_by(Score.persona)).all()
    summaries: list[ModelStatsSummary] = []
    for row in rows:
        if isinstance(row, tuple):
            persona, total, avg = row[0], int(row[1] or 0), float(row[2] or 0)
        else:
            persona = row.persona
            total = int(row.count)
            avg = float(row.avg)
        wins = 0
        debates_with_persona = session.exec(select(Score.debate_id).where(Score.persona == persona).distinct()).all()
        for debate_id_tuple in debates_with_persona:
            debate_id = debate_id_tuple[0] if isinstance(debate_id_tuple, tuple) else debate_id_tuple
            champ, _, _ = champion_for_debate(session, debate_id)
            if champ == persona:
                wins += 1
        win_rate = wins / total if total else 0.0
        summaries.append(
            ModelStatsSummary(
                model=persona,
                total_debates=total,
                wins=wins,
                win_rate=win_rate,
                avg_champion_score=avg,
                avg_score_overall=avg,
            )
        )
    summaries.sort(key=lambda x: x.win_rate, reverse=True)
    return summaries


@router.get("/stats/models/{model_id}", response_model=ModelStatsDetail)
async def get_model_detail(
    model_id: str,
    limit: int = Query(50, ge=1, le=200),
    session: Session = Depends(get_session),
):
    rows = session.exec(select(Debate).order_by(Debate.created_at.desc()).limit(limit)).all()
    total_debates = 0
    wins = 0
    scores_sum = 0.0
    scores_count = 0
    recent_debates: list[dict] = []
    champion_samples: list[dict] = []

    for debate in rows:
        scores = avg_scores_for_debate(session, debate.id)
        if not scores:
            continue
        total_debates += 1
        persona_score = next((s for s in scores if s[0] == model_id), None)
        if persona_score:
            scores_sum += persona_score[1]
            scores_count += 1
        champion_persona, champion_score, _ = scores[0][0], scores[0][1], None
        if champion_persona == model_id:
            wins += 1
            champion_samples.append(
                {
                    "debate_id": debate.id,
                    "prompt": debate.prompt,
                    "score": champion_score,
                    "excerpt": excerpt(debate.final_content),
                }
            )
        recent_debates.append(
            {
                "debate_id": debate.id,
                "prompt": debate.prompt,
                "champion": champion_persona,
                "champion_score": champion_score,
                "was_champion": champion_persona == model_id,
                "created_at": debate.created_at.isoformat() if debate.created_at else None,
            }
        )

    win_rate = wins / total_debates if total_debates else 0.0
    avg_score_overall = scores_sum / scores_count if scores_count else None
    avg_champion_score = (
        sum(item["score"] for item in champion_samples) / len(champion_samples) if champion_samples else None
    )
    return ModelStatsDetail(
        model=model_id,
        total_debates=total_debates,
        wins=wins,
        win_rate=win_rate,
        avg_champion_score=avg_champion_score,
        avg_score_overall=avg_score_overall,
        recent_debates=recent_debates,
        champion_samples=champion_samples[:5],
    )


@router.get("/config/members")
async def get_members(response: Response):
    config: DebateConfig = default_debate_config()
    payload = {"members": members_from_config(config)}
    response.headers["Cache-Control"] = "private, max-age=30"
    return payload


@router.get("/stats/hall-of-fame", response_model=HallOfFameResponse)
async def get_hall_of_fame_stats(
    limit: int = Query(50, ge=1, le=200),
    sort: str = Query("top", pattern="^(top|recent|closest)$"),
    model: Optional[str] = Query(default=None),
    start_date: Optional[str] = Query(default=None),
    end_date: Optional[str] = Query(default=None),
    session: Session = Depends(get_session),
    _: Optional[str] = Depends(get_optional_user),
):
    base_query = select(Debate)
    if start_date:
        try:
            start_dt = datetime.fromisoformat(start_date)
            base_query = base_query.where(Debate.created_at >= start_dt)
        except Exception:
            pass
    if end_date:
        try:
            end_dt = datetime.fromisoformat(end_date)
            base_query = base_query.where(Debate.created_at <= end_dt)
        except Exception:
            pass
    rows = session.exec(base_query).all()
    items: list[HallOfFameItem] = []
    for debate in rows:
        champion, champion_score, runner_up = champion_for_debate(session, debate.id)
        if model and champion and model.lower() not in champion.lower():
            continue
        margin = None
        if champion_score is not None and runner_up is not None:
            margin = round(champion_score - runner_up, 4)
        excerpt_text = excerpt(debate.final_content)
        items.append(
            HallOfFameItem(
                id=debate.id,
                prompt=debate.prompt or "",
                champion=champion,
                champion_score=champion_score,
                runner_up_score=runner_up,
                margin=margin,
                created_at=debate.created_at.isoformat() if debate.created_at else None,
                champion_excerpt=excerpt_text,
            )
        )
    if sort == "recent":
        items.sort(key=lambda x: x.created_at or "", reverse=True)
    elif sort == "closest":
        items.sort(key=lambda x: abs(x.margin or 0), reverse=True)
    else:
        items.sort(key=lambda x: x.champion_score or 0, reverse=True)
    return HallOfFameResponse(items=items[:limit])


@router.get("/stats/health", response_model=HealthSnapshot)
async def get_system_health(
    session: Session = Depends(get_session),
    _: Any = Depends(require_admin),
):
    db_ok = True
    try:
        session.exec(sa.text("SELECT 1"))
    except Exception:
        db_ok = False
    backend, redis_ok = ensure_rate_limiter_ready()
    return HealthSnapshot(
        db_ok=db_ok,
        rate_limit_backend=backend,
        redis_ok=redis_ok,
        enable_csrf=os.getenv("ENABLE_CSRF", "1").lower() not in {"0", "false", "no"},
        enable_sec_headers=os.getenv("ENABLE_SEC_HEADERS", "1").strip().lower() not in {"0", "false", "no"},
        mock_mode=os.getenv("USE_MOCK", "1") != "0" and os.getenv("REQUIRE_REAL_LLM", "0") != "1",
    )


@router.get("/stats/rate-limit", response_model=RateLimitSnapshot)
async def get_rate_limit_snapshot(_: Any = Depends(require_admin)):
    backend = os.getenv("RATE_LIMIT_BACKEND", "memory")
    return RateLimitSnapshot(
        backend=backend,
        window=int(os.getenv("RL_WINDOW", "60")),
        max_calls=int(os.getenv("RL_MAX_CALLS", "5")),
        recent_429s=get_recent_429_events(),
        total_429s=len(get_recent_429_events()),
    )


@router.get("/stats/debates", response_model=DebateSummary)
async def get_debate_summary(_: Any = Depends(require_admin), session: Session = Depends(get_session)):
    now = datetime.utcnow()
    total = session.exec(select(func.count()).select_from(Debate)).one()
    last_24h = session.exec(
        select(func.count()).select_from(Debate).where(Debate.created_at >= now - timedelta(days=1))
    ).one()
    last_7d = session.exec(
        select(func.count()).select_from(Debate).where(Debate.created_at >= now - timedelta(days=7))
    ).one()
    fast_count = 0
    configs = session.exec(select(Debate.config)).all()
    for cfg in configs:
        payload = cfg[0] if isinstance(cfg, tuple) else cfg
        if isinstance(payload, dict) and payload.get("fast_debate"):
            fast_count += 1

    def _num(value: Any) -> int:
        if isinstance(value, tuple):
            return int(value[0] or 0)
        return int(value or 0)

    return DebateSummary(
        total=_num(total),
        last_24h=_num(last_24h),
        last_7d=_num(last_7d),
        fast_debate=fast_count,
    )


# Alias for main/router imports
stats_router = router
