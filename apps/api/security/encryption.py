"""AES-256-GCM encryption for provider keys at rest.

FH125 D-2: Encrypts provider API keys before storing in the database.
Master key is read from PROVIDER_KEY_ENCRYPTION_KEY env var.
"""

import base64
import hashlib
import logging
import os
from typing import Optional

logger = logging.getLogger(__name__)

_VERSION = 1


def _get_master_key() -> bytes:
    """Derive a 32-byte AES key from the environment variable."""
    raw = os.environ.get("PROVIDER_KEY_ENCRYPTION_KEY", "")
    if not raw:
        raise RuntimeError(
            "PROVIDER_KEY_ENCRYPTION_KEY env var is required for provider key encryption. "
            "Generate one with: python -c \"import secrets; print(secrets.token_urlsafe(32))\""
        )
    return hashlib.sha256(raw.encode()).digest()


def encrypt_value(plaintext: str) -> dict:
    """Encrypt a plaintext string using AES-256-GCM.

    Returns dict with: ciphertext (base64), nonce (base64), key_version (int).
    """
    from cryptography.hazmat.primitives.ciphers.aead import AESGCM

    key = _get_master_key()
    nonce = os.urandom(12)  # 96-bit nonce for GCM
    aesgcm = AESGCM(key)
    ciphertext = aesgcm.encrypt(nonce, plaintext.encode(), None)

    return {
        "ciphertext": base64.b64encode(ciphertext).decode(),
        "nonce": base64.b64encode(nonce).decode(),
        "key_version": _VERSION,
    }


def decrypt_value(encrypted: dict) -> str:
    """Decrypt a value previously encrypted with encrypt_value.

    Args:
        encrypted: dict with ciphertext, nonce, key_version keys

    Returns:
        Decrypted plaintext string.
    """
    from cryptography.hazmat.primitives.ciphers.aead import AESGCM

    key = _get_master_key()
    nonce = base64.b64decode(encrypted["nonce"])
    ciphertext = base64.b64decode(encrypted["ciphertext"])
    aesgcm = AESGCM(key)
    plaintext = aesgcm.decrypt(nonce, ciphertext, None)
    return plaintext.decode()


def fingerprint_key(key: str) -> str:
    """Generate a short fingerprint for a key (last 4 chars + sha256 prefix)."""
    h = hashlib.sha256(key.encode()).hexdigest()
    return f"{key[-4:]}:{h[:8]}"
