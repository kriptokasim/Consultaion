# Hosted Credits MVP

This document outlines the design and enforcement mechanism for the Hosted Credits system, introducing monetization loops for the free trial tier.

## 1. Credit Allocation and Quotas
Every registered user starts with a free quota of hosted credits:
* **Default Free Plan**: Allocates `hosted_credits_limit = 10` upon signup.
* **Pro & Enterprise Plans**: Unlimited runs (not constrained by free hosted credits).
* **Credit Tracking**: Managed via three database columns on the `user` table:
  * `hosted_credits_limit`: Maximum number of runs the user can initiate using our hosted resources.
  * `hosted_credits_used`: Counter tracking how many runs have been executed.
  * `hosted_credit_source`: Metadata field (e.g. `"signup"`, `"promotion"`) tracking allocation context.

## 2. Enforcement Workflow
```mermaid
sequenceDiagram
    participant User as User
    participant Router as API Router (/debates POST)
    participant Database as Database
    
    User->>Router: POST New Run request
    Router->>Database: Fetch user plan and current credits
    alt User is Pro or Enterprise
        Router->>Database: Allow run without incrementing credits
        Router->>User: Success (Debate Created)
    else User is Free
        alt hosted_credits_used < hosted_credits_limit
            Router->>Database: Increment hosted_credits_used by 1
            Router->>User: Success (Debate Created)
        else hosted_credits_used >= hosted_credits_limit
            Router->>User: 400 Bad Request (hosted_credits.exhausted)
        end
    end
```

## 3. Failure Refund Policy
To ensure high quality and user satisfaction (vital for VC due diligence and PLG metrics):
* If a background run fails terminally during LLM execution (e.g., due to downstream LLM provider outages), the system automatically refunds the credit.
* The orchestrator's exception handling path queries the user and decrements `hosted_credits_used` by `1` (ensuring it never falls below `0`).
* Paid users (Pro/Enterprise) are unaffected by refund logic since their credits are not tracked/enforced.
