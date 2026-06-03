# Usage Dashboard Recommendations

To support the transition to a SaaS model, users need transparency into their usage, quotas, and limits.

## Dashboard Components

### 1. The Overview Widget
A persistent widget in the sidebar or top navigation indicating current quota health.
- **Free/BYOK Tier:** "3/10 Free Exports Used"
- **Pro Tier:** "Usage: $12.40 / $50.00 Limit"

### 2. Usage & Billing Page (`/settings/billing`)
A dedicated page containing:

#### Quota Bars
Visual progress bars for all metered metrics:
- Monthly Arena Runs (e.g., 45 / 100)
- Monthly Exports (e.g., 2 / 10)
- Team Seats (e.g., 3 / 5)

#### Credit Balance (If using Hosted Credits)
- Current credit balance.
- Option to "Top Up" or "Enable Auto-Reload".
- Estimated remaining queries (based on average historical prompt size).

#### API Key Management (BYOK)
- Clear UI showing which provider keys are valid, invalid, or missing.
- Warning badges if a provider's external quota is exhausted (requires syncing error states from the worker back to the UI).

### 3. In-App Interstitials
- **80% Warning:** Non-intrusive toast notification when a quota reaches 80%.
- **100% Blocker:** Hard block modal when attempting an action that exceeds quota, with a direct 1-click upgrade button.

## Technical Implementation
- Expand `billing/service.py` to expose a `GET /billing/usage` endpoint.
- Ensure the frontend caches this data globally (React Context or Zustand) to render the navigation widget without blocking page loads.
