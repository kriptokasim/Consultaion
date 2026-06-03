# Observability & SLO Recommendations

To operate Consultaion as a reliable production SaaS, we must move from reactive debugging to proactive observability based on Service Level Objectives (SLOs).

## Proposed Service Level Indicators (SLIs)

### 1. API Availability
- **Definition:** Percentage of successful requests (HTTP 2xx, 3xx, 4xx where 4xx is expected user error) out of total requests to core endpoints (`/debates`, `/debates/{id}`).
- **Target SLO:** 99.9% uptime over a rolling 30-day window.

### 2. Debate Start Latency
- **Definition:** Time taken for `POST /debates/{id}/start` to successfully enqueue the run and return a 200 OK.
- **Target SLO:** 99th percentile (P99) < 500ms.

### 3. Model Response Latency (External Dependency)
- **Definition:** Time taken from worker dispatch to receiving the first token (TTFT) or full response from external LLM providers.
- **Target SLO:** Tracked per-provider. Example: OpenAI TTFT P95 < 2s. 
- *Note: External latency should not impact our internal Availability SLA, but must be tracked for routing decisions.*

### 4. Synthesis Success Rate
- **Definition:** Percentage of completed runs where `final_meta.synthesis_success` is true.
- **Target SLO:** 95% success rate. High failure rates indicate prompt engineering issues or provider instability.

## Infrastructure Observability Stack

### Distributed Tracing
- **Action:** Instrument FastAPI and Next.js with OpenTelemetry.
- **Goal:** Trace a user request from the Next.js frontend, through the FastAPI backend, to the Celery/ArQ worker, and out to the LLM provider.

### Structured Logging
- **Action:** Transition all `print()` and standard `logging` to JSON structured logs (e.g., structlog).
- **Format:** Include `trace_id`, `user_id`, `debate_id`, `team_id` on every log line to enable fast querying in Datadog/Grafana Loki.

### Dashboarding
Create a primary "Golden Signals" dashboard monitoring:
1. **Traffic:** Requests per second (RPS).
2. **Latency:** P50, P90, P99 request duration.
3. **Errors:** 5xx rate, specific LLM provider failure rates.
4. **Saturation:** Database connection pool utilization, Worker queue length.

## Incident Management
- Alert on SLO burn rate (e.g., alert if 5% of the 30-day error budget is burned in 1 hour).
- Define Runbooks for: Database connection exhaustion, Provider API outages, Worker queue backups.
