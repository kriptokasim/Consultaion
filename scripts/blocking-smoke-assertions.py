#!/usr/bin/env python3
"""
Blocking smoke assertions — verifies historical Run rendering pipeline.

Loads a complete historical Run (Debate) from the database and runs
16 required checks against its serialized representation.  Failure
artifacts are written to /tmp/smoke-artifacts/ for CI upload.

Usage:
    python scripts/blocking-smoke-assertions.py [--url DATABASE_URL]
    python scripts/blocking-smoke-assertions.py [--debate-id <id>]
    python scripts/blocking-smoke-assertions.py [--all]

Returns exit code 0 only if all 16 checks pass, else 1.
"""

from __future__ import annotations

import argparse
import json
import sys
import traceback
from datetime import datetime
from pathlib import Path
from typing import Any

ARTIFACT_DIR = Path("/tmp/smoke-artifacts")


class SmokeCheck:
    """A single named assertion with failure capture."""

    def __init__(self, name: str):
        self.name = name
        self.passed = False
        self.detail: str | None = None

    def ok(self, detail: str | None = None) -> None:
        self.passed = True
        self.detail = detail

    def fail(self, detail: str) -> None:
        self.passed = False
        self.detail = detail

    def __repr__(self) -> str:
        status = "PASS" if self.passed else "FAIL"
        return f"[{status}] {self.name}" + (f" — {self.detail}" if self.detail else "")


