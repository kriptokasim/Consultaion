# Consultaion Investor KPI Dashboard Specification

## Objective

Create one canonical dashboard that proves product usage, retention, virality, reliability and unit economics. The dashboard should be reviewable weekly and exportable as a point-in-time diligence snapshot.

## North-star metric

**Weekly Shareable AI Decision Artifacts Created**

Count a decision artifact when an Arena/Debate run reaches durable synthesis and is either shared/public or revisited within seven days.

## Activation funnel

Track the following ordered funnel:

1. Landing/demo viewed
2. Prompt submitted
3. Arena/Debate run started
4. First model response visible
5. Synthesis completed
6. Decision artifact viewed
7. Share/public action
8. Public artifact viewed by another visitor
9. “Run this prompt yourself” CTA clicked
10. Signup completed
11. First authenticated run completed

Required metrics:

- landing → prompt submission rate
- prompt → successful synthesis rate
- signup → first-value conversion
- median time to first value

## Retention

- WAU
- MAU
- WAU/MAU
- second run within 7 days
- 4-week retained-user rate
- runs per active user
- decision artifacts revisited within 7/30 days

## Virality / PLG loop

- completed runs
- shareable artifacts created
- share rate
- unique public artifact viewers
- CTA click-through from public artifacts
- signups attributed to shared artifacts
- viral coefficient / signups per shared artifact

## Revenue

- active free users
- active BYOK users
- active Pro users
- team/enterprise seats
- free → paid conversion
- MRR / ARR when applicable
- ARPU / ARPA
- churn / expansion when applicable

## Unit economics

Every completed hosted run should produce or be attributable to:

- input tokens by model
- output tokens by model
- provider/model
- provider cost estimate
- synthesis cost estimate
- total hosted COGS
- plan/revenue attribution
- contribution-margin estimate

Dashboard metrics:

- median cost/run
- p90 cost/run
- cost/run by mode
- cost/run by plan
- cost/run by model mix
- hosted vs BYOK share
- gross-margin estimate by plan

## Reliability / product quality

- model response success rate
- provider failure rate
- timeout rate
- 429/rate-limit rate
- synthesis failure rate
- median time to first token
- median model completion time
- median synthesis completion time
- median end-to-end run latency
- percentage of runs completing with warnings/degraded quorum

## Suggested event taxonomy

### Acquisition / activation

- `landing_viewed`
- `demo_viewed`
- `prompt_submitted`
- `signup_started`
- `signup_completed`
- `first_authenticated_run_completed`

### Core run lifecycle

- `debate_run_started`
- `model_response_started`
- `model_response_completed`
- `model_response_failed`
- `synthesis_started`
- `synthesis_completed`
- `synthesis_failed`
- `run_completed_with_warnings`

### PLG / sharing

- `share_debate_enabled`
- `public_run_viewed`
- `public_run_cta_clicked`
- `public_run_prompt_prefilled`

### Monetization

- `hosted_credit_consumed`
- `quota_exceeded`
- `byok_key_added`
- `upgrade_clicked`
- `checkout_started`
- `subscription_activated`
- `subscription_cancelled`

## Required dimensions

Attach where applicable:

- `user_id` / anonymous session id
- `team_id`
- `debate_id` / run id
- `mode`
- `plan`
- `provider`
- `model_id`
- `credential_scope` (`hosted` / `byok`)
- `is_public`
- `source` / acquisition channel
- `release_sha`

Do not include provider API keys, prompts containing sensitive data, or raw hidden model reasoning in analytics properties.

## Dashboard views

### Board A — Investor snapshot

- WAU
- second-run rate
- share rate
- public-view → signup conversion
- paid users / MRR
- median cost/run
- gross-margin estimate

### Board B — PLG loop

`Public View → CTA → Signup → First Run → Share`

### Board C — Economics

Model/provider costs, hosted/BYOK mix, plan usage and margin.

### Board D — Reliability

Provider success, timeout/429 rate, synthesis failures and latency percentiles.

## Weekly export

Generate a dated investor snapshot with:

- current values
- previous-week values
- week-over-week delta
- short explanation for major movements
- exact analytics query/dashboard version

This snapshot should become part of the data room after real usage begins.
