# Trust Center & Security Practices

Welcome to the Consultaion Trust Center. We take the security, privacy, and reliability of your AI operations seriously.

## Data Privacy & Confidentiality

### 1. Your Data is Yours
We do not train models on your prompts, debate content, or uploaded data. We use enterprise API endpoints for all supported model providers (OpenAI, Anthropic, Google, etc.), which are bound by zero-retention and zero-training data processing agreements (DPAs).

### 2. Automatic PII Scrubbing
Consultaion features an integrated Personally Identifiable Information (PII) scrubber.
- Before a prompt is sent to any LLM, known PII patterns (emails, phone numbers, addresses, and names) are automatically redacted.
- This ensures that sensitive employee or customer data does not leave your infrastructure.

### 3. Public Sharing Safeguards
When you choose to share a run publicly via a link:
- **Redaction by Default:** We actively scan shared prompts for API keys, bearer tokens, and secrets. If detected, they are redacted from the public page and metadata.
- **Stripped Metadata:** Public runs expose only a safe subset of data. Internal model routing logic, user identities, and team affiliations are strictly excluded from public API responses.
- **No-Index Privacy:** Private runs, incomplete runs, and runs containing sensitive patterns are strictly hidden from search engines (`noindex, nofollow`).

## Infrastructure Security

### 1. Authentication & Authorization
- Secure JWT-based session management.
- Hardened mutation endpoints: Only the owner of a run (or a team editor) can start, share, export, or modify a run.
- Separation of concerns: Public read-only access is physically isolated from authenticated mutation operations.

### 2. Encryption
- **In Transit:** All communications between your browser, our servers, and third-party AI APIs are encrypted via TLS 1.2+.
- **At Rest:** Database volumes and sensitive fields (such as stored provider API keys) are encrypted at rest using industry-standard AES-256.

## Compliance & Subprocessors

*This section will be populated with our SOC2 status, GDPR compliance notes, and a full list of authorized subprocessors as we approach enterprise general availability.*
