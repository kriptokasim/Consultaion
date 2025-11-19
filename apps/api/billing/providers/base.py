from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Dict
from uuid import UUID

from billing.models import BillingPlan


class BillingProvider(ABC):
    @abstractmethod
    def create_checkout_session(self, user_id: UUID, plan: BillingPlan) -> str:
        """Return provider-hosted checkout URL for the given user and plan."""
        raise NotImplementedError

    @abstractmethod
    def handle_webhook(self, payload: Dict, headers: Dict) -> None:
        """Handle provider webhook events."""
        raise NotImplementedError
