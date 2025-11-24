# Security Notes

Consultaion handles user prompts, LLM traffic, and billing events. This brief highlights the key controls and expectations when running the stack.

## Secrets & Environment Separation
- Use long, unique `JWT_SECRET` values in any non-local environment; defaults are rejected at startup in production.
- Enable Stripe webhook verification with a `STRIPE_WEBHOOK_SECRET` when billing is active.
- When `REQUIRE_REAL_LLM=1`, set at least one provider key (`OPENAI_API_KEY`, `ANTHROPIC_API_KEY`, `GEMINI_API_KEY`, etc.); the API will hard-fail without them in production.

## PII Scrubbing
- `ENABLE_PII_SCRUB` removes common PII (emails, phone numbers) from LLM message payloads before they leave the API process.
- Scrubbing runs on message content only and is designed to minimize leakage to external providers.

## Provider Health & Circuit Breaker
- The LLM provider/model circuit breaker tracks error rates over a sliding window and opens when thresholds are breached.
- While open, calls to that provider/model are short-circuited until the cooldown elapses.
- Admins can view provider health in the Ops console to understand which providers/models are degraded.

## Operational Recommendations
- Rotate secrets regularly and keep `.env` values distinct per environment.
- Monitor the admin Ops view for rate limit spikes and unhealthy providers.
- In production, run Redis-backed rate limiting and SSE, and point Celery workers to the configured queues (`DEBATE_FAST_QUEUE_NAME`, `DEBATE_DEEP_QUEUE_NAME`, `DEBATE_DEFAULT_QUEUE`).
