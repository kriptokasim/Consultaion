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
# Patchset 112 additions:
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

_metrics: Dict[str, int] = defaultdict(int)
_lock = Lock()


def increment_metric(name: str, value: int = 1) -> None:
    with _lock:
        _metrics[name] += value


def get_metrics_snapshot() -> Dict[str, int]:
    with _lock:
        return dict(_metrics)
