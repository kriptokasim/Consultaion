"""PS157 benchmark harness: deterministic arena latency measurement.

Records milestone timestamps for a simulated 4-model × 100-chunk arena run.

Usage:
    python scripts/ps157_benchmark.py [--redis] [--verbose]

Output:
    JSON report with per-milestone latencies in milliseconds.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import logging
import os
import sys
import time
import uuid

# Ensure apps/api is importable
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "apps", "api"))

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
logger = logging.getLogger(__name__)

MODEL_COUNT = 4
CHUNKS_PER_MODEL = 100
CHUNK_INTERVAL_S = 0.001  # 1 ms logical chunk interval
MODEL_IDS = [f"bench-model-{i}" for i in range(MODEL_COUNT)]
PROVIDERS = [f"bench-provider-{i}" for i in range(MODEL_COUNT)]
MODEL_FAMILIES = [f"bench-family-{i}" for i in range(MODEL_COUNT)]


async def run_benchmark(use_redis: bool = False) -> dict:
    from sse_backend import get_sse_backend, MemoryChannelBackend

    if use_redis:
        try:
            from sse_backend import RedisChannelBackend
            backend = RedisChannelBackend()
            logger.info("Using Redis backend")
        except Exception as e:
            logger.warning("Redis unavailable (%s), falling back to memory", e)
            backend = MemoryChannelBackend()
    else:
        backend = MemoryChannelBackend()

    debate_id = f"bench-{uuid.uuid4().hex[:12]}"
    channel = f"debate:{debate_id}"

    milestones: dict[str, float] = {
        "benchmark_started": time.monotonic(),
    }

    received_events: list[dict] = []
    first_by_model: dict[str, float] = {}
    completed_by_model: dict[str, float] = {}
    done = asyncio.Event()

    async def subscribe():
        async for event in backend.subscribe(channel):
            received_events.append(event)
            evt_type = event.get("type") or (event.get("payload") or {}).get("type", "")
            payload = event.get("payload", event)
            model_id = payload.get("model_id", "unknown")

            if evt_type == "model_response_delta":
                if model_id not in first_by_model:
                    first_by_model[model_id] = time.monotonic()
            elif evt_type in ("model_response_completed", "model_response_failed"):
                completed_by_model[model_id] = time.monotonic()
                if len(completed_by_model) >= MODEL_COUNT:
                    milestones["all_models_completed"] = time.monotonic()
                    done.set()

    sub_task = asyncio.create_task(subscribe())
    await asyncio.sleep(0.05)

    milestones["arena_started"] = time.monotonic()

    async def simulate_model(model_index: int):
        model_id = MODEL_IDS[model_index]
        provider = PROVIDERS[model_index]
        response_id = f"resp-{debate_id}-a1-g0-{model_id}-{uuid.uuid4().hex[:12]}"

        lifecycle_events = [
            {"type": "model_response_queued", "model_id": model_id, "provider": provider},
            {"type": "model_response_connecting", "model_id": model_id, "provider": provider},
            {"type": "model_response_started", "model_id": model_id, "provider": provider},
        ]
        for evt in lifecycle_events:
            await backend.publish(channel, evt)

        milestones[f"{model_id}_first_delta"] = time.monotonic()
        for seq in range(1, CHUNKS_PER_MODEL + 1):
            await asyncio.sleep(CHUNK_INTERVAL_S)
            await backend.publish(channel, {
                "type": "model_response_delta",
                "model_id": model_id,
                "provider": provider,
                "response_id": response_id,
                "text": f"chunk-{seq} ",
                "delta_sequence": seq,
                "accumulated_chars": seq * 7,
            })

        await backend.publish(channel, {
            "type": "model_response_persisting",
            "model_id": model_id,
            "provider": provider,
            "response_id": response_id,
        })
        await backend.publish(channel, {
            "type": "model_response_completed",
            "model_id": model_id,
            "provider": provider,
            "response_id": response_id,
            "success": True,
        })

    tasks = [simulate_model(i) for i in range(MODEL_COUNT)]
    await asyncio.gather(*tasks)

    milestones["publish_done"] = time.monotonic()
    await asyncio.wait_for(done.wait(), timeout=10.0)

    sub_task.cancel()
    try:
        await sub_task
    except (asyncio.CancelledError, Exception):
        pass

    now = time.monotonic()
    milestones["benchmark_ended"] = now

    # Compute deltas
    start = milestones["benchmark_started"]
    arena_start = milestones["arena_started"]
    deltas: dict[str, float] = {}

    for model_id in MODEL_IDS:
        if model_id in first_by_model:
            key = f"{model_id}_first_delta_latency_ms"
            deltas[key] = (first_by_model[model_id] - arena_start) * 1000

    for model_id in MODEL_IDS:
        if model_id in completed_by_model:
            key = f"{model_id}_total_ms"
            deltas[key] = (completed_by_model[model_id] - arena_start) * 1000

    if first_by_model:
        first_model = min(first_by_model.values())
        deltas["first_model_first_delta_ms"] = (first_model - arena_start) * 1000

    if completed_by_model:
        first_done = min(completed_by_model.values())
        last_done = max(completed_by_model.values())
        deltas["first_model_complete_ms"] = (first_done - arena_start) * 1000
        deltas["all_models_complete_ms"] = (last_done - arena_start) * 1000
        deltas["spread_ms"] = (last_done - first_done) * 1000

    total_ms = (milestones["benchmark_ended"] - milestones["benchmark_started"]) * 1000
    deltas["total_benchmark_ms"] = total_ms
    deltas["publish_to_last_complete_ms"] = (
        last_done - milestones.get("publish_done", last_done)
    ) * 1000 if "all_models_completed" in milestones else 0

    delta_events = [e for e in received_events if
                    (e.get("type") or (e.get("payload") or {}).get("type", "")) == "model_response_delta"]
    deltas["total_delta_events_received"] = len(delta_events)

    result = {
        "config": {
            "models": MODEL_COUNT,
            "chunks_per_model": CHUNKS_PER_MODEL,
            "chunk_interval_s": CHUNK_INTERVAL_S,
            "backend": "redis" if use_redis else "memory",
        },
        "milestones_ms": deltas,
        "total_events": len(received_events),
        "delta_events": len(delta_events),
    }

    return result


def main():
    parser = argparse.ArgumentParser(description="PS157 benchmark harness")
    parser.add_argument("--redis", action="store_true", help="Use Redis backend")
    parser.add_argument("--verbose", action="store_true", help="Print progress")
    parser.add_argument("--runs", type=int, default=3, help="Number of benchmark runs (default 3)")
    args = parser.parse_args()

    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)

    results = []
    for i in range(args.runs):
        logger.info("Benchmark run %d/%d", i + 1, args.runs)
        result = asyncio.run(run_benchmark(use_redis=args.redis))
        results.append(result)
        if args.verbose:
            print(json.dumps(result, indent=2))

    # Aggregate
    if args.runs > 1:
        agg = {"runs": results, "config": results[0]["config"]}
        keys = list(results[0]["milestones_ms"].keys())
        agg["avg"] = {}
        for key in keys:
            values = [r["milestones_ms"][key] for r in results]
            avg = sum(values) / len(values)
            agg["avg"][key] = round(avg, 2)
        print("\n=== Average ({} runs) ===".format(args.runs))
        print(json.dumps(agg["avg"], indent=2))
        print("\n=== Full results ===")
        print(json.dumps(agg, indent=2))
    else:
        print(json.dumps(results[0], indent=2))


if __name__ == "__main__":
    main()
