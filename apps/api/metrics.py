from collections import defaultdict
from threading import Lock
from typing import Dict

# Standardized Metric Names (Patchset 107 + 112)
#
# Debate lifecycle:
# - debate.started
# - debate.completed
# - debate.failed
# - debate.degraded
#
# SSE:
# - sse.stream.opened
# - sse.stream.closed
# - sse.publish.failed
# - sse.publish.degraded
#
# Rate limiting:
# - rate_limit.triggered
#
# Mode usage (matches Debate.mode values: conversation, compare, debate):
# - mode.conversation.started
# - mode.compare.started
# - mode.debate.started
#
# Redis pool:
# - redis.pool.sync.created
# - redis.pool.async.created
# - redis.pool.sync.failed
# - redis.pool.async.failed
#
# Timeline/hydration:
# - timeline.fetch.slow  (>500ms)
# - timeline.fetch.ok
#
# - sse.lease.acquired
# - sse.lease.denied
# - sse.lease.released
# - sse.lease.release_failed
# - sse.lease.expired
# - sse.heartbeat.emitted
# - sse.backpressure.dropped
# - sse.backpressure.coalesced
# - sse.backpressure.overflow
# - sse.backpressure.slow_subscriber
# - sse.backpressure.critical_enqueue_failed

# Coding Agent:
# - coding.lane_latency_ms
# - coding.early_exit_rate
# - coding.lane_failure_count
# - coding.judge_invoked_count
# - coding.free_only_block_count

_metrics: Dict[str, int] = defaultdict(int)
_lock = Lock()
_METRICS_MAX = 1000


def increment_metric(name: str, value: int = 1) -> None:
    with _lock:
        if len(_metrics) >= _METRICS_MAX and name not in _metrics:
            return  # Drop new metric names when at capacity
        _metrics[name] += value

# Aliases for newer code
def incr_metric(name: str, value: int = 1, tags: Dict[str, str] = None) -> None:
    # We ignore tags for now in the simple dict backend, just append them to the name
    if tags:
        tag_str = ",".join(f"{k}={v}" for k, v in tags.items())
        name = f"{name}[{tag_str}]"
    increment_metric(name, value)

def record_timer(name: str, value_ms: float, tags: Dict[str, str] = None) -> None:
    if tags:
        tag_str = ",".join(f"{k}={v}" for k, v in tags.items())
        name = f"{name}[{tag_str}]"
    # Basic aggregate: we just store the count for now in this simple metrics module
    increment_metric(f"{name}_count", 1)

def get_metrics_snapshot() -> Dict[str, int]:
    with _lock:
        return dict(_metrics)

