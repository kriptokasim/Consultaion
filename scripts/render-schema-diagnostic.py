#!/usr/bin/env python3
"""
Render Schema Diagnostic — prints schema state without credentials.

Usage:
    python scripts/render-schema-diagnostic.py [--url DATABASE_URL]
    python scripts/render-schema-diagnostic.py [--debate-id ID] [--format json]

If --url is omitted, reads from DATABASE_URL env var or defaults to
the AppSettings value.
"""

from __future__ import annotations

import argparse
import json
import sys


def mask_url(url: str) -> str:
    """Mask credentials in a database URL for safe printing."""
    if "@" in url:
        prefix, rest = url.split("@", 1)
        if "://" in prefix:
            scheme, creds = prefix.split("://", 1)
            return f"{scheme}://****:****@{rest}"
        return f"****:****@{rest}"
    return url


def diagnose_debate(session, debate_id: str) -> dict:
    """Query debate-specific diagnostics. READ-ONLY, no mutations."""
    from models import (
        Debate,
        DebateCheckpoint,
        DebateContinuation,
        DebateStageCheckpoint,
        Message,
        Score,
    )
    from sqlmodel import func, select

    result: dict = {
        "debate_id": debate_id,
        "debate_exists": False,
        "status": None,
        "mode": None,
        "message_table_exists": False,
        "total_message_count": 0,
        "canonical_response_count": 0,
        "role_distribution": {},
        "checkpoint_count": 0,
        "stage_checkpoint_count": 0,
        "continuation_count": 0,
        "score_count": 0,
        "has_final_content": False,
        "has_synthesis_report": False,
        "has_final_meta": False,
    }

    from sqlalchemy import inspect as sa_inspect

    inspector = sa_inspect(session.get_bind())
    table_names = inspector.get_table_names()

    result["message_table_exists"] = "message" in table_names

    if not result["message_table_exists"]:
        return result

    debate = session.get(Debate, debate_id)
    if debate is None:
        return result

    result["debate_exists"] = True
    result["status"] = debate.status
    result["mode"] = debate.mode
    result["has_final_content"] = debate.final_content is not None
    result["has_final_meta"] = debate.final_meta is not None

    has_synthesis = False
    if debate.final_meta:
        has_synthesis = bool(debate.final_meta.get("synthesis_report"))
    result["has_synthesis_report"] = has_synthesis

    total = session.exec(
        select(func.count(Message.id)).where(Message.debate_id == debate_id)
    ).one()
    result["total_message_count"] = total

    canonical = session.exec(
        select(func.count(Message.id)).where(
            Message.debate_id == debate_id, Message.role == "arena_response"
        )
    ).one()
    result["canonical_response_count"] = canonical

    roles: dict[str, int] = {}
    for role_row in session.exec(
        select(Message.role, func.count(Message.id))
        .where(Message.debate_id == debate_id)
        .group_by(Message.role)
    ).all():
        roles[role_row[0]] = role_row[1]
    result["role_distribution"] = roles

    result["checkpoint_count"] = session.exec(
        select(func.count(DebateCheckpoint.id)).where(DebateCheckpoint.debate_id == debate_id)
    ).one()

    result["stage_checkpoint_count"] = session.exec(
        select(func.count(DebateStageCheckpoint.id)).where(
            DebateStageCheckpoint.debate_id == debate_id
        )
    ).one()

    result["continuation_count"] = session.exec(
        select(func.count(DebateContinuation.id)).where(
            DebateContinuation.debate_id == debate_id
        )
    ).one()

    result["score_count"] = session.exec(
        select(func.count(Score.id)).where(Score.debate_id == debate_id)
    ).one()

    return result


