# Model Provider & AI Data Policy

Consultaion integrates with various third-party LLM providers to execute simulations, agent debates, and model comparisons. This document describes our provider integration policies and details how your prompt data is processed by these model APIs.

## 1. Sub-processors (Model Providers)
To generate agent debate responses, we transmit prompt inputs to the following sub-processors:

| Provider | Purpose | Primary Data Center Location | Data Policy Link |
| --- | --- | --- | --- |
| **OpenAI** | GPT-4o, GPT-4o-mini | United States | [OpenAI Business Terms](https://openai.com/policies/business-terms) |
| **Anthropic** | Claude 3.5 Sonnet | United States | [Anthropic Commercial Terms](https://www.anthropic.com/legal/commercial-terms) |
| **Google** | Gemini 1.5 Pro/Flash | United States / Global | [Google Cloud Vertex Terms](https://cloud.google.com/terms/service-terms) |
| **DeepSeek** | DeepSeek V3, Coder | China / Global | [DeepSeek Terms of Service](https://www.deepseek.com/) |

## 2. Training Exclusions
We access third-party models exclusively via their commercial APIs (developer endpoints). Under the commercial terms of our provider agreements:
* **No Training on Customer Prompts:** OpenAI, Anthropic, Google, and DeepSeek are contractually prohibited from using any prompt text or generated output submitted through our API keys to train or improve their models.
* **Transient Storage:** Most providers retain API payloads for a maximum of 30 days solely for security monitoring and abuse investigation (abuse audit logs), after which they are automatically deleted.

## 3. PII Scrubbing Safeguards
When the `ENABLE_PII_SCRUB` configuration is enabled in the Model Gateway:
* Outgoing prompt content is audited before it leaves the Consultaion server.
* Common personal identifiers (email addresses, phone numbers, IP addresses, credit card numbers) are automatically redacted/masked.
* This occurs in-memory in our API layer before transmission to external model provider endpoints.
