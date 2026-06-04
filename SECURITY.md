# Security Policy & Vulnerability Disclosure

Consultaion handles user prompts, LLM traffic, and billing events. This document highlights key security controls and outlines our vulnerability reporting policy.

## Security Controls & Architecture

### Secrets & Environment Separation
* Use long, unique `JWT_SECRET` values in any non-local environment; defaults are rejected at startup in production.
* Enable Stripe webhook verification with a `STRIPE_WEBHOOK_SECRET` when billing is active.
* When `REQUIRE_REAL_LLM=1`, set at least one provider key (`OPENAI_API_KEY`, `ANTHROPIC_API_KEY`, `GEMINI_API_KEY`, etc.); the API will hard-fail without them in production.

### PII Scrubbing
* `ENABLE_PII_SCRUB` removes common PII (emails, phone numbers) from LLM message payloads before they leave the API process.
* Scrubbing runs on message content only and is designed to minimize leakage to external providers.

### Provider Health & Circuit Breaker
* The LLM provider/model circuit breaker tracks error rates over a sliding window and opens when thresholds are breached.
* While open, calls to that provider/model are short-circuited until the cooldown elapses.
* Admins can view provider health in the Ops console to understand which providers/models are degraded.

---

## Vulnerability Disclosure Policy

We take the security of our platform seriously. If you identify a security vulnerability, we appreciate your help in reporting it to us responsibly.

### Reporting a Vulnerability
Please do not open public issues for security vulnerabilities. Instead, report security issues directly to our security team:
* **Email:** security@consultaion.com
* Please include a detailed description of the vulnerability, steps to reproduce, and any proof of concept.

### Scope
Our security program covers the main application codebase, deployment configuration, and the Model Gateway APIs.

### Disclosure Guidelines
We request that you:
* Provide us with a reasonable amount of time to resolve the issue before disclosing it publicly.
* Avoid accessing, modifying, or deleting user data without authorization.
* Do not perform destructive attacks (such as DDoS) or social engineering.
