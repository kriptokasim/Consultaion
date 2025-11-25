"""
API Key generation and validation utilities.

Provides secure key generation with bcrypt hashing and validation logic.

Patchset 37.0
"""

import secrets
from typing import Tuple

import bcrypt


def generate_api_key() -> Tuple[str, str, str]:
    """
    Generate a new API key with prefix and hashed value.
    
    Returns:
        Tuple of (full_key, prefix, hashed_key)
        - full_key: The complete secret to show user once (e.g., "pk_abc123def456...")
        - prefix: Short public identifier (e.g., "pk_abc123")
        - hashed_key: Bcrypt hash of the full key for storage
        
    Example:
        >>> full_key, prefix, hashed_key = generate_api_key()
        >>> full_key.startswith(prefix)
        True
    """
    # Generate random bytes and encode as URL-safe base64
    random_bytes = secrets.token_urlsafe(32)  # ~43 chars
    
    # Create key with "pk_" prefix
    full_key = f"pk_{random_bytes}"
    
    # Extract prefix (first 10 chars: "pk_" + 7 chars)
    prefix = full_key[:10]
    
    # Hash the full key with bcrypt
    hashed_key = bcrypt.hashpw(full_key.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")
    
    return full_key, prefix, hashed_key


def verify_api_key(full_key: str, hashed_key: str) -> bool:
    """
    Verify an API key against its stored hash.
    
    Args:
        full_key: The full API key to verify
        hashed_key: The stored bcrypt hash
        
    Returns:
        True if the key matches the hash, False otherwise
    """
    try:
        return bcrypt.checkpw(full_key.encode("utf-8"), hashed_key.encode("utf-8"))
    except Exception:
        return False


def extract_prefix(full_key: str) -> str:
    """
    Extract the prefix from a full API key.
    
    Args:
        full_key: The full API key
        
    Returns:
        The prefix (first 10 chars)
    """
    return full_key[:10] if len(full_key) >= 10 else full_key
