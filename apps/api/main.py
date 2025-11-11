import asyncio
import json
import os
import uuid
from pathlib import Path
from time import time
from fastapi import BackgroundTasks, Depends, FastAPI, HTTPException, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy import func
from sqlmodel import Session, select

from database import engine, get_session, init_db
from models import Debate, DebateRound, Message, Score
from orchestrator import run_debate
from schemas import DebateCreate, default_debate_config

app = FastAPI(title="Consultaion API", version="0.1.0")

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


@app.on_event("startup")
def _startup() -> None:
    init_db()


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


@app.get("/config/default")
async def get_default_config():
    return default_debate_config()


@app.post("/debates")
async def create_debate(
    body: DebateCreate,
    background_tasks: BackgroundTasks,
    request: Request,
    session: Session = Depends(get_session),
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
    )
    session.add(debate)
    session.commit()

    q: asyncio.Queue = asyncio.Queue()
    CHANNELS[debate_id] = q
    background_tasks.add_task(run_debate, debate_id, body.prompt, q, config.model_dump())
    return {"id": debate_id}


@app.get("/debates")
async def list_debates(
    status: str | None = None,
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    session: Session = Depends(get_session),
):
    statement = select(Debate).order_by(Debate.created_at.desc())
    if status:
        statement = statement.where(Debate.status == status)
    statement = statement.offset(offset).limit(limit)
    debates = session.exec(statement).all()
    return debates


@app.get("/debates/{debate_id}")
async def get_debate(debate_id: str, session: Session = Depends(get_session)):
    debate = session.get(Debate, debate_id)
    if not debate:
        raise HTTPException(status_code=404, detail="debate not found")
    return debate


def _build_report(session: Session, debate_id: str):
    debate = session.get(Debate, debate_id)
    if not debate:
        raise HTTPException(status_code=404, detail="debate not found")

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
async def get_debate_report(debate_id: str, session: Session = Depends(get_session)):
    data = _build_report(session, debate_id)
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
async def export_debate_report(debate_id: str, session: Session = Depends(get_session)):
    data = _build_report(session, debate_id)
    filepath = EXPORT_DIR / f"{debate_id}.md"
    filepath.write_text(_report_to_markdown(data), encoding="utf-8")
    return {"uri": f"/exports/{filepath.name}"}


@app.get("/debates/{debate_id}/stream")
async def stream_events(debate_id: str):
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
