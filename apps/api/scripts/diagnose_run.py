#!/usr/bin/env python3
"""CLI tool to diagnose a debate run's state.

Usage:
    python -m scripts.diagnose_run --debate-id <id>
    python scripts/diagnose_run.py --debate-id <id>

Admin-only diagnostic: reads DB state and outputs a human-readable decision tree.
No secrets, no raw prompts, no user emails.
"""

from __future__ import annotations

import argparse
import json
import sys
import os
from datetime import datetime, timezone

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlmodel import Session, select, func
from models import Debate, Message, Score, DebateCheckpoint, DebateStageCheckpoint, LLMUsageLog
from checks import check_db_readiness


def _fmt_ts(dt: datetime | None) -> str:
    if dt is None:
        return "N/A"
    return dt.strftime("%Y-%m-%d %H:%M:%S UTC")


def diagnose(debate_id: str) -> str:
    lines: list[str] = []
    sep = "=" * 60

    lines.append(sep)
    lines.append(f"  DIAGNOSTIC REPORT — Debate {debate_id}")
    lines.append(sep)
    lines.append("")

    # 1. DB readiness
    db_ok, db_info = check_db_readiness()
    lines.append(f"[1] DATABASE: {'OK' if db_ok else 'DEGRADED'}")
    rev = db_info.get("revision", {})
    if rev:
        lines.append(f"    Current revision : {rev.get('current', 'N/A')}")
        lines.append(f"    Head revision    : {rev.get('head', 'N/A')}")
    lines.append("")

    # 2. Debate state
    from database import session_scope
    with session_scope() as session:
        debate = session.get(Debate, debate_id)
        if not debate:
            lines.append(f"[2] DEBATE: NOT FOUND")
            lines.append("")
            return "\n".join(lines)

        lines.append(f"[2] DEBATE STATE")
        lines.append(f"    Status          : {debate.status}")
        lines.append(f"    Mode            : {debate.mode}")
        lines.append(f"    Created         : {_fmt_ts(debate.created_at)}")
        lines.append(f"    Updated         : {_fmt_ts(debate.updated_at)}")
        config = debate.config or {}
        lines.append(f"    Locale          : {config.get('locale', 'en')}")
        lines.append("")

        # 3. Message counts
        msg_total = session.exec(
            select(func.count(Message.id)).where(Message.debate_id == debate_id)
        ).one()
        msg_by_role = {}
        for role_row in session.exec(
            select(Message.role, func.count(Message.id)).where(Message.debate_id == debate_id).group_by(Message.role)
        ).all():
            msg_by_role[role_row[0]] = role_row[1]

        lines.append(f"[3] MESSAGES: {msg_total} total")
        for role, count in sorted(msg_by_role.items()):
            lines.append(f"    {role:30s} {count}")
        lines.append("")

        # 4. Arena responses breakdown
        responses = session.exec(
            select(Message).where(Message.debate_id == debate_id, Message.role == "arena_response")
        ).all()
        successful = sum(1 for m in responses if m.meta and m.meta.get("success", True))
        failed = len(responses) - successful
        lines.append(f"[4] ARENA RESPONSES: {len(responses)} ({successful} ok, {failed} failed)")
        for msg in responses:
            meta = msg.meta or {}
            model_id = meta.get("model_id", "?")
            provider = meta.get("provider", "?")
            ok = "OK" if meta.get("success", True) else "FAIL"
            err_code = meta.get("error_code", "")
            lines.append(f"    [{ok:4s}] {model_id} ({provider}) {f'— {err_code}' if err_code else ''}")
        lines.append("")

        # 5. Scores
        score_count = session.exec(
            select(func.count(Score.id)).where(Score.debate_id == debate_id)
        ).one()
        lines.append(f"[5] SCORES: {score_count}")
        lines.append("")

        # 6. Checkpoints
        ckpt_count = session.exec(
            select(func.count(DebateCheckpoint.id)).where(DebateCheckpoint.debate_id == debate_id)
        ).one()
        stage_ckpt_count = session.exec(
            select(func.count(DebateStageCheckpoint.id)).where(DebateStageCheckpoint.debate_id == debate_id)
        ).one()
        lines.append(f"[6] CHECKPOINTS: {ckpt_count} global, {stage_ckpt_count} stage")

        stage_names = []
        for sc in session.exec(
            select(DebateStageCheckpoint).where(DebateStageCheckpoint.debate_id == debate_id)
        ).all():
            stage_names.append(sc.stage_name)
        if stage_names:
            lines.append(f"    Stages: {', '.join(stage_names)}")
        lines.append("")

        # 7. Provider failures from LLMUsageLog
        failures = session.exec(
            select(LLMUsageLog).where(
                LLMUsageLog.debate_id == debate_id, LLMUsageLog.success == False
            ).order_by(LLMUsageLog.created_at.desc())
        ).all()

        lines.append(f"[7] PROVIDER FAILURES: {len(failures)}")
        if failures:
            by_provider: dict[str, int] = {}
            for f_log in failures:
                key = f"{f_log.provider}/{f_log.model}"
                by_provider[key] = by_provider.get(key, 0) + 1
            for key, count in sorted(by_provider.items(), key=lambda x: -x[1]):
                lines.append(f"    {key}: {count}x")
            lines.append("")
            lines.append("    Last 5 failures:")
            for f_log in failures[:5]:
                lines.append(f"      {_fmt_ts(f_log.created_at)} | {f_log.provider}/{f_log.model} | role={f_log.role}")
                if f_log.error_message:
                    snippet = f_log.error_message[:120]
                    lines.append(f"        {snippet}")
        lines.append("")

        # 8. Decision tree
        lines.append(f"[8] DECISION TREE")
        status = debate.status
        if status == "failed":
            reason = "all_models_failed" if failed == len(responses) and len(responses) > 0 else "unknown"
            lines.append(f"    Run FAILED — reason: {reason}")
            if failed == len(responses) and len(responses) > 0:
                lines.append("    -> All provider calls failed. Check API keys and circuit state.")
            elif len(responses) == 0:
                lines.append("    -> No responses persisted. Check orchestrator logs for dispatch errors.")
        elif status == "completed":
            lines.append(f"    Run COMPLETED — {successful}/{len(responses)} models succeeded")
            if failed > 0:
                lines.append(f"    -> {failed} model(s) failed but synthesis proceeded (partial success).")
        elif status == "perspectives_ready":
            lines.append(f"    Run PAUSED at perspectives_ready — {successful}/{len(responses)} models succeeded")
            lines.append("    -> Awaiting user action to continue to synthesis.")
        elif status == "running":
            lines.append("    Run is still RUNNING — check orchestrator/worker logs for stalls.")
        elif status == "queued":
            lines.append("    Run is QUEUED — waiting for worker pickup.")
        else:
            lines.append(f"    Status: {status}")
        lines.append("")

        # 9. Schema info
        lines.append(f"[9] SCHEMA: db_ok={db_ok}")
        lines.append(f"    Missing capabilities: {db_info.get('missing_capabilities', [])}")
        lines.append("")

    lines.append(sep)
    lines.append("  End of report")
    lines.append(sep)
    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(description="Diagnose a Consultaion debate run")
    parser.add_argument("--debate-id", required=True, help="Debate UUID to diagnose")
    args = parser.parse_args()
    print(diagnose(args.debate_id))


if __name__ == "__main__":
    main()
