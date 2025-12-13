from collections import defaultdict
from datetime import datetime, timedelta, timezone
from typing import Any, Optional

import sqlalchemy as sa
from auth import get_current_admin, get_optional_user
from config import settings
from deps import get_session
from fastapi import APIRouter, Depends, HTTPException, Query, Response
from metrics import get_metrics_snapshot
from models import Debate, Score
from parliament.model_registry import list_enabled_models
from pydantic import BaseModel
from ratelimit import ensure_rate_limiter_ready, get_recent_429_events
from schemas import DebateConfig, default_debate_config, default_panel_config
from sqlalchemy import func
from sqlmodel import Session, select
from sqlmodel import Session, select
from sse_backend import BaseSSEBackend
from deps import get_session, get_sse_backend

from routes.common import (
    avg_scores_for_debate,
    champion_for_debate,
    excerpt,
    members_from_config,
)

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







@router.get("/debug/cookie-config")
async def debug_cookie_config():
    """
    Debug endpoint to check cookie configuration.
    Helps diagnose cross-domain auth issues.
    """
    import os

    from auth import COOKIE_DOMAIN, COOKIE_SAMESITE, COOKIE_SECURE
    
    return {
        "is_local_env": settings.IS_LOCAL_ENV,
        "cookie_secure": COOKIE_SECURE,
        "cookie_samesite": COOKIE_SAMESITE,
        "cookie_domain": COOKIE_DOMAIN or "(not set)",
        "render_env_var": os.environ.get("RENDER", "(not set)"),
        "env": settings.ENV,
        "cors_origins": settings.CORS_ORIGINS,
        "web_app_origin": settings.WEB_APP_ORIGIN,
    }


if settings.ENABLE_METRICS:

    @router.get("/metrics")
    def metrics():
        payload = get_metrics_snapshot()
        payload["total_429s"] = len(get_recent_429_events())
        return payload


@router.get("/version")
def version():
    return {"app": "consultaion", "version": settings.APP_VERSION}


@router.get("/stats/models", response_model=list[ModelStatsSummary])
async def get_model_leaderboard_stats(session: Session = Depends(get_session)):
    rows = session.exec(select(Score.debate_id, Score.persona, Score.score)).all()
    if not rows:
        return []

    persona_stats: dict[str, dict[str, Any]] = defaultdict(lambda: {"score_sum": 0.0, "score_count": 0, "debates": set()})
    debate_persona_scores: dict[str, dict[str, list[float]]] = defaultdict(lambda: defaultdict(list))

    for row in rows:
        if isinstance(row, tuple):
            debate_id, persona, score_val = row
        else:
            debate_id, persona, score_val = row.debate_id, row.persona, row.score
        score_float = float(score_val or 0.0)
        persona_stats[persona]["score_sum"] += score_float
        persona_stats[persona]["score_count"] += 1
        persona_stats[persona]["debates"].add(debate_id)
        debate_persona_scores[debate_id][persona].append(score_float)

    champion_counts: dict[str, int] = defaultdict(int)
    for debate_id, persona_scores in debate_persona_scores.items():
        averages: list[tuple[str, float]] = []
        for persona, scores in persona_scores.items():
            if not scores:
                continue
            averages.append((persona, sum(scores) / len(scores)))
        if not averages:
            continue
        averages.sort(key=lambda item: item[1], reverse=True)
        champion_persona = averages[0][0]
        champion_counts[champion_persona] += 1

    summaries: list[ModelStatsSummary] = []
    for persona, stats in persona_stats.items():
        score_count = stats["score_count"]
        score_sum = stats["score_sum"]
        total_debates = len(stats["debates"])
        avg_score = score_sum / score_count if score_count else 0.0
        wins = champion_counts.get(persona, 0)
        win_rate = wins / total_debates if total_debates else 0.0
        summaries.append(
            ModelStatsSummary(
                model=persona,
                total_debates=total_debates,
                wins=wins,
                win_rate=win_rate,
                avg_champion_score=avg_score,
                avg_score_overall=avg_score,
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
    panel = default_panel_config()
    payload = {"members": members_from_config(config, panel)}
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
    _: Any = Depends(get_current_admin),
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
        enable_csrf=settings.ENABLE_CSRF,
        enable_sec_headers=settings.ENABLE_SEC_HEADERS,
        mock_mode=settings.USE_MOCK and not settings.REQUIRE_REAL_LLM,
    )


@router.get("/stats/rate-limit", response_model=RateLimitSnapshot)
async def get_rate_limit_snapshot(_: Any = Depends(get_current_admin)):
    backend = settings.RATE_LIMIT_BACKEND or "memory"
    return RateLimitSnapshot(
        backend=backend,
        window=settings.RL_WINDOW,
        max_calls=settings.RL_MAX_CALLS,
        recent_429s=get_recent_429_events(),
        total_429s=len(get_recent_429_events()),
    )


@router.get("/stats/debates", response_model=DebateSummary)
async def get_debate_summary(_: Any = Depends(get_current_admin), session: Session = Depends(get_session)):
    now = datetime.now(timezone.utc)
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
