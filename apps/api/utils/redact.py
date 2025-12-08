"""
Patchset 58.0: Logging Hygiene

Helper functions for redacting sensitive data from logs.
"""
from typing import Any, Dict, Set

SENSITIVE_KEYS: Set[str] = {
    "password",
    "token",
    "access_token",
    "refresh_token",
    "authorization",
    "cookie",
    "secret",
    "key",
    "api_key",
    "client_secret",
}

def redact_sensitive(data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Redact sensitive keys from a dictionary for safe logging.
    Recursively handles nested dictionaries.
    """
    if not isinstance(data, dict):
        return data
        
    redacted = {}
    for k, v in data.items():
        key_lower = str(k).lower()
        if key_lower in SENSITIVE_KEYS or any(s in key_lower for s in ["password", "token", "secret", "auth"]):
            redacted[k] = "[REDACTED]"
        elif isinstance(v, dict):
            redacted[k] = redact_sensitive(v)
        elif isinstance(v, list):
            # Simple list redaction: if items are dicts, redact them
            redacted[k] = [redact_sensitive(i) if isinstance(i, dict) else i for i in v]
        else:
            redacted[k] = v
            
    return redacted
