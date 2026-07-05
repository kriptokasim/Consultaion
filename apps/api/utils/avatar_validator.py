"""Hardened avatar URL validation.

Patchset 148 D1: Centralized validator that blocks SSRF-dangerous URLs
including private/loopback/link-local/CGNAT/metadata IPs, dangerous schemes,
and known local hostnames.
"""
from __future__ import annotations

import ipaddress
import logging
from urllib.parse import urlparse

logger = logging.getLogger(__name__)

MAX_AVATAR_URL_LENGTH = 512

BLOCKED_HOSTNAMES = frozenset({
    "localhost",
    "metadata.google.internal",
    "metadata.internal",
})

DANGEROUS_SCHEMES = frozenset({
    "javascript",
    "data",
    "file",
    "vbscript",
    "about",
    "blob",
})

# RFC1918 + loopback + link-local + CGNAT + metadata
_BLOCKED_NETWORKS = [
    ipaddress.ip_network("127.0.0.0/8"),       # IPv4 loopback
    ipaddress.ip_network("10.0.0.0/8"),         # RFC1918
    ipaddress.ip_network("172.16.0.0/12"),      # RFC1918
    ipaddress.ip_network("192.168.0.0/16"),     # RFC1918
    ipaddress.ip_network("169.254.0.0/16"),     # Link-local
    ipaddress.ip_network("100.64.0.0/10"),      # CGNAT
    ipaddress.ip_network("::1/128"),            # IPv6 loopback
    ipaddress.ip_network("fe80::/10"),          # IPv6 link-local
    ipaddress.ip_network("fc00::/7"),           # IPv6 unique-local (private)
    ipaddress.ip_network("fd00::/8"),           # IPv6 private
]


def _is_blocked_ip(host: str) -> bool:
    """Check if a hostname is a literal IP in a blocked range."""
    try:
        addr = ipaddress.ip_address(host.strip("[]"))
    except ValueError:
        return False
    return any(addr in net for net in _BLOCKED_NETWORKS)


def _is_metadata_ip(host: str) -> bool:
    """Check for well-known cloud metadata service IPs."""
    try:
        addr = ipaddress.ip_address(host.strip("[]"))
    except ValueError:
        return False
    metadata_addrs = [
        ipaddress.ip_address("169.254.169.254"),  # AWS/GCP/Azure metadata
    ]
    return addr in metadata_addrs


def validate_avatar_url(value: str | None, *, allow_http: bool = False) -> str | None:
    """Validate and normalize an avatar URL.

    Args:
        value: Raw URL string or None.
        allow_http: If True, allow http:// scheme (for local/test environments).
                    Default False — only https:// is allowed.

    Returns:
        Cleaned URL or None (if empty/whitespace).

    Raises:
        ValueError: If the URL is invalid or blocked.
    """
    if value is None:
        return None

    cleaned = value.strip()
    if not cleaned:
        return None

    # Length cap
    if len(cleaned) > MAX_AVATAR_URL_LENGTH:
        raise ValueError(
            f"Avatar URL must be at most {MAX_AVATAR_URL_LENGTH} characters "
            f"(got {len(cleaned)})"
        )

    # Protocol-relative URLs
    if cleaned.startswith("//"):
        raise ValueError("Protocol-relative URLs are not allowed for avatar URLs")

    parsed = urlparse(cleaned)

    # Scheme validation
    scheme = (parsed.scheme or "").lower()

    if scheme in DANGEROUS_SCHEMES:
        raise ValueError(f"Scheme '{scheme}:' is not allowed for avatar URLs")

    allowed_schemes = {"https"}
    if allow_http:
        allowed_schemes.add("http")

    if scheme not in allowed_schemes:
        raise ValueError(
            f"Invalid avatar URL scheme: only {', '.join(sorted(allowed_schemes))} "
            f"URLs are allowed (got '{scheme}')"
        )

    # Host validation
    hostname = (parsed.hostname or "").lower()

    if not hostname:
        raise ValueError("Avatar URL must include a hostname")

    if hostname in BLOCKED_HOSTNAMES:
        raise ValueError(f"Hostname '{hostname}' is not allowed for avatar URLs")

    # IP range blocking
    if _is_blocked_ip(hostname):
        raise ValueError("Private, loopback, or link-local IP addresses are not allowed for avatar URLs")

    if _is_metadata_ip(hostname):
        raise ValueError("Cloud metadata service addresses are not allowed for avatar URLs")

    # TODO(ADR): Add async DNS-based SSRF protection before any future
    # server-side avatar proxy/fetch feature. Current validation only blocks
    # literal IPs and known local hostnames.

    return cleaned
