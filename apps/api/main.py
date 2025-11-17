import asyncio
import csv
import json
import logging.config
import os
import uuid
from datetime import datetime, timedelta
from contextlib import asynccontextmanager, suppress
from io import StringIO
from pathlib import Path
from time import time
from typing import Any, Optional, Literal

from fastapi import BackgroundTasks, Depends, FastAPI, HTTPException, Query, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, Response, StreamingResponse
import sqlalchemy as sa
from sqlalchemy import func
from sqlmodel import Session, select
from pydantic import BaseModel
from starlette.middleware.base import BaseHTTPMiddleware

from auth import (
    CSRF_COOKIE_NAME,
    ENABLE_CSRF,
    clear_auth_cookie,
    clear_csrf_cookie,
    create_access_token,
    generate_csrf_token,
    hash_password,
    set_auth_cookie,
    set_csrf_cookie,
    verify_password,
)
from audit import record_audit
from deps import get_current_user, get_optional_user, get_session, require_admin
from database import engine, init_db
from log_config import LOGGING_CONFIG, reset_request_id, set_request_id
from metrics import get_metrics_snapshot, increment_metric
from models import AuditLog, Debate, DebateRound, Message, PairwiseVote, RatingPersona, Score, Team, TeamMember, User
from orchestrator import run_debate
from ratelimit import get_recent_429_events, increment_ip_bucket, record_429
from ratings import update_ratings_for_debate
from schemas import DebateCreate, DebateConfig, default_debate_config
from usage_limits import RateLimitError, reserve_run_slot

logging.config.dictConfig(LOGGING_CONFIG)
logger = logging.getLogger(__name__)

SENTRY_DSN = os.getenv("SENTRY_DSN")
if SENTRY_DSN:
    import sentry_sdk
    from sentry_sdk.integrations.fastapi import FastApiIntegration
    from sentry_sdk.integrations.sqlalchemy import SqlalchemyIntegration

    sentry_sdk.init(
        dsn=SENTRY_DSN,
        environment=os.getenv("SENTRY_ENV", "local"),
        traces_sample_rate=float(os.getenv("SENTRY_SAMPLE_RATE", "0.1")),
        integrations=[FastApiIntegration(), SqlalchemyIntegration()],
    )

SAFE_METHODS = {"GET", "HEAD", "OPTIONS", "TRACE"}
ENABLE_SEC_HEADERS = os.getenv("ENABLE_SEC_HEADERS", "1").strip().lower() not in {"0", "false", "no"}


async def csrf_protect(request: Request) -> None:
    """Optional double-submit CSRF guard for cookie auth."""
    if request.method in SAFE_METHODS or not ENABLE_CSRF:
        return
    if request.url.path in {"/auth/login", "/auth/register"}:
        return
    csrf_cookie = request.cookies.get(CSRF_COOKIE_NAME)
    csrf_header = request.headers.get("x-csrf-token") or request.headers.get("X-CSRF-Token")
    if not csrf_cookie or not csrf_header or csrf_cookie != csrf_header:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="CSRF token missing or invalid",
        )

@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    _warn_on_multi_worker()
    sweeper_task: asyncio.Task | None = None
    try:
        sweeper_task = asyncio.create_task(_channel_sweeper_loop())
    except RuntimeError:
        sweeper_task = None
    try:
        yield
    finally:
        if sweeper_task:
            sweeper_task.cancel()
            with suppress(asyncio.CancelledError):
                await sweeper_task


app = FastAPI(
    title="Consultaion API",
    version="0.1.0",
    lifespan=lifespan,
    dependencies=[Depends(csrf_protect)],
)

if ENABLE_SEC_HEADERS:

    @app.middleware("http")
    async def security_headers_middleware(request: Request, call_next):
        response: Response = await call_next(request)
        response.headers.setdefault("X-Content-Type-Options", "nosniff")
        response.headers.setdefault("X-Frame-Options", "DENY")
        response.headers.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
        response.headers.setdefault("X-XSS-Protection", "0")
        return response


def _warn_on_multi_worker() -> None:
    """Warn if multiple workers are in use while SSE queues are process-local."""
    worker_env = os.getenv("WEB_CONCURRENCY") or os.getenv("GUNICORN_WORKERS")
    try:
        if worker_env and int(worker_env) > 1:
            logger.warning(
                "SSE queues are process-local; running with %s workers may cause /debates/{id}/stream to miss events. "
                "Use a single worker or move SSE to a shared backend.",
                worker_env,
            )
    except ValueError:
        # Ignore non-integer worker hints
        return


class RequestIDMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        request_id = request.headers.get("x-request-id") or str(uuid.uuid4())
        token = set_request_id(request_id)
        try:
            response = await call_next(request)
        finally:
            reset_request_id(token)
        response.headers["X-Request-ID"] = request_id
        return response

