# Pricing Strategy & Monetization Model

This document defines the monetization framework for Consultaion to ensure a viable Gross Margin while enabling rapid Product-Led Growth (PLG).

## Core Philosophy
We must separate the value of our software (the orchestration, synthesis, and sharing workflows) from the cost of goods sold (COGS) of the underlying AI models. We are not selling API calls; we are selling the decision layer.

## The Margin Problem
A single "Arena Run" consumes roughly 5x the compute of a standard LLM chat:
- 4 concurrent model generation calls.
- 1 synthesis call (often using an advanced model like Claude 3.5 Sonnet or GPT-4o).
If we subsidize this for free users indiscriminately, COGS will scale linearly with growth, draining capital.

## The Three-Tier Strategy

### Tier 1: Free (The PLG Engine)
**Goal:** Maximize user acquisition and viral sharing without burning capital.
- **Hosted Credits:** Users receive a very limited number of "Hosted Runs" per month (e.g., 3-5). This allows them to experience the "Aha!" moment immediately.
- **BYOK (Bring Your Own Key):** Once hosted credits are exhausted, the user can continue using the platform for free by inputting their own OpenAI, Anthropic, or Google API keys.
- **Value Prop:** We offload the compute cost to the user while keeping them engaged in our ecosystem. The platform remains free to use, driving adoption among power users and developers.

### Tier 2: Pro (The Convenience Layer)
**Goal:** Monetize users who value convenience over cost management.
- **Price:** $20 - $30 / month.
- **Offering:** Unlimited (or highly capped, e.g., 500/month) hosted Arena runs.
- **Value Prop:** The user does not want to manage multiple API keys, track billing across three different providers, or hit rate limits. We provide a single, predictable subscription for multi-model access.
- **Margin Optimization:** We route less complex synthesis tasks to cheaper models (e.g., GPT-4o-mini or Claude 3 Haiku) to preserve margins on high-volume users.

### Tier 3: Team / Enterprise (The System of Record)
**Goal:** Capture organizational value and establish defensibility.
- **Price:** $50+ / user / month (or custom annual contracts).
- **Offering:** 
  - Shared workspaces for team decision-making.
  - Role-based access control (RBAC).
  - Single Sign-On (SSO) and audit logs.
  - Integration with internal knowledge bases (RAG).
  - Compliance and data retention policies (e.g., enforcing zero-data-retention API calls for sensitive data).
- **Value Prop:** Centralizing the company's AI usage. Instead of employees copying sensitive data into shadow-IT ChatGPT tabs, they use Consultaion, where administrators can monitor usage, enforce data privacy, and maintain a historical ledger of AI-assisted decisions.

## Conversion Triggers (Friction Points)
The platform is designed to naturally guide users toward the Pro or Team tiers:
1. **The API Key Wall:** When a free user exhausts their hosted credits, they are prompted to either add their API keys or upgrade to Pro. Many will choose Pro for simplicity.
2. **The Sharing Ceiling:** Free/BYOK users may be restricted in how long their shared links remain active (e.g., 30 days). Pro users get permanent link hosting.
3. **The Collaboration Wall:** When a user wants to invite a colleague to comment on or fork a decision artifact, they are prompted to upgrade to a Team workspace.

## Key Metrics for Iteration
- **Cost Per Run (CPR):** Must be actively monitored and optimized (e.g., through prompt caching or model routing).
- **BYOK Adoption Rate:** Indicates how sticky the UI/UX is when stripped of subsidized compute.
- **Payback Period:** How many months of a Pro subscription it takes to recover the Customer Acquisition Cost (CAC) + the subsidized compute cost of their Free trial period.