def write_artifact(name: str, data: Any) -> None:
    """Write a JSON artifact for CI upload."""
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    path = ARTIFACT_DIR / f"{name}.json"
    with open(path, "w") as f:
        json.dump(data, f, indent=2, default=str)
    print(f"  artifact: {path}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Blocking smoke assertions")
    parser.add_argument("--url", type=str, default=None, help="Database URL")
    parser.add_argument("--debate-id", type=str, default=None, help="Specific debate ID to test")
    parser.add_argument("--all", action="store_true", help="Test all completed debates")
    args = parser.parse_args()

    if args.url:
        database_url = args.url
    else:
        from config import settings
        database_url = settings.DATABASE_URL

    if not database_url:
        print("FATAL: DATABASE_URL is not set")
        sys.exit(1)

    print(f"Smoke assertions — {datetime.utcnow().isoformat()}Z")
    print(f"Database URL: {'***' if '@' in database_url else database_url}")

    from sqlalchemy import create_engine
    engine = create_engine(database_url, pool_pre_ping=True)

    from models import Debate
    from serializers import serialize_debate_private
    from sqlmodel import Session, select

    checks: list[SmokeCheck] = []

    def check(name: str) -> SmokeCheck:
        c = SmokeCheck(name)
        checks.append(c)
        return c

    session = Session(engine)

    try:
        # --- Load debate(s) ---
        if args.debate_id:
            debates = [session.get(Debate, args.debate_id)]
            if not debates[0]:
                print(f"FATAL: Debate {args.debate_id} not found")
                sys.exit(1)
        elif args.all:
            stmt = select(Debate).where(Debate.status.in_(["completed", "failed"]))
            debates = list(session.execute(stmt).scalars().all())
            if not debates:
                print("FATAL: No completed/failed debates found")
                sys.exit(1)
            print(f"Testing {len(debates)} debates")
        else:
            stmt = select(Debate).where(Debate.status.in_(["completed", "failed"])).limit(1)
            debates = list(session.execute(stmt).scalars().all())
            if not debates:
                print("FATAL: No completed/failed debates found in database")
                sys.exit(1)

        for debate in debates:
            debate_id = debate.id
            print(f"\n--- Checking debate {debate_id} (status={debate.status}) ---")

            # 1. Debate has a non-empty prompt
            c = check("debate.has_prompt")
            if debate.prompt and len(debate.prompt.strip()) > 0:
                c.ok(f"prompt length={len(debate.prompt)}")
            else:
                c.fail("prompt is empty or missing")

            # 2. Debate has a valid status
            c = check("debate.valid_status")
            if debate.status in ("created", "scheduled", "running", "perspectives_ready",
                                 "completed", "failed", "paused", "queued"):
                c.ok(f"status={debate.status}")
            else:
                c.fail(f"unknown status: {debate.status}")

            # 3. Debate has created_at
            c = check("debate.has_created_at")
            if debate.created_at:
                c.ok(f"created_at={debate.created_at}")
            else:
                c.fail("created_at is missing")

            # 4. Debate has a mode
            c = check("debate.has_mode")
            mode = getattr(debate, "mode", None)
            if mode:
                c.ok(f"mode={mode}")
            else:
                c.fail("mode is missing")

            # 5. Serialization succeeds without session
            c = check("serialize_base_succeeds")
            try:
                base = serialize_debate_private(debate)
                c.ok(f"fields={len(base)}")
            except Exception as e:
                c.fail(f"serialization failed: {e}")

            # 6. Serialization with session succeeds
            c = check("serialize_with_session_succeeds")
            try:
                full = serialize_debate_private(debate, session=session)
                c.ok(f"fields={len(full)}")
            except Exception as e:
                c.fail(f"serialization with session failed: {e}")

            # 7. Serialized output has 'id' field
            c = check("serialized_has_id")
            if full.get("id") == debate_id:
                c.ok()
            else:
                c.fail(f"id mismatch: {full.get('id')} vs {debate_id}")

            # 8. Serialized output has 'status' field
            c = check("serialized_has_status")
            if full.get("status"):
                c.ok(f"status={full['status']}")
            else:
                c.fail("status field missing")

            # 9. Serialized output has 'prompt' field
            c = check("serialized_has_prompt")
            if full.get("prompt"):
                c.ok()
            else:
                c.fail("prompt field missing")

            # 10. read_quality is present
            c = check("serialized_read_quality")
            rq = full.get("read_quality")
            if rq in ("full", "degraded"):
                c.ok(f"read_quality={rq}")
            else:
                c.fail(f"unexpected read_quality: {rq}")

            # 11. final_content is present for completed debates
            if debate.status == "completed":
                c = check("completed_has_final_content")
                if debate.final_content:
                    c.ok(f"final_content length={len(debate.final_content)}")
                else:
                    c.fail("completed debate missing final_content")

            # 12. final_meta present for completed/failed debates
            c = check("final_meta_present")
            if debate.final_meta:
                c.ok(f"final_meta keys={list(debate.final_meta.keys())}")
            else:
                c.fail("final_meta is missing or None")

            # 13. created_at is a datetime
            c = check("created_at_is_datetime")
            if isinstance(debate.created_at, datetime):
                c.ok()
            else:
                c.fail(f"type={type(debate.created_at)}")

            # 14. user_id is present (private serialization)
            c = check("serialized_has_user_id")
            if full.get("user_id"):
                c.ok(f"user_id={full['user_id']}")
            else:
                c.fail("user_id is missing")

            # 15. Serialized output is JSON-serializable
            c = check("serialized_is_json_serializable")
            try:
                json.dumps(full, default=str)
                c.ok()
            except Exception as e:
                c.fail(f"JSON serialization failed: {e}")

            # 16. Engine version present
            c = check("has_engine_version")
            ev = getattr(debate, "engine_version", None) or full.get("engine_version")
            if ev:
                c.ok(f"engine_version={ev}")
            else:
                c.fail("engine_version missing")

    except Exception as e:
        print(f"\nFATAL: Unhandled exception: {e}")
        traceback.print_exc()
        sys.exit(1)
    finally:
        session.close()

    # --- Summary ---
    print(f"\n{'='*60}")
    print(f"RESULTS: {sum(1 for c in checks if c.passed)}/{len(checks)} passed")
    fail_count = 0
    for c in checks:
        print(f"  {c}")
        if not c.passed:
            fail_count += 1

    # Write artifacts
    summary = {
        "timestamp": datetime.utcnow().isoformat() + "Z",
        "total": len(checks),
        "passed": sum(1 for c in checks if c.passed),
        "failed": fail_count,
        "checks": [
            {"name": c.name, "passed": c.passed, "detail": c.detail}
            for c in checks
        ],
    }
    write_artifact("smoke-summary", summary)

    if fail_count > 0:
        failures = [c for c in checks if not c.passed]
        write_artifact("smoke-failures", [{"name": c.name, "detail": c.detail} for c in failures])
        print(f"\nFAILED: {fail_count} assertion(s) failed — see artifacts")
        sys.exit(1)

    print("\nALL CHECKS PASSED")
    sys.exit(0)


if __name__ == "__main__":
    main()
