import csv
from io import StringIO
from typing import Any, Dict, List, Optional

from models import Debate, DebateRound, Message, Score, User
from routes.common import require_debate_access
from sqlalchemy import func
from sqlmodel import Session, select


def build_report(session: Session, debate_id: str, current_user: Optional[User]) -> Dict[str, Any]:
    """
    Fetch all data required for a debate report.
    """
    debate = require_debate_access(session.get(Debate, debate_id), current_user, session)

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


def report_to_markdown(payload: Dict[str, Any]) -> str:
    """
    Format a debate report as Markdown.
    """
    debate: Debate = payload["debate"]
    rounds: List[DebateRound] = payload["rounds"]
    scores: List[Score] = payload["scores"]
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


def generate_csv_content(scores: List[Score]) -> str:
    """
    Generate CSV content from scores.
    """
    header = ["persona", "judge", "score", "rationale", "timestamp"]
    with StringIO() as output:
        writer = csv.writer(output)
        writer.writerow(header)
        for score in scores:
            writer.writerow(
                [
                    score.persona,
                    score.judge,
                    float(score.score),
                    score.rationale or "",
                    score.created_at.isoformat() if score.created_at else "",
                ]
            )
        return output.getvalue()