origins = os.getenv("CORS_ORIGINS", "http://localhost:3000").split(",")
app.add_middleware(RequestIDMiddleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


CHANNELS: dict[str, asyncio.Queue] = {}
CHANNEL_META: dict[str, float] = {}
CHANNEL_TTL_SECS = int(os.getenv("CHANNEL_TTL_SECS", "7200"))
CHANNEL_SWEEP_INTERVAL = int(os.getenv("CHANNEL_SWEEP_INTERVAL", "60"))
ENABLE_METRICS = os.getenv("ENABLE_METRICS", "1").lower() not in {"0", "false", "no"}


def _mark_channel(debate_id: str) -> None:
    try:
        loop = asyncio.get_running_loop()
        CHANNEL_META[debate_id] = loop.time()
    except RuntimeError:
        CHANNEL_META[debate_id] = time()


def sweep_stale_channels(now: float | None = None) -> list[str]:
    if now is None:
        try:
            now = asyncio.get_running_loop().time()
        except RuntimeError:
            now = time()
    stale = [key for key, created in CHANNEL_META.items() if now - created > CHANNEL_TTL_SECS]
    for debate_id in stale:
        CHANNELS.pop(debate_id, None)
        CHANNEL_META.pop(debate_id, None)
    return stale


async def _channel_sweeper_loop() -> None:
    try:
        while True:
            sweep_stale_channels()
            await asyncio.sleep(CHANNEL_SWEEP_INTERVAL)
    except asyncio.CancelledError:
        raise


def _cleanup_channel(debate_id: str) -> None:
    CHANNELS.pop(debate_id, None)
    CHANNEL_META.pop(debate_id, None)


def _track_metric(name: str, value: int = 1) -> None:
    if ENABLE_METRICS:
        increment_metric(name, value)

MAX_CALLS = int(os.getenv("RL_MAX_CALLS", "5"))
WINDOW = int(os.getenv("RL_WINDOW", "60"))
AUTH_MAX_CALLS = int(os.getenv("AUTH_RL_MAX_CALLS", "10"))
AUTH_WINDOW = int(os.getenv("AUTH_RL_WINDOW", "300"))
EXPORT_DIR = Path(os.getenv("EXPORT_DIR", "exports"))
EXPORT_DIR.mkdir(parents=True, exist_ok=True)


class AuthRequest(BaseModel):
    email: str
    password: str


class UserProfile(BaseModel):
    id: str
    email: str
    role: str

class TeamCreate(BaseModel):
    name: str


class TeamMemberCreate(BaseModel):
    email: str
    role: Literal["owner", "editor", "viewer"] = "viewer"


class DebateUpdate(BaseModel):
    team_id: Optional[str] = None


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


class HealthSnapshot(BaseModel):
    db_ok: bool
    rate_limit_backend: str
    redis_ok: Optional[bool] = None
    enable_csrf: bool
    enable_sec_headers: bool
    mock_mode: bool


class RateLimitSnapshot(BaseModel):
    backend: str
    window: int
    max_calls: int
    recent_429s: list[dict]


class DebateSummary(BaseModel):
    total: int
    last_24h: int
    last_7d: int
    fast_debate: int


def serialize_user(user: User) -> dict[str, Any]:
    return {"id": user.id, "email": user.email, "role": user.role}


@app.get("/healthz")
def healthz():
    return {"status": "ok"}


@app.get("/readyz")
def readyz(session: Session = Depends(get_session)):
    session.exec(sa.text("SELECT 1"))
    return {"db": "ok"}


if ENABLE_METRICS:

    @app.get("/metrics")
    def metrics():
        return get_metrics_snapshot()


@app.get("/version")
def version():
    return {"app": "consultaion", "version": os.getenv("APP_VERSION", "0.2.0")}


def _members_from_config(config: DebateConfig) -> list[dict[str, str]]:
    members: list[dict[str, str]] = []
    seen: set[str] = set()

    for agent in config.agents:
        agent_id = agent.name
        role = "critic" if "critic" in agent.name.lower() else "agent"
        members.append(
            {
                "id": agent_id,
                "name": agent.name,
                "role": role,
                "party": getattr(agent, "tools", None) and ", ".join(agent.tools or []) or None,
            }
        )
        seen.add(agent_id)

    for judge in config.judges:
        if judge.name in seen:
            continue
        members.append({"id": judge.name, "name": judge.name, "role": "judge"})
        seen.add(judge.name)

    return members


def _serialize_team(team: Team, role: Optional[str] = None) -> dict[str, Any]:
    return {
        "id": team.id,
        "name": team.name,
        "created_at": team.created_at,
        "role": role,
    }


def _serialize_rating_persona(row: RatingPersona) -> dict[str, Any]:
    badge = "NEW" if row.n_matches < 15 else None
    return {
        "persona": row.persona,
        "category": row.category,
        "elo": row.elo,
        "stdev": row.stdev,
        "n_matches": row.n_matches,
        "win_rate": row.win_rate,
        "ci": {"low": row.ci_low, "high": row.ci_high},
        "last_updated": row.last_updated.isoformat() if row.last_updated else None,
        "label": f"{row.persona}{f' ({row.category})' if row.category else ''}",
        "badge": badge,
    }


def _user_team_role(session: Session, user_id: Optional[str], team_id: Optional[str]) -> Optional[str]:
    if not user_id or not team_id:
        return None
    return session.exec(
        select(TeamMember.role).where(TeamMember.user_id == user_id, TeamMember.team_id == team_id)
    ).first()


def _user_is_team_member(session: Session, user: Optional[User], team_id: Optional[str]) -> bool:
    if not user or not team_id:
        return False
    if user.role == "admin":
        return True
    role = _user_team_role(session, user.id, team_id)
    return role is not None


def _user_can_edit_team(session: Session, user: User, team_id: Optional[str]) -> bool:
    if not team_id:
        return False
    if user.role == "admin":
        return True
    role = _user_team_role(session, user.id, team_id)
    return role in {"owner", "editor"}


def _user_team_ids(session: Session, user_id: str) -> list[str]:
    rows = session.exec(select(TeamMember.team_id).where(TeamMember.user_id == user_id)).all()
    return [row[0] if isinstance(row, tuple) else row for row in rows]


def _is_debate_owner_or_admin(debate: Debate, user: User) -> bool:
    return user.role == "admin" or debate.user_id == user.id


def _avg_scores_for_debate(session: Session, debate_id: str) -> list[tuple[str, float]]:
    rows = session.exec(select(Score.persona, func.avg(Score.score)).where(Score.debate_id == debate_id).group_by(Score.persona)).all()
    result: list[tuple[str, float]] = []
    for row in rows:
        if isinstance(row, tuple):
            result.append((row[0], float(row[1])))
        else:
            result.append((row.persona, float(row.avg)))
    result.sort(key=lambda x: x[1], reverse=True)
    return result


def _champion_for_debate(session: Session, debate_id: str) -> tuple[Optional[str], Optional[float], Optional[float]]:
    scores = _avg_scores_for_debate(session, debate_id)
    if not scores:
        return None, None, None
    champion_persona, champion_score = scores[0]
    runner_up = scores[1][1] if len(scores) > 1 else None
    return champion_persona, champion_score, runner_up


def _excerpt(text: Optional[str], limit: int = 220) -> Optional[str]:
    if not text:
        return None
    clean = text.strip()
    if len(clean) <= limit:
        return clean
    return clean[:limit].rstrip() + "…"


def _build_hof_items(
    session: Session,
    debates: list[Debate],
    champion_filter: Optional[str],
) -> list[HallOfFameItem]:
    items: list[HallOfFameItem] = []
    for debate in debates:
        champion, champion_score, runner_up = _champion_for_debate(session, debate.id)
        if champion_filter and champion and champion_filter.lower() not in champion.lower():
            continue
        margin = None
        if champion_score is not None and runner_up is not None:
            margin = round(champion_score - runner_up, 4)
        excerpt = _excerpt(debate.final_content)
        items.append(
            HallOfFameItem(
                id=debate.id,
                prompt=debate.prompt or "",
                champion=champion,
                champion_score=champion_score,
                runner_up_score=runner_up,
                margin=margin,
                created_at=debate.created_at.isoformat() if debate.created_at else None,
                champion_excerpt=excerpt,
            )
        )
    return items


def _can_access_debate(debate: Debate, user: Optional[User], session: Session) -> bool:
    if debate.user_id is None:
        return True
    if not user:
        return False
    if user.role == "admin":
        return True
    if debate.user_id == user.id:
        return True
    if debate.team_id:
        return _user_is_team_member(session, user, debate.team_id)
    return False


def _require_debate_access(debate: Optional[Debate], user: Optional[User], session: Session) -> Debate:
    if not debate or not _can_access_debate(debate, user, session):
        raise HTTPException(status_code=404, detail="debate not found")
    return debate


@app.get("/config/default")
async def get_default_config():
    return default_debate_config()


@app.get("/leaderboard")
async def get_leaderboard(
    response: Response,
    category: Optional[str] = Query(default=None),
    min_matches: int = Query(0, ge=0, le=1000),
    limit: int = Query(50, ge=1, le=200),
    session: Session = Depends(get_session),
):
    stmt = select(RatingPersona).order_by(RatingPersona.elo.desc())
    if category == "":
        stmt = stmt.where(RatingPersona.category.is_(None))
    elif category:
        stmt = stmt.where(RatingPersona.category == category)
    if min_matches:
        stmt = stmt.where(RatingPersona.n_matches >= min_matches)
    stmt = stmt.limit(limit)
    rows = session.exec(stmt).all()
    payload = {"items": [_serialize_rating_persona(row) for row in rows]}
    response.headers["Cache-Control"] = "private, max-age=30"
    return payload


@app.get("/leaderboard/persona/{persona}")
async def get_leaderboard_persona(
    response: Response,
    persona: str,
    category: Optional[str] = Query(default=None),
    session: Session = Depends(get_session),
):
    stmt = select(RatingPersona).where(RatingPersona.persona == persona)
    if category == "":
        stmt = stmt.where(RatingPersona.category.is_(None))
    elif category:
        stmt = stmt.where(RatingPersona.category == category)
    row = session.exec(stmt).first()
    if not row:
        raise HTTPException(status_code=404, detail="persona not found")
    payload = _serialize_rating_persona(row)
    response.headers["Cache-Control"] = "private, max-age=30"
    return payload


@app.get("/stats/models", response_model=list[ModelStatsSummary])
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
            champ, _, _ = _champion_for_debate(session, debate_id)
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


@app.get("/stats/models/{model_id}", response_model=ModelStatsDetail)
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
        scores = _avg_scores_for_debate(session, debate.id)
        if not scores:
            continue
        total_debates += 1
        persona_score = next((s for s in scores if s[0] == model_id), None)
        if persona_score:
            scores_sum += persona_score[1]
            scores_count += 1
        champion_persona, champion_score = scores[0]
        if champion_persona == model_id:
            wins += 1
            champion_samples.append(
                {
                    "debate_id": debate.id,
                    "prompt": debate.prompt,
                    "score": champion_score,
                    "excerpt": _excerpt(debate.final_content),
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


@app.get("/config/members")
async def get_members(response: Response):
    config: DebateConfig = default_debate_config()
    payload = {"members": _members_from_config(config)}
    response.headers["Cache-Control"] = "private, max-age=30"
    return payload


@app.get("/stats/hall-of-fame", response_model=HallOfFameResponse)
async def get_hall_of_fame_stats(
    limit: int = Query(50, ge=1, le=200),
    sort: str = Query("top", pattern="^(top|recent|closest)$"),
    model: Optional[str] = Query(default=None),
    start_date: Optional[str] = Query(default=None),
    end_date: Optional[str] = Query(default=None),
    session: Session = Depends(get_session),
    _: Optional[User] = Depends(get_optional_user),
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
    items = _build_hof_items(session, rows, model)
    if sort == "recent":
        items.sort(key=lambda x: x.created_at or "", reverse=True)
    elif sort == "closest":
        items.sort(key=lambda x: abs(x.margin or 0), reverse=True)
    else:
        items.sort(key=lambda x: x.champion_score or 0, reverse=True)
    return HallOfFameResponse(items=items[:limit])


@app.get("/debates/{debate_id}/members")
async def get_debate_members(
    debate_id: str,
    session: Session = Depends(get_session),
    current_user: Optional[User] = Depends(get_optional_user),
):
    debate = _require_debate_access(session.get(Debate, debate_id), current_user, session)
    config_data = debate.config or {}
    try:
        config = DebateConfig.model_validate(config_data)
    except Exception:
        config = default_debate_config()
    return {"members": _members_from_config(config)}


@app.post("/auth/register")
async def register_user(body: AuthRequest, response: Response, session: Session = Depends(get_session), request: Any = None):
    ip = request.client.host if request and request.client else "anonymous"
    if request and not increment_ip_bucket(ip, AUTH_WINDOW, AUTH_MAX_CALLS):
        record_429(ip, request.url.path)
        raise HTTPException(status_code=429, detail="rate limit exceeded")
    email = body.email.strip().lower()
    if "@" not in email:
        raise HTTPException(status_code=400, detail="invalid email")
    existing = session.exec(select(User).where(User.email == email)).first()
    if existing:
        raise HTTPException(status_code=400, detail="email already registered")
    if len(body.password or "") < 8:
        raise HTTPException(status_code=400, detail="password too short; minimum 8 characters")
    user = User(email=email, password_hash=hash_password(body.password))
    session.add(user)
    session.commit()
    session.refresh(user)
    token = create_access_token(user_id=user.id, email=user.email, role=user.role)
    set_auth_cookie(response, token)
    if ENABLE_CSRF:
        set_csrf_cookie(response, generate_csrf_token())
    record_audit(
        "register",
        user_id=user.id,
        target_type="user",
        target_id=user.id,
        meta={"email": user.email},
    )
    return serialize_user(user)


@app.post("/auth/login")
async def login_user(body: AuthRequest, response: Response, session: Session = Depends(get_session), request: Any = None):
    ip = request.client.host if request and request.client else "anonymous"
    if request and not increment_ip_bucket(ip, AUTH_WINDOW, AUTH_MAX_CALLS):
        record_429(ip, request.url.path)
        raise HTTPException(status_code=429, detail="rate limit exceeded")
    email = body.email.strip().lower()
    user = session.exec(select(User).where(User.email == email)).first()
    if not user or not verify_password(body.password, user.password_hash):
        raise HTTPException(status_code=401, detail="invalid credentials")
    token = create_access_token(user_id=user.id, email=user.email, role=user.role)
    set_auth_cookie(response, token)
    if ENABLE_CSRF:
        set_csrf_cookie(response, generate_csrf_token())
    record_audit(
        "login",
        user_id=user.id,
        target_type="user",
        target_id=user.id,
        meta={"email": user.email},
    )
    return serialize_user(user)


@app.post("/auth/logout")
async def logout_user(response: Response):
    clear_auth_cookie(response)
    if ENABLE_CSRF:
        clear_csrf_cookie(response)
    return {"ok": True}


@app.get("/me")
async def get_me(current_user: User = Depends(get_current_user)):
    return serialize_user(current_user)


def _get_team_or_404(session: Session, team_id: str) -> Team:
    team = session.get(Team, team_id)
    if not team:
        raise HTTPException(status_code=404, detail="team not found")
    return team


@app.post("/teams")
async def create_team(
    body: TeamCreate,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    name = body.name.strip()
    if not name:
        raise HTTPException(status_code=400, detail="team name required")
    team = Team(name=name)
    session.add(team)
    session.commit()
    session.refresh(team)
    session.add(TeamMember(team_id=team.id, user_id=current_user.id, role="owner"))
    session.commit()
    record_audit(
        "team_created",
        user_id=current_user.id,
        target_type="team",
        target_id=team.id,
        meta={"name": team.name},
    )
    return _serialize_team(team, "owner")


@app.get("/teams")
async def list_teams(
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    rows = session.exec(
        select(Team, TeamMember.role)
        .join(TeamMember, TeamMember.team_id == Team.id)
        .where(TeamMember.user_id == current_user.id)
        .order_by(Team.created_at.desc())
    ).all()
    items = [
        _serialize_team(team, role)
        for team, role in rows
    ]
    return {"items": items}


@app.get("/teams/{team_id}/members")
async def list_team_members(
    team_id: str,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    team = _get_team_or_404(session, team_id)
    if not _user_is_team_member(session, current_user, team.id):
        raise HTTPException(status_code=403, detail="not a team member")
    rows = session.exec(
        select(TeamMember, User)
        .join(User, User.id == TeamMember.user_id)
        .where(TeamMember.team_id == team.id)
        .order_by(TeamMember.created_at.asc())
    ).all()
    return {
        "team": _serialize_team(team),
        "members": [
            {
                "id": member.id,
                "user_id": user.id,
                "email": user.email,
                "role": member.role,
                "created_at": member.created_at,
            }
            for member, user in rows
        ],
    }


@app.post("/teams/{team_id}/members")
async def add_team_member(
    team_id: str,
    body: TeamMemberCreate,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    team = _get_team_or_404(session, team_id)
    current_role = _user_team_role(session, current_user.id, team.id)
    if current_user.role != "admin" and current_role != "owner":
        raise HTTPException(status_code=403, detail="only owners can manage members")
    email = body.email.strip().lower()
    user = session.exec(select(User).where(User.email == email)).first()
    if not user:
        raise HTTPException(status_code=404, detail="user not found")
    member = session.exec(
        select(TeamMember).where(TeamMember.team_id == team.id, TeamMember.user_id == user.id)
    ).first()
    if member:
        member.role = body.role
        session.add(member)
    else:
        member = TeamMember(team_id=team.id, user_id=user.id, role=body.role)
        session.add(member)
    session.commit()
    record_audit(
        "team_member_added",
        user_id=current_user.id,
        target_type="team",
        target_id=team.id,
        meta={"member_id": member.user_id, "role": member.role},
    )
    return {
        "id": member.id,
        "team_id": member.team_id,
        "user_id": member.user_id,
        "role": member.role,
    }


@app.post("/debates")
async def create_debate(
    body: DebateCreate,
    background_tasks: BackgroundTasks,
    request: Request,
    session: Session = Depends(get_session),
    current_user: Optional[User] = Depends(get_optional_user),
):
    # Note: unauthenticated debate creation with small per-IP buckets can be abused; consider tightening in future.
    ip = request.client.host if request.client else "anonymous"
    allowed = increment_ip_bucket(ip, WINDOW, MAX_CALLS)
    if not allowed:
        record_429(ip, request.url.path)
        raise HTTPException(status_code=429, detail="rate limit exceeded")
    if current_user:
        try:
            reserve_run_slot(session, current_user.id)
        except RateLimitError as exc:
            payload = {
                "code": "rate_limit",
                "reason": exc.code,
                "detail": exc.detail,
                "reset_at": exc.reset_at,
            }
            record_audit(
                "rate_limit_block",
                user_id=current_user.id,
                target_type="debate",
                target_id=None,
                meta=payload,
            )
            raise HTTPException(status_code=429, detail=payload) from exc

    config = body.config or default_debate_config()
    debate_id = str(uuid.uuid4())
    debate = Debate(
        id=debate_id,
        prompt=body.prompt,
        status="queued",
        config=config.model_dump(),
        user_id=current_user.id if current_user else None,
    )
    session.add(debate)
    session.commit()

    q: asyncio.Queue = asyncio.Queue()
    CHANNELS[debate_id] = q
    _mark_channel(debate_id)
    if os.getenv("DISABLE_AUTORUN", "0") != "1":
        background_tasks.add_task(run_debate, debate_id, body.prompt, q, config.model_dump(), _cleanup_channel)
    record_audit(
        "debate_created",
        user_id=current_user.id if current_user else None,
        target_type="debate",
        target_id=debate_id,
        meta={"prompt": body.prompt},
    )
    _track_metric("debates_created")
    return {"id": debate_id}


@app.post("/debates/{debate_id}/start")
async def start_debate_run(
    debate_id: str,
    background_tasks: BackgroundTasks,
    session: Session = Depends(get_session),
    current_user: Optional[User] = Depends(get_optional_user),
):
    if os.getenv("DISABLE_AUTORUN", "0") != "1":
        raise HTTPException(status_code=400, detail="Manual start is disabled")
    debate = session.get(Debate, debate_id)
    debate = _require_debate_access(debate, current_user, session)
    if debate.status not in {"queued", "failed"}:
        raise HTTPException(status_code=400, detail="Debate already started")
    q = CHANNELS.get(debate_id)
    if not q:
        q = asyncio.Queue()
        CHANNELS[debate_id] = q
    _mark_channel(debate_id)
    config_payload = debate.config or default_debate_config().model_dump()
    background_tasks.add_task(run_debate, debate_id, debate.prompt, q, config_payload, _cleanup_channel)
    record_audit(
        "debate_manual_start",
        user_id=current_user.id if current_user else None,
        target_type="debate",
        target_id=debate_id,
    )
    return {"status": "scheduled"}


@app.get("/debates")
async def list_debates(
    status: str | None = None,
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    q: str | None = Query(default=None, description="Prompt substring filter"),
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    filters = []
    if current_user.role != "admin":
        team_ids = _user_team_ids(session, current_user.id)
        if team_ids:
            filters.append((Debate.user_id == current_user.id) | (Debate.team_id.in_(team_ids)))
        else:
            filters.append(Debate.user_id == current_user.id)
    elif status == "all":
        status = None
    if status:
        filters.append(Debate.status == status)
    if isinstance(q, str):
        query_text = q.strip()
        if query_text:
            filters.append(sa.func.lower(Debate.prompt).contains(query_text.lower()))

    base_query = select(Debate)
    if filters:
        base_query = base_query.where(*filters)

    total_stmt = select(func.count()).select_from(base_query.subquery())
    total_result = session.exec(total_stmt).one()
    if isinstance(total_result, tuple):
        total_result = total_result[0]
    total = int(total_result or 0)

    items_stmt = base_query.order_by(Debate.created_at.desc()).offset(offset).limit(limit)
    debates = session.exec(items_stmt).all()
    has_more = offset + len(debates) < total
    return {
        "items": debates,
        "total": total,
        "limit": limit,
        "offset": offset,
        "has_more": has_more,
    }


@app.get("/debates/{debate_id}")
async def get_debate(
    debate_id: str,
    session: Session = Depends(get_session),
    current_user: Optional[User] = Depends(get_optional_user),
):
    debate = session.get(Debate, debate_id)
    return _require_debate_access(debate, current_user, session)


def _build_report(session: Session, debate_id: str, current_user: Optional[User]):
    debate = _require_debate_access(session.get(Debate, debate_id), current_user, session)

    rounds = session.exec(
        select(DebateRound).where(DebateRound.debate_id == debate_id).order_by(DebateRound.index)
    ).all()
    scores = session.exec(select(Score).where(Score.debate_id == debate_id)).all()
    messages_count = session.exec(select(func.count()).where(Message.debate_id == debate_id)).one()
    if isinstance(messages_count, tuple):
        messages_count = messages_count[0]

    return {
        "debate": debate,
        "rounds": rounds,
        "scores": scores,
        "messages_count": messages_count,
    }


@app.get("/stats/health", response_model=HealthSnapshot)
async def get_system_health(
    session: Session = Depends(get_session),
    _: User = Depends(require_admin),
):
    db_ok = True
    try:
        session.exec(sa.text("SELECT 1"))
    except Exception:
        db_ok = False
    redis_ok = None
    if os.getenv("RATE_LIMIT_BACKEND", "memory").lower() == "redis":
        try:
            client = None
            from ratelimit import _get_redis_client  # type: ignore

            client = _get_redis_client()
            if client:
                redis_ok = bool(client.ping())
        except Exception:
            redis_ok = False

    return HealthSnapshot(
        db_ok=db_ok,
        rate_limit_backend=os.getenv("RATE_LIMIT_BACKEND", "memory"),
        redis_ok=redis_ok,
        enable_csrf=ENABLE_CSRF,
        enable_sec_headers=ENABLE_SEC_HEADERS,
        mock_mode=os.getenv("USE_MOCK", "1") != "0" and os.getenv("REQUIRE_REAL_LLM", "0") != "1",
    )


@app.get("/stats/rate-limit", response_model=RateLimitSnapshot)
async def get_rate_limit_snapshot(_: User = Depends(require_admin)):
    return RateLimitSnapshot(
        backend=os.getenv("RATE_LIMIT_BACKEND", "memory"),
        window=WINDOW,
        max_calls=MAX_CALLS,
        recent_429s=get_recent_429_events(),
    )


@app.get("/stats/debates", response_model=DebateSummary)
async def get_debate_summary(_: User = Depends(require_admin), session: Session = Depends(get_session)):
    now = datetime.utcnow()
    total = session.exec(select(func.count()).select_from(Debate)).one()
    last_24h = session.exec(
        select(func.count()).select_from(Debate).where(Debate.created_at >= now - timedelta(days=1))
    ).one()
    last_7d = session.exec(
        select(func.count()).select_from(Debate).where(Debate.created_at >= now - timedelta(days=7))
    ).one()
    # fast_debate is stored in config; fall back to python counting
    fast_count = 0
    configs = session.exec(select(Debate.config)).all()
    for cfg in configs:
        payload = cfg[0] if isinstance(cfg, tuple) else cfg
        if isinstance(payload, dict) and payload.get("fast_debate"):
            fast_count += 1

    def _num(value):
        if isinstance(value, tuple):
            return int(value[0] or 0)
        return int(value or 0)

    return DebateSummary(
        total=_num(total),
        last_24h=_num(last_24h),
        last_7d=_num(last_7d),
        fast_debate=fast_count,
    )


def _report_to_markdown(payload: dict) -> str:
    debate: Debate = payload["debate"]
    rounds: list[DebateRound] = payload["rounds"]
    scores: list[Score] = payload["scores"]
    lines = [
        f"# Debate {debate.id}",
        "",
        f"Prompt: {debate.prompt}",
        f"Status: {debate.status}",
        f"Final Answer:\n{debate.final_content or 'N/A'}",
        "",
        "## Rounds",
    ]
    for rnd in rounds:
        lines.append(f"- Round {rnd.index} ({rnd.label}): {rnd.note or ''}")
    lines.append("")
    lines.append("## Scores")
    for score in scores:
        lines.append(f"- {score.persona} judged by {score.judge}: {score.score} — {score.rationale}")
    lines.append("")
    lines.append(f"Messages logged: {payload['messages_count']}")
    return "\n".join(lines)


@app.get("/debates/{debate_id}/report")
async def get_debate_report(
    debate_id: str,
    session: Session = Depends(get_session),
    current_user: Optional[User] = Depends(get_optional_user),
):
    data = _build_report(session, debate_id, current_user)
    return {
        "id": debate_id,
        "prompt": data["debate"].prompt,
        "status": data["debate"].status,
        "final": data["debate"].final_content,
        "scores": [score.model_dump() for score in data["scores"]],
        "rounds": [round_.model_dump() for round_ in data["rounds"]],
        "messages_count": data["messages_count"],
        "created_at": data["debate"].created_at,
        "updated_at": data["debate"].updated_at,
    }


@app.post("/debates/{debate_id}/export")
async def export_debate_report(
    debate_id: str,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    data = _build_report(session, debate_id, current_user)
    filepath = EXPORT_DIR / f"{debate_id}.md"
    filepath.write_text(_report_to_markdown(data), encoding="utf-8")
    _track_metric("exports_generated")
    record_audit(
        "export_markdown",
        user_id=current_user.id if current_user else None,
        target_type="debate",
        target_id=debate_id,
    )
    content = filepath.read_text(encoding="utf-8")
    return Response(
        content=content,
        media_type="text/markdown; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{filepath.name}"'},
    )


@app.get("/debates/{debate_id}/events")
async def get_debate_events(
    debate_id: str,
    session: Session = Depends(get_session),
    current_user: Optional[User] = Depends(get_optional_user),
):
    debate = _require_debate_access(session.get(Debate, debate_id), current_user, session)

    messages = session.exec(
        select(Message).where(Message.debate_id == debate_id).order_by(Message.created_at.asc())
    ).all()
    scores = session.exec(
        select(Score).where(Score.debate_id == debate_id).order_by(Score.created_at.asc())
    ).all()
    pairwise_votes = session.exec(
        select(PairwiseVote)
        .where(PairwiseVote.debate_id == debate_id)
        .order_by(PairwiseVote.created_at.asc())
    ).all()

    events: list[dict[str, Any]] = []
    for message in messages:
        if message.role in {"candidate", "revised"}:
            events.append(
                {
                    "type": "message",
                    "round": message.round_index,
                    "actor": message.persona,
                    "role": "agent",
                    "text": message.content,
                    "at": message.created_at.isoformat(),
                }
            )

    for score in scores:
        events.append(
            {
                "type": "score",
                "persona": score.persona,
                "judge": score.judge,
                "score": float(score.score),
                "rationale": score.rationale,
                "role": "judge",
                "at": score.created_at.isoformat(),
            }
        )
    for vote in pairwise_votes:
        winner = vote.candidate_a if vote.winner == "A" else vote.candidate_b
        loser = vote.candidate_b if vote.winner == "A" else vote.candidate_a
        events.append(
            {
                "type": "pairwise",
                "winner": winner,
                "loser": loser,
                "judge": vote.judge_id,
                "user_id": vote.user_id,
                "category": vote.category,
                "at": vote.created_at.isoformat() if vote.created_at else None,
            }
        )

    events.sort(key=lambda event: event.get("at", ""))
    return {"items": events}


@app.get("/debates/{debate_id}/judges")
async def get_debate_judges(
    debate_id: str,
    session: Session = Depends(get_session),
    current_user: Optional[User] = Depends(get_optional_user),
):
    _require_debate_access(session.get(Debate, debate_id), current_user, session)
    rows = session.exec(
        select(Score.judge)
        .where(Score.debate_id == debate_id)
        .distinct()
        .order_by(Score.judge)
    ).all()
    judges: list[str] = []
    for row in rows:
        value = row[0] if isinstance(row, tuple) else row
        if value:
            judges.append(value)
    return {"judges": judges}


@app.get("/debates/{debate_id}/scores.csv")
async def export_scores_csv(
    debate_id: str,
    session: Session = Depends(get_session),
    current_user: Optional[User] = Depends(get_optional_user),
):
    _require_debate_access(session.get(Debate, debate_id), current_user, session)

    scores = session.exec(
        select(Score).where(Score.debate_id == debate_id).order_by(Score.created_at.asc())
    ).all()

    buffer = StringIO()
    writer = csv.writer(buffer)
    writer.writerow(["persona", "judge", "score", "rationale", "timestamp"])
    for score in scores:
        writer.writerow(
            [
                score.persona,
                score.judge,
                score.score,
                score.rationale,
                score.created_at.isoformat() if score.created_at else "",
            ]
        )

    csv_bytes = buffer.getvalue()
    headers = {"Content-Disposition": f'attachment; filename="{debate_id}.csv"'}
    _track_metric("exports_generated")
    record_audit(
        "export_csv",
        user_id=current_user.id if current_user else None,
        target_type="debate",
        target_id=debate_id,
    )
    return Response(content=csv_bytes, media_type="text/csv", headers=headers)


@app.get("/debates/{debate_id}/stream")
async def stream_events(
    debate_id: str,
    session: Session = Depends(get_session),
    current_user: Optional[User] = Depends(get_optional_user),
):
    _require_debate_access(session.get(Debate, debate_id), current_user, session)
    if debate_id not in CHANNELS:
        return JSONResponse({"error": "not found"}, status_code=404)
    q = CHANNELS[debate_id]
    _track_metric("sse_stream_open")

    async def eventgen():
        while True:
            event = await q.get()
            yield f"data: {json.dumps(event, ensure_ascii=False)}\n\n"
            if event.get("type") == "final":
                await asyncio.sleep(0.2)
                break

    return StreamingResponse(
        eventgen(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@app.get("/admin/users")
async def admin_users(
    session: Session = Depends(get_session),
    _: User = Depends(require_admin),
):
    query = (
        select(
            User,
            func.count(Debate.id).label("debate_count"),
            func.max(Debate.created_at).label("last_activity"),
        )
        .outerjoin(Debate, Debate.user_id == User.id)
        .group_by(User.id)
        .order_by(User.created_at.desc())
    )
    rows = session.exec(query).all()
    items: list[dict[str, Any]] = []
    for user, debate_count, last_activity in rows:
        items.append(
            {
                "id": user.id,
                "email": user.email,
                "role": user.role,
                "debate_count": int(debate_count or 0),
                "last_activity": last_activity.isoformat() if last_activity else None,
                "created_at": user.created_at.isoformat(),
            }
        )
    return {"items": items}


@app.get("/admin/logs")
async def admin_logs(
    limit: int = Query(100, ge=1, le=500),
    session: Session = Depends(get_session),
    _: User = Depends(require_admin),
):
    rows = session.exec(
        select(AuditLog).order_by(AuditLog.created_at.desc()).limit(limit)
    ).all()
    return {
        "items": [
            {
                "id": log.id,
                "action": log.action,
                "user_id": log.user_id,
                "target_type": log.target_type,
                "target_id": log.target_id,
                "meta": log.meta,
                "created_at": log.created_at.isoformat(),
            }
            for log in rows
        ]
    }


@app.post("/ratings/update/{debate_id}")
async def update_ratings_endpoint(
    debate_id: str,
    _: User = Depends(require_admin),
):
    await asyncio.to_thread(update_ratings_for_debate, debate_id)
    return {"ok": True}
@app.patch("/debates/{debate_id}")
async def update_debate(
    debate_id: str,
    body: DebateUpdate,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    debate = session.get(Debate, debate_id)
    if not debate:
        raise HTTPException(status_code=404, detail="debate not found")
    if not _is_debate_owner_or_admin(debate, current_user):
        raise HTTPException(status_code=403, detail="insufficient permissions")

    previous_team = debate.team_id
    if body.team_id is not None:
        if body.team_id == "":
            debate.team_id = None
        else:
            team = _get_team_or_404(session, body.team_id)
            if not _user_can_edit_team(session, current_user, team.id):
                raise HTTPException(status_code=403, detail="cannot assign to this team")
            debate.team_id = team.id

    session.add(debate)
    session.commit()
    session.refresh(debate)
    if previous_team != debate.team_id:
        record_audit(
            "debate_team_updated",
            user_id=current_user.id,
            target_type="debate",
            target_id=debate.id,
            meta={"team_id": debate.team_id},
        )
    return {
        "id": debate.id,
        "team_id": debate.team_id,
    }
