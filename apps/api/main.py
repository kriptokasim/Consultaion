import asyncio
import csv
import json
import os
import uuid
from contextlib import asynccontextmanager
from io import StringIO
from pathlib import Path
from time import time
from typing import Any, Optional

from fastapi import BackgroundTasks, Depends, FastAPI, HTTPException, Query, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, Response, StreamingResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy import func
from sqlmodel import Session, select
from pydantic import BaseModel

from auth import clear_auth_cookie, create_access_token, hash_password, set_auth_cookie, verify_password
from deps import get_current_user, get_optional_user, get_session, require_admin
from database import engine, init_db
from models import Debate, DebateRound, Message, Score, User
from orchestrator import run_debate
from schemas import DebateCreate, DebateConfig, default_debate_config

@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    yield


app = FastAPI(title="Consultaion API", version="0.1.0", lifespan=lifespan)

origins = os.getenv("CORS_ORIGINS", "http://localhost:3000").split(",")
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


CHANNELS: dict[str, asyncio.Queue] = {}
RATE_BUCKET: dict[str, list[float]] = {}
MAX_CALLS = int(os.getenv("RL_MAX_CALLS", "5"))
WINDOW = int(os.getenv("RL_WINDOW", "60"))
EXPORT_DIR = Path(os.getenv("EXPORT_DIR", "exports"))
EXPORT_DIR.mkdir(parents=True, exist_ok=True)

app.mount("/exports", StaticFiles(directory=str(EXPORT_DIR)), name="exports")


class AuthRequest(BaseModel):
    email: str
    password: str


class UserProfile(BaseModel):
    id: str
    email: str
    role: str


def serialize_user(user: User) -> dict[str, Any]:
    return {"id": user.id, "email": user.email, "role": user.role}


@app.get("/healthz")
def healthz():
    try:
        with engine.connect() as conn:
            conn.exec_driver_sql("SELECT 1")
    except Exception as exc:
        return {"ok": False, "error": str(exc)}
    return {"ok": True}


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


def _can_access_debate(debate: Debate, user: Optional[User]) -> bool:
    if debate.user_id is None:
        return True
    if not user:
        return False
    if user.role == "admin":
        return True
    return debate.user_id == user.id


def _require_debate_access(debate: Optional[Debate], user: Optional[User]) -> Debate:
    if not debate or not _can_access_debate(debate, user):
        raise HTTPException(status_code=404, detail="debate not found")
    return debate


@app.get("/config/default")
async def get_default_config():
    return default_debate_config()


@app.get("/config/members")
async def get_members():
    config: DebateConfig = default_debate_config()
    return {"members": _members_from_config(config)}


@app.get("/debates/{debate_id}/members")
async def get_debate_members(
    debate_id: str,
    session: Session = Depends(get_session),
    current_user: Optional[User] = Depends(get_optional_user),
):
    debate = _require_debate_access(session.get(Debate, debate_id), current_user)
    config_data = debate.config or {}
    try:
        config = DebateConfig.model_validate(config_data)
    except Exception:
        config = default_debate_config()
    return {"members": _members_from_config(config)}


@app.post("/auth/register")
async def register_user(body: AuthRequest, response: Response, session: Session = Depends(get_session)):
    email = body.email.strip().lower()
    if "@" not in email:
        raise HTTPException(status_code=400, detail="invalid email")
    existing = session.exec(select(User).where(User.email == email)).first()
    if existing:
        raise HTTPException(status_code=400, detail="email already registered")
    user = User(email=email, password_hash=hash_password(body.password))
    session.add(user)
    session.commit()
    session.refresh(user)
    token = create_access_token(user_id=user.id, email=user.email, role=user.role)
    set_auth_cookie(response, token)
    return serialize_user(user)


@app.post("/auth/login")
async def login_user(body: AuthRequest, response: Response, session: Session = Depends(get_session)):
    email = body.email.strip().lower()
    user = session.exec(select(User).where(User.email == email)).first()
    if not user or not verify_password(body.password, user.password_hash):
        raise HTTPException(status_code=401, detail="invalid credentials")
    token = create_access_token(user_id=user.id, email=user.email, role=user.role)
    set_auth_cookie(response, token)
    return serialize_user(user)


