# API Access Documentation

**Patchset 37.0**

This document explains how to create and use API keys for programmatic access to the Consultaion platform.

---

## Overview

API keys allow you to authenticate requests to the Consultaion API without using browser cookies. This enables:

- **CLI tools** and scripts
- **CI/CD pipelines** and automation
- **Third-party integrations**
- **Server-to-server** communication

---

## Creating an API Key

### Via Web UI

1. Navigate to **Settings → API Access**
2. Click **"Create New Key"**
3. Enter a descriptive name (e.g., "CI Pipeline", "Local Development")
4. Click **"Generate Key"**
5. **Copy the secret immediately** - it will only be shown once!

### Via API

```bash
curl -X POST https://api.consultaion.com/keys \
  -H "Content-Type: application/json" \
  -H "Cookie: session=YOUR_SESSION_COOKIE" \
  -d '{"name": "My API Key"}'
```

Response:
```json
{
  "id": "550e8400-e29b-41d4-a716-446655440000",
  "name": "My API Key",
  "prefix": "pk_abc123",
  "created_at": "2025-11-25T12:00:00Z",
  "secret": "pk_abc123def456ghi789jkl012mno345pqr678stu901vwx234yz"
}
```

⚠️ **Important**: Store the `secret` securely. It cannot be retrieved later.

---

## Using API Keys

### Authentication Headers

API keys can be sent in two ways:

#### Option 1: Authorization Bearer (Recommended)

```bash
curl https://api.consultaion.com/debates \
  -H "Authorization: Bearer pk_abc123def456..."
```

#### Option 2: X-API-Key Header

```bash
curl https://api.consultaion.com/debates \
  -H "X-API-Key: pk_abc123def456..."
```

---

## Examples

### List Debates (curl)

```bash
export CONSULTAION_API_KEY="pk_abc123def456..."

curl https://api.consultaion.com/debates \
  -H "Authorization: Bearer $CONSULTAION_API_KEY"
```

### Create a Debate (curl)

```bash
curl -X POST https://api.consultaion.com/debates \
  -H "Authorization: Bearer $CONSULTAION_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "prompt": "Should we adopt a four-day work week?",
    "model_id": "gpt-4"
  }'
```

### JavaScript/TypeScript Example

```typescript
const CONSULTAION_API_KEY = process.env.CONSULTAION_API_KEY;

async function listDebates() {
  const response = await fetch('https://api.consultaion.com/debates', {
    headers: {
      'Authorization': `Bearer ${CONSULTAION_API_KEY}`,
    },
  });
  
  if (!response.ok) {
    throw new Error(`API error: ${response.status}`);
  }
  
  const data = await response.json();
  return data.items;
}

async function createDebate(prompt: string, modelId: string) {
  const response = await fetch('https://api.consultaion.com/debates', {
    method: 'POST',
    headers: {
      'Authorization': `Bearer ${CONSULTAION_API_KEY}`,
      'Content-Type': 'application/json',
    },
    body: JSON.stringify({ prompt, model_id: modelId }),
  });
  
  if (!response.ok) {
    throw new Error(`API error: ${response.status}`);
  }
  
  return response.json();
}
```

### Python Example

```python
import os
import requests

CONSULTAION_API_KEY = os.getenv('CONSULTAION_API_KEY')
API_BASE = 'https://api.consultaion.com'

def list_debates():
    response = requests.get(
        f'{API_BASE}/debates',
        headers={'Authorization': f'Bearer {CONSULTAION_API_KEY}'}
    )
    response.raise_for_status()
    return response.json()['items']

def create_debate(prompt, model_id='gpt-4'):
    response = requests.post(
        f'{API_BASE}/debates',
        headers={'Authorization': f'Bearer {CONSULTAION_API_KEY}'},
        json={'prompt': prompt, 'model_id': model_id}
    )
    response.raise_for_status()
    return response.json()

# Usage
debates = list_debates()
new_debate = create_debate("Should we adopt a four-day work week?")
print(f"Created debate: {new_debate['id']}")
```

---

## Managing API Keys

### List Your Keys

```bash
curl https://api.consultaion.com/keys \
  -H "Authorization: Bearer $CONSULTAION_API_KEY"
```

Response:
```json
[
  {
    "id": "550e8400-e29b-41d4-a716-446655440000",
    "name": "CI Pipeline",
    "prefix": "pk_abc123",
    "created_at": "2025-11-25T12:00:00Z",
    "last_used_at": "2025-11-25T14:30:00Z",
    "revoked": false,
    "team_id": null
  }
]
```

### Revoke a Key

```bash
curl -X DELETE https://api.consultaion.com/keys/550e8400-e29b-41d4-a716-446655440000 \
  -H "Authorization: Bearer $CONSULTAION_API_KEY"
```

Once revoked, the key can no longer be used for authentication.

---

## Security Best Practices

### ✅ Do

- **Store keys in environment variables** or secure vaults (e.g., AWS Secrets Manager, HashiCorp Vault)
- **Use separate keys** for different environments (dev, staging, prod)
- **Revoke unused keys** immediately
- **Rotate keys periodically** (e.g., every 90 days)
- **Use descriptive names** to track key usage

### ❌ Don't

- **Never commit keys to source control** (add to `.gitignore`)
- **Don't share keys** between team members (create individual keys)
- **Don't log keys** in application logs
- **Don't expose keys** in client-side code (browser JavaScript)

### Example: Environment Variables

```bash
# .env file (add to .gitignore!)
CONSULTAION_API_KEY=pk_abc123def456...
```

```javascript
// Load from environment
const apiKey = process.env.CONSULTAION_API_KEY;
```

---

## Rate Limits & Billing

API keys are subject to the same rate limits and billing quotas as your account:

- **Free Plan**: 10 debates/hour
- **Pro Plan**: 100 debates/hour
- **Enterprise**: Custom limits

When you hit a rate limit, the API returns:

```json
{
  "error": {
    "code": "rate_limit.exceeded",
    "message": "Rate limit exceeded",
    "details": {
      "detail": "You have reached 10 debates in the last 1 hour",
      "reset_at": "2025-11-25T15:00:00Z"
    }
  }
}
```

HTTP Status: `429 Too Many Requests`

---

## Troubleshooting

### Invalid API Key

**Error**: `401 Unauthorized` with `auth.invalid_api_key`

**Solutions**:
- Verify the key is correct (check for typos)
- Ensure the key hasn't been revoked
- Check that you're using the full secret (not just the prefix)

### Rate Limit Exceeded

**Error**: `429 Too Many Requests`

**Solutions**:
- Wait until the `reset_at` time
- Upgrade your plan for higher limits
- Implement exponential backoff in your client

### Permission Denied

**Error**: `403 Forbidden`

**Solutions**:
- Verify the key owner has access to the resource
- Check team membership if accessing team resources

---

## API Reference

For complete API documentation, see:
- [API Reference](https://docs.consultaion.com/api)
- [OpenAPI Spec](https://api.consultaion.com/openapi.json)

---

## Support

Need help? Contact us:
- **Email**: support@consultaion.com
- **Discord**: [Join our community](https://discord.gg/consultaion)
- **GitHub**: [Report issues](https://github.com/consultaion/consultaion/issues)
