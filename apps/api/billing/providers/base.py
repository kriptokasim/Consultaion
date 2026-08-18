from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Dict
from uuid import UUID

from billing.models import BillingPlan

BillingUserID = str | UUID


class BillingProvider(ABC):
    @abstractmethod
    def create_checkout_session(self, user_id: BillingUserID, plan: BillingPlan) -> str:
        """Return provider-hosted checkout URL for the canonical application user ID."""
        raise NotImplementedError

    @abstractmethod
    def handle_webhook(self, payload: Dict, headers: Dict, db_session = None) -> None:
        """Handle provider webhook events."""
        raise NotImplementedError
