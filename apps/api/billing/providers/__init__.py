from __future__ import annotations

from config import settings

from .base import BillingProvider
from .stripe_provider import StripeBillingProvider


def get_billing_provider() -> BillingProvider:
    provider = (settings.BILLING_PROVIDER or "stripe").lower()
    if provider == "stripe":
        return StripeBillingProvider()
    raise RuntimeError(f"Unsupported BILLING_PROVIDER: {provider}")
