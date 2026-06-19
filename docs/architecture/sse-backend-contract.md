# SSE Backend Contract

## Overview

The SSE backend interface is a public protocol that all backend implementations must follow. Routes and services interact only through this interface.

## Base Protocol

```python
class BaseSSEBackend(ABC):
    async def create_channel(self, channel_id: str) -> None: ...
    async def publish(self, channel_id: str, event: DomainEvent) -> EventEnvelope: ...
    async def subscribe(self, channel_id: str, *, last_sequence: int | None) -> AsyncIterator[EventEnvelope]: ...
    async def replay(self, channel_id: str, *, after_sequence: int | None) -> list[EventEnvelope]: ...
    async def close_channel(self, channel_id: str) -> None: ...
    async def health(self) -> SSEBackendHealth: ...
```

## Anti-Patterns Eliminated

The following private attribute access patterns are no longer allowed:

- `hasattr(sse_backend, "_history")`
- `hasattr(sse_backend, "_redis")`
- `sse_backend._history`
- `sse_backend._redis`
- `sse_backend._lock`

## Implementations

| Backend | Storage | Use Case |
|---------|---------|----------|
| `MemorySSEBackend` | In-process dict | Testing, single-instance |
| `RedisSSEBackend` | Redis Pub/Sub | Production, multi-instance |

## Replay Capability

The `replay()` method provides event history access. Routes use this instead of accessing `_history` directly.

## Health Check

The `health()` method returns `SSEBackendHealth` with:
- `status`: "healthy" | "degraded" | "unhealthy"
- `backend_type`: "memory" | "redis"
- `latency_ms`: response time
