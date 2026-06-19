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

_metrics: Dict[str, int] = defaultdict(int)
_lock = Lock()
_METRICS_MAX = 1000


def increment_metric(name: str, value: int = 1) -> None:
    with _lock:
        if len(_metrics) >= _METRICS_MAX and name not in _metrics:
            return  # Drop new metric names when at capacity
        _metrics[name] += value


def get_metrics_snapshot() -> Dict[str, int]:
    with _lock:
        return dict(_metrics)
