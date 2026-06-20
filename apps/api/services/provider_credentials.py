"""Provider Credential Resolver — decrypts user-provided API keys for model calls.

FH125 Track F: Supplies decrypted BYOK keys to the model gateway.
Each decryption is short-lived, scoped to the current call, and AAD-bound.
"""

import logging
from dataclasses import dataclass
from typing import Optional

from models import UserProviderKey
from sqlmodel import Session, select

logger = logging.getLogger(__name__)


@dataclass
class ResolvedProviderCredential:
    """A decrypted provider credential with metadata."""
    key: str
    source: str  # "user", "server", or "none"
    provider: str
    user_id: Optional[str] = None


def resolve_provider_credential(
    session: Session,
    user_id: str,
    provider: str,
) -> Optional[ResolvedProviderCredential]:
    """Resolve and decrypt a user's provider key.

    Returns ResolvedProviderCredential with source="user" if found,
    or None if no user key exists (caller falls back to server key).
    """
    stmt = select(UserProviderKey).where(
        UserProviderKey.user_id == user_id,
        UserProviderKey.provider == provider,
    )
    key_record = session.exec(stmt).first()
    if not key_record:
        return None

    # Reject legacy rows without encryption metadata
    if not key_record.encryption_nonce and key_record.encryption_key_version == 0:
        logger.warning(
            "Rejecting legacy unencrypted key: user_id=%s provider=%s",
            user_id, provider,
        )
        return None

    try:
        from security.encryption import decrypt_value
        decrypted = decrypt_value(
            {
                "ciphertext": key_record.encrypted_key,
                "nonce": key_record.encryption_nonce,
                "key_version": key_record.encryption_key_version,
            },
            user_id=user_id,
            provider=provider,
        )
        return ResolvedProviderCredential(
            key=decrypted,
            source="user",
            provider=provider,
            user_id=user_id,
        )
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
) -> Optional[ResolvedProviderCredential]:
    """Get API key for a provider, preferring user BYOK over server key."""
    if not user_id:
        return None

    credential = resolve_provider_credential(session, user_id, provider)
    if credential:
        return credential

    return None
