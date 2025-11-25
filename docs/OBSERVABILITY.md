# Observability & Logging

Consultaion uses structured logging and telemetry to provide visibility into system behavior, performance, and health.

## Logging

### Format
- **Local Development**: Human-readable logs with timestamps and request IDs.
- **Production/Staging**: JSON-structured logs for ingestion by tools like Datadog, CloudWatch, or ELK.

### Configuration
Logging is configured in `apps/api/log_config.py`. The format is automatically selected based on `IS_LOCAL_ENV`.

### Structured Events
Critical lifecycle events are logged with the `log_event` helper, producing structured JSON payloads.

**Key Events:**
- `debate.created`: When a new debate is initialized.
- `debate.started_manually`: When a user manually triggers a debate run.
- `billing.usage.increment`: When usage quotas (debates, exports, tokens) are consumed.
- `billing.limit_exceeded`: When a user hits a plan limit.
- `rate_limit.exceeded`: When an API rate limit is hit.
- `circuit_breaker.opened`: When an LLM provider is marked as unhealthy.

## Telemetry

### Admin Ops
The Admin Ops dashboard (`/admin/ops`) provides real-time visibility into:
- **Provider Health**: Error rates and circuit breaker status for each LLM provider/model.
- **Rate Limits**: Recent 429 events and Redis backend status.
- **System Health**: Database connectivity and SSE backend status.

### Performance
- **Exports**: Heavy export operations (CSV/Markdown) run in a thread pool to avoid blocking the main event loop.
- **Dashboard**: High-traffic counts (e.g., total debates) are cached in Redis (TTL 30s) to reduce database load.

## Troubleshooting

### Missing Logs?
Ensure `LOG_LEVEL` is set correctly (default: INFO).

### Rate Limit Issues?
Check `RATE_LIMIT_BACKEND` setting. If `redis`, ensure `REDIS_URL` is reachable.
View recent 429s in the Admin Ops dashboard.

### Provider Errors?
Check the "Runtime signals" section in Admin Ops. If a circuit is open, it will automatically close after the cooldown period (default: 60s).
