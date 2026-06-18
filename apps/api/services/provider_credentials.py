"""Provider Credential Resolver — decrypts user-provided API keys for model calls.

FH125: Supplies decrypted BYOK keys to the model gateway without caching
plaintext globally. Each decryption is short-lived and scoped to the current call.
"""

import logging
from typing import Optional

from sqlmodel import Session, select

from models import UserProviderKey

logger = logging.getLogger(__name__)


def resolve_provider_key(
    session: Session,
    user_id: str,
    provider: str,
) -> Optional[str]:
    """Resolve and decrypt a user's provider key for the given provider.

    Returns the decrypted key string, or None if not found.
    Never logs the key value. Never caches plaintext globally.
    """
    stmt = select(UserProviderKey).where(
        UserProviderKey.user_id == user_id,
        UserProviderKey.provider == provider,
    )
    key_record = session.exec(stmt).first()
    if not key_record:
        return None

    try:
        from security.encryption import decrypt_value
        return decrypt_value({
            "ciphertext": key_record.encrypted_key,
            "nonce": key_record.encryption_nonce,
            "key_version": key_record.encryption_key_version,
        })
    except Exception as exc:
        logger.warning(
            "Failed to decrypt provider key: user_id=%s provider=%s error=%s",
            user_id, provider, type(exc).__name__,
        )
        return None


def get_model_api_key(
    session: Session,
    user_id: Optional[str],
    provider: str,
) -> Optional[str]:
    """Get the API key for a provider, preferring user's BYOK key over server key.

    This is the main entry point for model gateway integration.
    Returns the decrypted user key if available, otherwise None (caller falls back to server key).
    """
    if not user_id:
        return None

    user_key = resolve_provider_key(session, user_id, provider)
    if user_key:
        return user_key

    return None
