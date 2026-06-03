# Growth: Free Trial & Hosted Credits

To accelerate the Product-Led Growth (PLG) flywheel, Consultaion should transition from a strictly "Bring Your Own Key" (BYOK) model to a frictionless hosted credits model for onboarding.

## The Problem
Currently, a user signs up but must immediately provide API keys for OpenAI, Anthropic, etc., before experiencing the "Aha!" moment of comparing models side-by-side. This introduces massive friction and drop-off.

## Proposed Solution: The "Aha!" Trial

### 1. Hosted Credits Pool
- Provide new sign-ups with a small pool of "Consultaion Credits" (e.g., $1.00 USD worth of inference).
- Route trial queries through our own internal enterprise API keys for supported providers.

### 2. Frictionless First Run
- User clicks "Start your own Arena run" from a public shared link.
- They sign up via Google OAuth (1-click).
- They immediately land on the Arena prompt screen with models pre-selected (e.g., GPT-4o-mini, Claude 3.5 Haiku, Llama 3).
- They run the prompt using their free credits — reaching the "Aha!" moment in < 30 seconds.

### 3. Exhaustion & Upsell
- When credits are depleted (or nearing depletion), show a persistent CTA.
- **Path A (Pro):** Upgrade to a paid monthly tier that includes a larger pool of hosted credits.
- **Path B (BYOK):** Allow the user to input their own API keys to continue using the platform for free (with feature limits).

## Fraud Prevention Requirements
Hosted credits attract abuse. We must implement:
1. **Phone Verification (Optional but recommended):** Required to unlock free credits, preventing simple email-based Sybil attacks.
2. **Rate Limiting:** Strict daily IP and user-based limits on trial accounts.
3. **Cost Caps:** Hard limits on the internal routing tier to prevent a single user from running expensive Opus/GPT-4 queries that drain their trial in one click. Restrict trial tier to highly efficient models.

## Metrics to Track
- **Time to First Run (TTFR):** Target < 60 seconds from landing page.
- **Trial Conversion Rate:** Percentage of users who hit the credit limit and successfully add a credit card or API key.
- **Viral Coefficient (k-factor):** How many new trial users are generated per public shared run.
