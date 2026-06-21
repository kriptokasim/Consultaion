# Model Gateway Keys

This document explains the canonical model key architecture for the Consultaion Model Gateway.

## Canonical Keys vs Aliases

To maintain a clean database and metric namespace, every model now has exactly ONE canonical key.

- **Canonical keys** explicitly reference the provider and model class (e.g. `openai_fast`, `gemini_general`, `anthropic_reasoning`).
- **Aliases** are backward-compatible identifiers (e.g. `gpt4o-mini`, `gemini-2-flash`).

### Best Practices

1. **Never persist aliases** to the database or send them in API telemetry.
2. **Always resolve keys** at the earliest entry point using `resolve_model_key()`.
3. If an alias is encountered, `resolve_model_key()` will log a deprecation warning but successfully return the canonical key.

## `FREE_ONLY_MODE`

The gateway now supports a `FREE_ONLY_MODE` (via config). When enabled, any resolved canonical key that does not have a `cost_class` strictly equal to `free` will be rejected with a `GatewayModelRestrictedError`.

This ensures we never silently route users to expensive models when building purely free features like the Coding Agent.

### Cost Classes

- `free`: Groq Llama, Gemini Flash, DeepInfra, Together, Fireworks
- `cheap`: OpenAI GPT-4o-mini
- `paid`: OpenAI GPT-4o, Anthropic Claude 3.5 Sonnet, Gemini Pro, Mistral Large, xAI Grok
- `unknown`: OpenRouter Fallbacks

## Checking Freshness

We maintain an active registry of model mappings and free tier constraints. To ensure our metadata stays accurate over time, you can run:

```bash
python scripts/check_model_freshness.py
```

This will alert if any models haven't been verified in >90 days or if a free model is missing source attribution for its cost classification.
