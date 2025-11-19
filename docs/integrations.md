# Integrations & Automations

## n8n Webhook Setup

1. Start n8n locally via Docker Compose:

```yaml
version: "3.8"
services:
  n8n:
    image: n8nio/n8n:latest
    restart: unless-stopped
    environment:
      N8N_BASIC_AUTH_ACTIVE: "true"
      N8N_BASIC_AUTH_USER: n8n
      N8N_BASIC_AUTH_PASSWORD: changeme
      N8N_HOST: localhost
      N8N_PORT: 5678
      WEBHOOK_URL: http://localhost:5678/
    ports:
      - "5678:5678"
    volumes:
      - ./n8n_data:/home/node/.n8n
```

2. Create a new **Webhook** node in n8n and copy the production URL. Paste it into `.env` as `N8N_WEBHOOK_URL`.
3. Trigger workflows using events emitted by the backend:
   - `subscription_activated`: fire Slack/email alerts and update CRM rows.
   - `usage_limit_nearing`: send upgrade nudges when 80% of plan limits are consumed.
   - `usage_limit_exceeded`: notify support or auto-open the billing modal.
4. Optional nightly workflow: use an HTTP node to call an internal admin usage endpoint (future) and email a report.
