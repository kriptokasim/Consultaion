#!/usr/bin/env python3
"""CLI tool to diagnose a debate run's state.

Usage:
    python -m scripts.diagnose_run --debate-id <id>
    python scripts/diagnose_run.py --debate-id <id>
    python scripts/diagnose_run.py --debate-id <id> --format json

Admin-only diagnostic: reads DB state and outputs a human-readable decision tree.
No secrets, no raw prompts, no user emails.
"""

from __future__ import annotations

import argparse
import json
import sys
import os
from datetime import datetime, timezone

# Ensure the api/ directory is on sys.path so sibling packages resolve.
_api_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _api_dir not in sys.path:
    sys.path.insert(0, _api_dir)

from sqlmodel import Session, select, func
from models import Debate, Message, Score, DebateCheckpoint, DebateStageCheckpoint, LLMUsageLog
from checks import check_db_readiness


def _fmt_ts(dt: datetime | None) -> str:
    if dt is None:
        return "N/A"
    return dt.strftime("%Y-%m-%d %H:%M:%S UTC")


def _fmt_ts_iso(dt: datetime | None) -> str | None:
    if dt is None:
        return None
    return dt.isoformat()


def diagnose_json(debate_id: str) -> dict:
    """Produce structured JSON diagnostic for a debate run."""
    db_ok, db_info = check_db_readiness()
    rev = db_info.get("revision", {})

    result = {
        "debate": {
            "exists": False,
            "id": debate_id,
            "status": None,
            "mode": None,
            "created_at": None,
            "updated_at": None,
        },
        "content": {
            "has_final_content": False,
            "has_synthesis_report": False,
            "has_final_meta": False,
        },
        "responses": {
            "total_message_rows": 0,
            "canonical_response_rows": 0,
            "roles": {},
            "successful": 0,
            "failed": 0,
        },
        "events": {
            "count": 0,
            "response_like_events": 0,
        },
        "schema": {
            "current_revision": rev.get("current", None),
            "expected_head": rev.get("head", None),
            "at_head": rev.get("current") == rev.get("head") if rev.get("current") and rev.get("head") else None,
        },
        "runtime": {
            "git_sha": os.environ.get("GIT_SHA", "unknown"),
            "service_role": "api",
        },
        "diagnosis": "unknown",
    }

    from database import session_scope
    try:
        with session_scope() as session:
            debate = session.get(Debate, debate_id)
            if not debate:
                result["diagnosis"] = "debate_not_found"
                return result

            result["debate"]["exists"] = True
            result["debate"]["status"] = debate.status
            result["debate"]["mode"] = debate.mode
            result["debate"]["created_at"] = _fmt_ts_iso(debate.created_at)
            result["debate"]["updated_at"] = _fmt_ts_iso(debate.updated_at)

            result["content"]["has_final_content"] = debate.final_content is not None
            result["content"]["has_final_meta"] = debate.final_meta is not None

            has_synthesis = False
            if debate.final_meta:
                has_synthesis = bool(debate.final_meta.get("synthesis_report"))
            result["content"]["has_synthesis_report"] = has_synthesis

            msg_total = session.exec(
                select(func.count(Message.id)).where(Message.debate_id == debate_id)
            ).one()
            result["responses"]["total_message_rows"] = msg_total

            msg_by_role: dict[str, int] = {}
            for role_row in session.exec(
                select(Message.role, func.count(Message.id)).where(Message.debate_id == debate_id).group_by(Message.role)
            ).all():
                msg_by_role[role_row[0]] = role_row[1]
            result["responses"]["roles"] = msg_by_role

            responses = session.exec(
                select(Message).where(Message.debate_id == debate_id, Message.role == "arena_response")
            ).all()
            successful = sum(1 for m in responses if m.meta and m.meta.get("success", True))
            failed = len(responses) - successful
            result["responses"]["canonical_response_rows"] = len(responses)
            result["responses"]["successful"] = successful
            result["responses"]["failed"] = failed

            result["events"]["count"] = msg_total
            result["events"]["response_like_events"] = len(responses)

            if not db_ok:
                result["diagnosis"] = "schema_behind_head"
            elif not result["schema"]["at_head"]:
                result["diagnosis"] = "schema_behind_head"
            elif len(responses) == 0 and msg_total == 0:
                result["diagnosis"] = "responses_irrecoverably_missing"
            elif len(responses) == 0 and msg_total > 0:
                result["diagnosis"] = "serializer_failure_suspected"
            elif successful > 0:
                result["diagnosis"] = "responses_available"
            elif failed > 0 and len(responses) > 0:
                if result["content"]["has_final_meta"] and result["content"]["has_synthesis_report"]:
                    result["diagnosis"] = "responses_available"
                else:
                    result["diagnosis"] = "responses_missing_final_meta_recoverable"
            else:
                result["diagnosis"] = "responses_irrecoverably_missing"

    except Exception as exc:
        result["diagnosis"] = "message_query_failed"
        result["_error"] = str(exc)

    return result


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

        stage_keys = []
        for sc in session.exec(
            select(DebateStageCheckpoint).where(DebateStageCheckpoint.debate_id == debate_id)
        ).all():
            stage_keys.append(sc.stage_key)
        if stage_keys:
            lines.append(f"    Stages: {', '.join(stage_keys)}")
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
    parser.add_argument(
        "--format",
        choices=["text", "json"],
        default="text",
        dest="output_format",
        help="Output format (default: text)",
    )
    args = parser.parse_args()

    if args.output_format == "json":
        result = diagnose_json(args.debate_id)
        print(json.dumps(result, indent=2))
    else:
        print(diagnose(args.debate_id))


if __name__ == "__main__":
    main()
