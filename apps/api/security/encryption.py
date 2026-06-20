"""AES-256-GCM encryption for provider keys at rest.

FH125 Track F: Versioned keyring with AAD binding.

Configuration:
  PROVIDER_KEY_ENCRYPTION_KEYS={"1":"<base64-key>","2":"<base64-key>"}
  PROVIDER_KEY_ACTIVE_VERSION=2

Or legacy:
  PROVIDER_KEY_ENCRYPTION_KEY=<single-key>  (version 1)
"""

import base64
import hashlib
import json
import logging
import os

logger = logging.getLogger(__name__)


def _parse_keyring() -> dict[int, bytes]:
    """Parse versioned keyring from environment."""
    raw = os.environ.get("PROVIDER_KEY_ENCRYPTION_KEYS", "")
    if raw:
        try:
            data = json.loads(raw)
            return {int(k): base64.b64decode(v) for k, v in data.items()}
        except (json.JSONDecodeError, ValueError) as exc:
            raise RuntimeError(f"PROVIDER_KEY_ENCRYPTION_KEYS is invalid JSON: {exc}") from exc

    # Legacy: single key
    single = os.environ.get("PROVIDER_KEY_ENCRYPTION_KEY", "")
    if single:
        return {1: hashlib.sha256(single.encode()).digest()}

    return {}


def _get_active_version() -> int:
    return int(os.environ.get("PROVIDER_KEY_ACTIVE_VERSION", "1"))


def _get_key_for_version(version: int) -> bytes:
    """Get the encryption key for a specific version."""
    keyring = _parse_keyring()
    if version not in keyring:
        raise RuntimeError(f"No encryption key for version {version}. Available: {sorted(keyring.keys())}")
    key = keyring[version]
    if len(key) != 32:
        raise RuntimeError(f"Key version {version} must be exactly 32 bytes, got {len(key)}")
    return key


def _get_active_key() -> tuple[bytes, int]:
    """Get the active encryption key and version."""
    keyring = _parse_keyring()
    if not keyring:
        raise RuntimeError(
            "No provider key encryption configured. "
            "Set PROVIDER_KEY_ENCRYPTION_KEYS or PROVIDER_KEY_ENCRYPTION_KEY."
        )
    version = _get_active_version()
    return _get_key_for_version(version), version


def encrypt_value(plaintext: str, user_id: str = "", provider: str = "") -> dict:
    """Encrypt with AES-256-GCM using AAD binding.

    AAD binds ciphertext to (user_id, provider, key_version) —
    decryption with wrong context fails.
    """
    from cryptography.hazmat.primitives.ciphers.aead import AESGCM

    key, version = _get_active_key()
    nonce = os.urandom(12)

    # AAD: bind to user, provider, and key version
    aad = f"{user_id}:{provider}:{version}".encode()
    aesgcm = AESGCM(key)
    ciphertext = aesgcm.encrypt(nonce, plaintext.encode(), aad)

    return {
        "ciphertext": base64.b64encode(ciphertext).decode(),
        "nonce": base64.b64encode(nonce).decode(),
        "key_version": version,
    }


def decrypt_value(encrypted: dict, user_id: str = "", provider: str = "") -> str:
    """Decrypt with AES-256-GCM using AAD verification."""
    from cryptography.hazmat.primitives.ciphers.aead import AESGCM

    version = encrypted["key_version"]
    key = _get_key_for_version(version)
    nonce = base64.b64decode(encrypted["nonce"])
    ciphertext = base64.b64decode(encrypted["ciphertext"])

    aad = f"{user_id}:{provider}:{version}".encode()
    aesgcm = AESGCM(key)
    plaintext = aesgcm.decrypt(nonce, ciphertext, aad)
    return plaintext.decode()


def fingerprint_key(key: str) -> str:
    """Generate a short fingerprint for a key."""
    h = hashlib.sha256(key.encode()).hexdigest()
    return f"{key[-4:]}:{h[:8]}"


def validate_keyring() -> None:
    """Validate keyring at startup. Call once during app initialization."""
    keyring = _parse_keyring()
    if not keyring:
        logger.warning("No provider key encryption configured — BYOK disabled")
        return

    for ver, key in keyring.items():
        if len(key) != 32:
            raise RuntimeError(f"Key version {ver} must be 32 bytes, got {len(key)}")

    active = _get_active_version()
    if active not in keyring:
        raise RuntimeError(f"Active version {active} not in keyring (available: {sorted(keyring.keys())})")

    logger.info("Provider key encryption keyring validated: versions=%s active=%d", sorted(keyring.keys()), active)