def main() -> None:
    parser = argparse.ArgumentParser(description="Schema diagnostic")
    parser.add_argument("--url", type=str, default=None, help="Database URL")
    parser.add_argument("--debate-id", type=str, default=None, help="Debate UUID for debate-specific diagnostics")
    parser.add_argument(
        "--format",
        choices=["text", "json"],
        default="text",
        dest="output_format",
        help="Output format (default: text)",
    )
    args = parser.parse_args()

    if args.url:
        database_url = args.url
    else:
        from config import settings
        database_url = settings.DATABASE_URL

    if not database_url:
        print("ERROR: DATABASE_URL is not set")
        sys.exit(1)

    try:
        from sqlalchemy import create_engine, inspect, text
        engine = create_engine(database_url, pool_pre_ping=True)
    except Exception as exc:
        print(f"ERROR: Cannot connect: {exc}")
        sys.exit(1)

    dialect = engine.dialect.name

    from services.migration_safety import (
        ensure_alembic_version_table,
        get_current_revisions,
        get_migration_heads,
        verify_critical_columns,
        verify_required_tables,
    )
    from sqlmodel import Session

    schema_data: dict = {}

    with Session(engine) as session:
        ensure_alembic_version_table(session)

        inspector_obj = inspect(session.get_bind())
        alembic_table_exists = "alembic_version" in inspector_obj.get_table_names()

        version_num_type = None
        version_num_max_length = None

        if alembic_table_exists:
            cols = inspector_obj.get_columns("alembic_version")
            for c in cols:
                if c["name"] == "version_num":
                    version_num_type = str(c["type"])
                    try:
                        result = session.execute(
                            text(
                                "SELECT character_maximum_length "
                                "FROM information_schema.columns "
                                "WHERE table_name='alembic_version' "
                                "AND column_name='version_num'"
                            )
                        ).scalar()
                        if result:
                            version_num_max_length = result
                    except Exception:
                        pass

        current_revisions = get_current_revisions(session)
        heads = get_migration_heads()
        at_head = None
        if current_revisions and heads:
            at_head = current_revisions[0] == heads[0]

        missing_tables = verify_required_tables(session)
        missing_cols = verify_critical_columns(session)

        schema_data = {
            "dialect": dialect,
            "alembic_version_table": "present" if alembic_table_exists else "missing",
            "version_num_type": version_num_type,
            "version_num_max_length": version_num_max_length,
            "current_revisions": current_revisions or [],
            "expected_heads": heads or [],
            "at_head": at_head,
            "missing_tables": missing_tables,
            "missing_critical_columns": missing_cols,
        }

        debate_data = None
        if args.debate_id:
            debate_data = diagnose_debate(session, args.debate_id)

    if args.output_format == "json":
        output: dict = {
            "database_url": mask_url(database_url),
            "schema": schema_data,
        }
        if debate_data is not None:
            output["debate"] = debate_data
        print(json.dumps(output, indent=2))
    else:
        print(f"Database URL: {mask_url(database_url)}")
        print(f"Dialect: {dialect}")

        if alembic_table_exists:
            print(f"version_num type: {version_num_type}")
            if version_num_max_length:
                print(f"version_num max length: {version_num_max_length}")
        else:
            print("alembic_version table: MISSING")

        print(f"Current revision(s): {current_revisions or '(none)'}")
        print(f"Expected head(s): {heads}")

        if current_revisions and heads:
            print(f"At head: {at_head}")

        if missing_tables:
            print(f"Missing tables: {missing_tables}")
        else:
            print("Required tables: ALL PRESENT")

        if missing_cols:
            print(f"Missing critical columns: {missing_cols}")
        else:
            print("Critical columns: ALL PRESENT")

        if debate_data is not None:
            print()
            print(f"Debate: {args.debate_id}")
            print(f"  Exists: {debate_data['debate_exists']}")
            if debate_data["debate_exists"]:
                print(f"  Status: {debate_data['status']}")
                print(f"  Mode: {debate_data['mode']}")
                print(f"  Message table: {'present' if debate_data['message_table_exists'] else 'MISSING'}")
                print(f"  Total messages: {debate_data['total_message_count']}")
                print(f"  Canonical responses: {debate_data['canonical_response_count']}")
                print(f"  Role distribution: {debate_data['role_distribution']}")
                print(f"  Checkpoints: {debate_data['checkpoint_count']}")
                print(f"  Stage checkpoints: {debate_data['stage_checkpoint_count']}")
                print(f"  Continuations: {debate_data['continuation_count']}")
                print(f"  Scores: {debate_data['score_count']}")
                print(f"  Final content: {debate_data['has_final_content']}")
                print(f"  Synthesis report: {debate_data['has_synthesis_report']}")
                print(f"  Final meta: {debate_data['has_final_meta']}")

        print()
        print("Diagnostic complete")


if __name__ == "__main__":
    main()
