# Traction & Metrics Dashboard

This document details the tracking, metrics, and analytics visualization dashboard designed to measure product-led growth (PLG) and user activation loop traction for Consultaion.

## 1. Key Performance Indicators (KPIs)

To track business model viability and virality, the traction dashboard monitors:

*   **Conversion (Signups):** The percentage of visitors to public Arena runs who click the "Run this prompt yourself" CTA and register.
*   **Virality (K-Factor):** Calculated as `K = i * c` where `i` is the average number of invitations (shared run views) per user, and `c` is the conversion rate to signups.
*   **Activation Rate (Aha! Moment):** The percentage of new signups who execute their first Arena run within 24 hours.
*   **User Retention (WAU/MAU):** Monthly retention cohort tracking based on weekly active users (users creating at least one Arena run per week).
*   **Unit Economics (Gross Margin):** The average cost of API queries for hosted runs compared to the revenue per user.

---

## 2. Event Instrumentation Map

The following client-side and server-side events must be captured via PostHog or Segment:

| Event Name | Trigger | Properties Captured | Purpose |
| :--- | :--- | :--- | :--- |
| `public_run_viewed` | Public visitor lands on `/runs/[id]` | `debate_id`, `model_count`, `referrer` | Measure viral page visits |
| `public_run_cta_clicked` | Visitor clicks "Run this prompt yourself" | `debate_id`, `prompt_length` | Measure intent to activate |
| `signup_completed` | User successfully registers | `method` (Google/Email), `attribution_id` | Track new user signups |
| `debate_run_started` | User starts an Arena/Compare run | `debate_id`, `models`, `mode` | Track core value delivery |
| `run_shared` | User toggles run privacy to public | `debate_id`, `prompt_title` | Track virality action |

---

## 3. Analytics Dashboard Views (PostHog Configuration)

The following three dashboard panels must be set up in the analytics platform:

### A. The PLG Acquisition Funnel
Tracks the user acquisition journey from unauthenticated viewing to core loop participation:
1.  **Step 1:** `public_run_viewed` (Unique Visitors)
2.  **Step 2:** `public_run_cta_clicked` (Intent Click)
3.  **Step 3:** `signup_completed` (Conversion)
4.  **Step 4:** `debate_run_started` (First Value Delivered)

### B. Virality & Sharing Loop
*   **Total Shared Runs:** A time-series chart of `run_shared` events.
*   **Viral Referrals:** Number of visits where `referrer` matches a shared run URL.
*   **Attributed Signups:** Registrations where `attribution_id` is linked to a shared run.

### C. System Latency & Cost Board
*   **Error Rate:** Count of `debate_run_error_generic` vs successful runs.
*   **BYOK Key Health:** Successful vs failed runs for BYOK configurations.
*   **Hosted Credit Burn:** Total cost of hosted model queries per day/week.
