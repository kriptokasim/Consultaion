#!/usr/bin/env python3
"""
Patchset 136: Production Run Pipeline Smoke Test

Proves end-to-end execution by:
1. Checking pipeline health
2. Running LLM smoke test
3. Creating a tiny debate
4. Polling status until completion/failure
5. Printing a concise report

Usage:
    python scripts/smoke_run_pipeline.py --base-url https://your-app.onrender.com --token <admin-jwt>

Exit code 0 on PASS, non-zero on failure.
"""
from __future__ import annotations

import argparse
import json
import sys
import time
import urllib.error
import urllib.request


def _request(method: str, url: str, token: str | None = None, body: dict | None = None) -> dict:
    """Make an HTTP request and return parsed JSON."""
    headers = {"Content-Type": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"

    data = json.dumps(body).encode() if body else None
    req = urllib.request.Request(url, data=data, headers=headers, method=method)

    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            return json.loads(resp.read().decode())
    except urllib.error.HTTPError as exc:
        body_text = exc.read().decode() if exc.fp else ""
        print(f"  HTTP {exc.code}: {body_text[:200]}", file=sys.stderr)
        raise SystemExit(1)


def main() -> None:
    parser = argparse.ArgumentParser(description="Run Pipeline Smoke Test")
    parser.add_argument("--base-url", required=True, help="API base URL (e.g. https://app.onrender.com)")
    parser.add_argument("--token", required=True, help="Admin JWT token")
    parser.add_argument("--provider", default="openrouter", help="Provider to smoke test")
    parser.add_argument("--model-id", default=None, help="Model ID for smoke test")
    parser.add_argument("--poll-timeout", type=int, default=300, help="Max seconds to poll debate status")
    args = parser.parse_args()

    base = args.base_url.rstrip("/")
    passed = []
    failed = []

    print("Run Pipeline Smoke Test")
    print("=" * 50)

    # 1. Pipeline Health
    print("\n[1/4] Checking pipeline health...")
    try:
        health = _request("GET", f"{base}/ops/run-pipeline-health", token=args.token)
        status = health.get("status", "unknown")
        blocking = health.get("blocking_errors", [])
        warnings = health.get("warnings", [])
        print(f"  pipeline health: {status}")
        print(f"  blocking errors: {len(blocking)}")
        print(f"  warnings: {len(warnings)}")

        worker_seen = health.get("worker", {}).get("heartbeat_seen", False)
        print(f"  worker heartbeat: {'seen' if worker_seen else 'NOT SEEN'}")

        or_key = health.get("providers", {}).get("openrouter", {}).get("key_present", False)
        print(f"  openrouter key: {'present' if or_key else 'MISSING'}")

        if status == "blocked":
            for e in blocking:
                print(f"  BLOCKING: {e.get('message', '')}")
            failed.append("pipeline_health_blocked")
        else:
            passed.append("pipeline_health")
    except SystemExit:
        failed.append("pipeline_health")
    except Exception as exc:
        print(f"  ERROR: {exc}", file=sys.stderr)
        failed.append("pipeline_health")

    # 2. LLM Smoke Test
    print("\n[2/4] Running LLM smoke test...")
    try:
        smoke_body: dict = {"provider": args.provider}
        if args.model_id:
            smoke_body["model_id"] = args.model_id
        smoke = _request("POST", f"{base}/ops/llm-smoke-test", token=args.token, body=smoke_body)
        if smoke.get("success"):
            latency = smoke.get("latency_ms", 0)
            print(f"  llm smoke: success, provider={smoke.get('provider')}, latency={latency:.0f}ms")
            passed.append("llm_smoke")
        else:
            print(f"  llm smoke: FAILED - {smoke.get('error_code')}: {smoke.get('message', '')}")
            failed.append("llm_smoke")
    except SystemExit:
        failed.append("llm_smoke")
    except Exception as exc:
        print(f"  ERROR: {exc}", file=sys.stderr)
        failed.append("llm_smoke")

    # 3. Create Debate
    print("\n[3/4] Creating test debate...")
    debate_id = None
    try:
        create_resp = _request("POST", f"{base}/debates", token=args.token, body={
            "prompt": "Reply with exactly: OK",
            "mode": "arena",
        })
        debate_id = create_resp.get("id")
        autorun = create_resp.get("autorun")
        dispatch_mode = create_resp.get("dispatch_mode")
        queue = create_resp.get("queue")
        warning = create_resp.get("warning")
        print(f"  debate id: {debate_id}")
        print(f"  autorun: {autorun}")
        print(f"  dispatch_mode: {dispatch_mode}")
        if queue:
            print(f"  queue: {queue}")
        if warning:
            print(f"  WARNING: {warning}")
        if debate_id:
            passed.append("debate_create")
        else:
            failed.append("debate_create")
    except SystemExit:
        failed.append("debate_create")
    except Exception as exc:
        print(f"  ERROR: {exc}", file=sys.stderr)
        failed.append("debate_create")

    # 4. Poll Status
    if debate_id:
        print(f"\n[4/4] Polling debate status (max {args.poll_timeout}s)...")
        terminal_statuses = {"completed", "completed_with_warnings", "failed", "cancelled", "degraded"}
        start = time.time()
        final_status = None
        while time.time() - start < args.poll_timeout:
            try:
                detail = _request("GET", f"{base}/debates/{debate_id}", token=args.token)
                final_status = detail.get("status")
                elapsed = time.time() - start
                print(f"  status: {final_status} (elapsed: {elapsed:.1f}s)")
                if final_status in terminal_statuses:
                    break
            except SystemExit:
                break
            except Exception as exc:
                print(f"  poll error: {exc}", file=sys.stderr)
            time.sleep(5)

        if final_status in ("completed", "completed_with_warnings"):
            print(f"  debate status: {final_status}")
            passed.append("debate_completed")
        elif final_status in ("failed", "degraded"):
            print(f"  debate status: {final_status}")
            failed.append("debate_failed")
        elif final_status == "cancelled":
            print(f"  debate was cancelled")
            failed.append("debate_cancelled")
        else:
            print(f"  debate stuck in status: {final_status}")
            failed.append("debate_stuck")
    else:
        print("\n[4/4] Skipped (no debate_id)")

    # Summary
    print("\n" + "=" * 50)
    if failed:
        print(f"FAIL ({len(failed)} failures: {', '.join(failed)})")
        sys.exit(1)
    else:
        print(f"PASS ({len(passed)} checks passed)")
        sys.exit(0)


if __name__ == "__main__":
    main()
