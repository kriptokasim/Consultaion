"""PS155.6 — Performance benchmarks for delta coalescing, fencing, and checkpoints."""
from __future__ import annotations

import asyncio
import os
import random
import sys
import time
from pathlib import Path

# Add project root to sys.path so we can import orchestrator, models, etc.
sys.path.append(str(Path(__file__).resolve().parents[1]))

# Disable logging to avoid cluttering benchmark output
import logging

logging.disable(logging.CRITICAL)

# Delete temp benchmark db if it exists to ensure a clean schema creation
for f in ["./benchmark_temp.db", "./benchmark_temp.db-journal"]:
    if os.path.exists(f):
        try:
            os.remove(f)
        except Exception:
            pass

# Set test environment defaults to SQLite
os.environ["DATABASE_URL"] = "sqlite:///./benchmark_temp.db"
os.environ["DATABASE_URL_ASYNC"] = "sqlite+aiosqlite:///./benchmark_temp.db"
os.environ["ENV"] = "test"
os.environ["JWT_SECRET"] = "test-secret"
os.environ["USE_MOCK"] = "1"
os.environ["SSE_BACKEND"] = "memory"

from database import init_db, reset_engine  # noqa: E402
from database_async import async_session_scope, reset_async_engine  # noqa: E402
from models import Debate, DebateStageCheckpoint  # noqa: E402

from config import settings  # noqa: E402

# Force reload config settings and reset engines to SQLite
settings.reload()
reset_engine()
reset_async_engine()
init_db()

from orchestration.checkpoints import run_with_checkpoint  # noqa: E402
from orchestrator import _try_acquire_lease  # noqa: E402
from sse_backend import DeltaCoalescer  # noqa: E402


def benchmark_delta_coalescing():
    print("\n=== Benchmark 1: Delta Coalescing Throughput ===")
    
    # Simulate a typical debate output of 500 tokens/deltas
    num_deltas = 500
    
    # 1. Without coalescing (each event is emitted individually)
    start_time = time.perf_counter()
    emitted_count_raw = 0
    for i in range(num_deltas):
        event = {
            "type": "model_response_delta",
            "payload": {
                "response_id": "res_1",
                "text": "word ",
                "accumulated_chars": i * 5,
                "delta_sequence": i,
            }
        }
        emitted_count_raw += 1
    duration_raw = time.perf_counter() - start_time
    print(f"Without coalescing: Processed {num_deltas} events. Emitted {emitted_count_raw} events. Time: {duration_raw:.5f}s ({num_deltas/duration_raw:.1f} events/sec)")

    # 2. With coalescing (using DeltaCoalescer with 150ms flush window)
    coalescer = DeltaCoalescer(flush_interval_ms=150)
    start_time = time.perf_counter()
    emitted_count_coalesced = 0
    
    for i in range(num_deltas):
        event = {
            "type": "model_response_delta",
            "payload": {
                "response_id": "res_1",
                "text": "word ",
                "accumulated_chars": i * 5,
                "delta_sequence": i,
            }
        }
        # Ingest
        res = coalescer.ingest(event)
        emitted_count_coalesced += len(res)
        
    # Flush whatever is left
    res = coalescer.flush_all()
    emitted_count_coalesced += len(res)
    
    duration_coalesced = time.perf_counter() - start_time
    print(f"With coalescing:    Processed {num_deltas} events. Emitted {emitted_count_coalesced} events. Time: {duration_coalesced:.5f}s ({num_deltas/duration_coalesced:.1f} events/sec)")
    reduction = (1 - (emitted_count_coalesced / emitted_count_raw)) * 100
    print(f"--> Event rate reduced by {reduction:.2f}%!")


async def benchmark_checkpoint_latency():
    print("\n=== Benchmark 2: Checkpoint Transition Latency ===")
    
    num_iterations = 50
    debate_id = "benchmark-checkpoint-debate"
    owner_id = "worker-bench-1"
    
    # Prep debate
    async with async_session_scope() as session:
        # Clear existing
        existing = await session.get(Debate, debate_id)
        if existing:
            await session.delete(existing)
            await session.commit()
            
        debate = Debate(id=debate_id, prompt="Benchmarking checkpoints", status="running", lease_epoch=1)
        session.add(debate)
        await session.commit()
        
    latencies = []
    
    for i in range(num_iterations):
        stage_key = f"stage_{i}"
        input_data = {"test": f"val_{i}"}
        
        async def dummy_run(_i=i):
            return {"output": f"res_{_i}"}
            
        async def dummy_load(data):
            return data
            
        t0 = time.perf_counter()
        # Perform checkpoint transition
        await run_with_checkpoint(
            debate_id=debate_id,
            stage_key=stage_key,
            input_data=input_data,
            run_fn=dummy_run,
            load_fn=dummy_load,
            owner_id=owner_id
        )
        latencies.append(time.perf_counter() - t0)
        
    avg_latency = (sum(latencies) / num_iterations) * 1000
    print(f"Average checkpoint transition latency: {avg_latency:.2f}ms over {num_iterations} runs")
    
    # Cleanup
    async with async_session_scope() as session:
        db_debate = await session.get(Debate, debate_id)
        if db_debate:
            await session.delete(db_debate)
        # also delete checkpoints
        from sqlmodel import select
        chk_res = await session.execute(select(DebateStageCheckpoint).where(DebateStageCheckpoint.debate_id == debate_id))
        for chk in chk_res.scalars().all():
            await session.delete(chk)
        await session.commit()


async def benchmark_lease_contention():
    print("\n=== Benchmark 3: Lease Acquisition Contention ===")
    
    debate_id = "benchmark-lease-contention-debate"
    num_concurrent_workers = 30
    
    # Setup debate record
    async with async_session_scope() as session:
        existing = await session.get(Debate, debate_id)
        if existing:
            await session.delete(existing)
            await session.commit()
            
        debate = Debate(id=debate_id, prompt="Benchmarking lease contention", status="queued", lease_epoch=0)
        session.add(debate)
        await session.commit()
        
    # Generate multiple unique runner IDs trying to lease concurrently
    runners = [f"runner-{i}-{random.randint(1000, 9999)}" for i in range(num_concurrent_workers)]
    
    t0 = time.perf_counter()
    # Execute all try_acquire_lease calls concurrently
    results = await asyncio.gather(*[_try_acquire_lease(debate_id, r) for r in runners])
    duration = time.perf_counter() - t0
    
    successful_leases = [res for res in results if res[0] is True]
    failed_leases = [res for res in results if res[0] is False]
    
    print(f"Lease contention under {num_concurrent_workers} concurrent requests:")
    print(f"  Total time: {duration:.5f}s")
    print(f"  Successful lease acquisitions: {len(successful_leases)}")
    print(f"  Rejected lease acquisitions:   {len(failed_leases)}")
    
    if len(successful_leases) > 0:
        print(f"  Final epoch after burst:       {successful_leases[0][1]}")
        
    # Cleanup
    async with async_session_scope() as session:
        db_debate = await session.get(Debate, debate_id)
        if db_debate:
            await session.delete(db_debate)
            await session.commit()


async def main():
    benchmark_delta_coalescing()
    await benchmark_checkpoint_latency()
    await benchmark_lease_contention()

    # Dispose engines to avoid keeping event loop running
    from database import engine
    from database_async import async_engine
    engine.dispose()
    await async_engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
