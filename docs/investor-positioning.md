# Consultaion Investor Positioning

## One-Liner
The decision layer for multi-model AI.

## Short Pitch
Consultaion runs your question across multiple leading AI models (GPT-4o, Claude, Gemini, DeepSeek), highlights where they agree or disagree, and synthesizes the strongest answer into a shareable decision artifact.

## Problem
Single-model AI answers are often confident, incomplete, or wrong. As models become commoditized, the value shifts from generating text to making high-stakes decisions. Currently, teams rely on copying and pasting between ChatGPT, Claude, and Gemini tabs to verify logic, leaving no audit trail or reusable artifact of *why* an AI decision was made.

## Why Now
1. **Model Parity:** No single AI model wins every benchmark anymore. The state-of-the-art changes weekly.
2. **Hallucination Fatigue:** Enterprises no longer trust single-model outputs for critical tasks.
3. **API Cost Collapse:** Inference costs have dropped dramatically, making it economically feasible to query 4-5 models simultaneously for a single user prompt.

## Solution
A multi-model AI decision workspace. Users submit one prompt, and Consultaion acts as an orchestration layer that queries the top models, forces them into a standardized format, and uses an independent synthesizer model to score, compare, and merge the outputs. The result is not a fleeting chat message, but a persistent, shareable decision artifact.

## Differentiation
Unlike a standard "LLM Wrapper" or chat interface, Consultaion creates a verifiable reasoning artifact. It does not try to be a better chatbot; it tries to be a better decision engine. By explicitly surfacing disagreement between models, it builds trust rather than blind reliance.

## Target Users
- **Product Managers & Strategists:** Comparing go-to-market strategies or product roadmaps.
- **Software Architects:** Evaluating technical trade-offs between databases or frameworks.
- **Researchers & Analysts:** Verifying facts across multiple distinct model training sets.

## Core Use Cases
1. **High-Stakes Decision Making:** "Should we use PostgreSQL or DynamoDB for this feature?"
2. **Adversarial Critique (Red Teaming):** "Tear apart this business plan."
3. **Creative Synthesis:** "Brainstorm 10 marketing angles."

## Product-Led Growth (PLG) Loop
1. **Create:** User runs a multi-model Arena comparison.
2. **Share:** User generates a public, read-only link to the synthesized decision artifact.
3. **Distribute:** The link is shared in Slack, Discord, or Twitter.
4. **Acquire:** Visitors view the artifact, see the value of multi-model synthesis, and click the "Run this prompt yourself" CTA.
5. **Activate:** Visitor signs up and drops into the composer with the prompt pre-filled.

## Business Model
B2B SaaS with a freemium PLG motion.
- **Free:** BYOK (Bring Your Own Key) access, or limited hosted credits (e.g., 3 free Arena runs).
- **Pro:** Monthly subscription for unlimited hosted Arena runs.
- **Team/Enterprise:** Shared workspace, SSO, audit trails, and organizational model policies.

## Defensibility
The moat is not the models; it is the workflow, the data, and the trust. By becoming the centralized workspace where a team's AI-assisted decisions are made, compared, and stored, Consultaion integrates into the system of record rather than remaining an isolated tool.

## Key Risks
- **Provider Policy Changes:** Over-reliance on Anthropic/OpenAI API terms of service.
- **Margin Compression:** Running 5 inferences per prompt is expensive if not monetized effectively.
- **UI Commoditization:** A major player (like Perplexity or OpenAI) could introduce a native multi-model comparison feature.

## Metrics Investors Will Ask For
- **Weekly Shareable Artifacts Created**
- **Share Rate (Public / Total Runs)**
- **Viral Coefficient (Signups per Shared Run)**
- **Free-to-Paid Conversion Rate**
