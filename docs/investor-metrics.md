# Investor Metrics

This document outlines the critical tracking and reporting metrics for Consultaion's product-led growth (PLG) and venture-backable SaaS strategy.

## North Star Metric
**Weekly Shareable AI Decision Artifacts Created.**
An artifact is considered "created" when an Arena run successfully completes its synthesis phase and is either (a) marked public, (b) shared via link, or (c) revisited by the user within 7 days. This proves that the multi-model comparison provided lasting value beyond a single chat session.

## Activation Funnel
- **Public Run Views:** Number of unique visitors landing on a shared `/runs/[id]` page.
- **CTA Click-Through Rate:** Percentage of public run visitors who click "Run this prompt yourself".
- **Signup Started & Completed:** Conversion rate from CTA to authenticated session.
- **Composer Prefilled:** Number of users who successfully land in the dashboard with the prompt pre-populated.
- **Time to First Value (TTFV):** Time from signup completion to the successful synthesis of their first Arena run.

## PLG Funnel
- **Runs Shared:** Total number of runs transitioned from Private to Public.
- **Share Rate:** Percentage of completed runs that end up being shared.
- **Viral Coefficient (K-Factor):** Average number of new signups generated per shared run.

## Retention Metrics
- **Second Run Created:** Percentage of users who create a second run within 7 days of their first.
- **Weekly Active Users (WAU):** Users who complete at least one run per week.
- **Runs per Active User:** Average runs executed per active user per month.

## Revenue Metrics
- **Free-to-Paid Conversion:** Percentage of users upgrading to Pro or Team plans.
- **Upgrade Triggers Hit:** Count of users hitting the BYOK friction point or hosted-credit limit.
- **Gross Margin per Run:** Estimated cost of executing 4 model inference calls + 1 synthesis call vs the user's LTV.

## AI Quality Metrics
- **Model Failure Rate:** Frequency of timeout/429 errors from underlying providers (OpenAI, Anthropic, etc.).
- **Synthesis Failure Rate:** Frequency of the synthesizer model failing to parse the JSON format or timing out.
- **Median Run Latency:** End-to-end time from prompt submission to synthesis completion.

## Event Definitions (PostHog / Segment)
The following events are already instrumented via the `trackEvent` utility:
- `public_run_cta_clicked`
- `public_run_prompt_prefilled`
- `debate_run_started`
- `debate_run_error_generic`
- `quota_exceeded`
- `share_debate_enabled`

## Dashboard Requirements
To be investor-ready, the internal admin dashboard (or PostHog dashboard) must map these events into the following views:
1. **The PLG Loop:** A funnel chart tracking `Public View -> CTA Click -> Signup -> First Run -> Share Action`.
2. **The Cost Board:** A table tracking `Total Tokens Consumed per Model` vs `Active Subscriptions`.
3. **The Quality Board:** An uptime monitor showing `Provider Success Rates` and `Average Latency`.