@app.post("/auth/logout")
async def logout_user(response: Response):
    clear_auth_cookie(response)
    return {"ok": True}


@app.get("/me")
async def get_me(current_user: User = Depends(get_current_user)):
    return serialize_user(current_user)


@app.post("/debates")
async def create_debate(
    body: DebateCreate,
    background_tasks: BackgroundTasks,
    request: Request,
    session: Session = Depends(get_session),
    current_user: Optional[User] = Depends(get_optional_user),
):
    ip = request.client.host if request.client else "anonymous"
    now = time()
    bucket = [stamp for stamp in RATE_BUCKET.get(ip, []) if now - stamp < WINDOW]
    if len(bucket) >= MAX_CALLS:
        raise HTTPException(status_code=429, detail="rate limit exceeded")
    bucket.append(now)
    RATE_BUCKET[ip] = bucket

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
    if os.getenv("DISABLE_AUTORUN", "0") != "1":
        background_tasks.add_task(run_debate, debate_id, body.prompt, q, config.model_dump())
    return {"id": debate_id}


@app.get("/debates")
async def list_debates(
    status: str | None = None,
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    statement = select(Debate).order_by(Debate.created_at.desc())
    if current_user.role != "admin":
        statement = statement.where(Debate.user_id == current_user.id)
    elif status == "all":
        status = None
    if status:
        statement = statement.where(Debate.status == status)
    statement = statement.offset(offset).limit(limit)
    debates = session.exec(statement).all()
    return debates


@app.get("/debates/{debate_id}")
async def get_debate(
    debate_id: str,
    session: Session = Depends(get_session),
    current_user: Optional[User] = Depends(get_optional_user),
):
    debate = session.get(Debate, debate_id)
    return _require_debate_access(debate, current_user)


def _build_report(session: Session, debate_id: str, current_user: Optional[User]):
    debate = _require_debate_access(session.get(Debate, debate_id), current_user)

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
    current_user: Optional[User] = Depends(get_optional_user),
):
    data = _build_report(session, debate_id, current_user)
    filepath = EXPORT_DIR / f"{debate_id}.md"
    filepath.write_text(_report_to_markdown(data), encoding="utf-8")
    return {"uri": f"/exports/{filepath.name}"}


@app.get("/debates/{debate_id}/events")
async def get_debate_events(
    debate_id: str,
    session: Session = Depends(get_session),
    current_user: Optional[User] = Depends(get_optional_user),
):
    debate = _require_debate_access(session.get(Debate, debate_id), current_user)

    messages = session.exec(
        select(Message).where(Message.debate_id == debate_id).order_by(Message.created_at.asc())
    ).all()
    scores = session.exec(
        select(Score).where(Score.debate_id == debate_id).order_by(Score.created_at.asc())
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

    events.sort(key=lambda event: event.get("at", ""))
    return {"items": events}


@app.get("/debates/{debate_id}/judges")
async def get_debate_judges(
    debate_id: str,
    session: Session = Depends(get_session),
    current_user: Optional[User] = Depends(get_optional_user),
):
    _require_debate_access(session.get(Debate, debate_id), current_user)
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
    _require_debate_access(session.get(Debate, debate_id), current_user)

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
    return Response(content=csv_bytes, media_type="text/csv", headers=headers)


@app.get("/debates/{debate_id}/stream")
async def stream_events(
    debate_id: str,
    session: Session = Depends(get_session),
    current_user: Optional[User] = Depends(get_optional_user),
):
    _require_debate_access(session.get(Debate, debate_id), current_user)
    if debate_id not in CHANNELS:
        return JSONResponse({"error": "not found"}, status_code=404)
    q = CHANNELS[debate_id]

    async def eventgen():
        while True:
            event = await q.get()
            yield f"data: {json.dumps(event, ensure_ascii=False)}\n\n"
            if event.get("type") == "final":
                await asyncio.sleep(0.2)
                break

    return StreamingResponse(eventgen(), media_type="text/event-stream")


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
