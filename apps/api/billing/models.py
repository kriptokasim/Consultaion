from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal
from typing import Dict, Optional

from pydantic import ConfigDict
from sqlalchemy import Column, DateTime, JSON, Numeric, UniqueConstraint, text
from sqlmodel import Field, SQLModel

from models import utcnow


class BillingPlan(SQLModel, table=True):
    __tablename__ = "billing_plans"
    __table_args__ = {"extend_existing": True}
    model_config = ConfigDict(protected_namespaces=())

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True, nullable=False)
    slug: str = Field(nullable=False, index=True, unique=True)
    name: str = Field(nullable=False)
    price_monthly: Optional[Decimal] = Field(
        default=None,
        sa_column=Column(Numeric(10, 2), nullable=True),
    )
    currency: str = Field(default="USD", nullable=False)
    is_default_free: bool = Field(default=False, nullable=False)
    limits: Dict[str, object] = Field(
        default_factory=dict,
        sa_column=Column(JSON, nullable=False, server_default=text("'{}'")),
    )
    created_at: datetime = Field(default_factory=utcnow, sa_column=Column(DateTime(timezone=True), nullable=False))
    updated_at: datetime = Field(default_factory=utcnow, sa_column=Column(DateTime(timezone=True), nullable=False))

class BillingSubscription(SQLModel, table=True):
    __tablename__ = "billing_subscriptions"
    __table_args__ = {"extend_existing": True}
    model_config = ConfigDict(protected_namespaces=())

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True, nullable=False)
    user_id: str = Field(foreign_key="user.id", nullable=False, index=True)
    plan_id: uuid.UUID = Field(foreign_key="billing_plans.id", nullable=False)
    status: str = Field(nullable=False)
    current_period_start: datetime = Field(sa_column=Column(DateTime(timezone=True), nullable=False))
    current_period_end: datetime = Field(sa_column=Column(DateTime(timezone=True), nullable=False))
    cancel_at_period_end: bool = Field(default=False, nullable=False)
    provider: str = Field(nullable=False)
    provider_customer_id: Optional[str] = Field(default=None)
    provider_subscription_id: Optional[str] = Field(default=None)
    created_at: datetime = Field(default_factory=utcnow, sa_column=Column(DateTime(timezone=True), nullable=False))
    updated_at: datetime = Field(default_factory=utcnow, sa_column=Column(DateTime(timezone=True), nullable=False))

class BillingUsage(SQLModel, table=True):
    __tablename__ = "billing_usage"
    __table_args__ = (
        UniqueConstraint("user_id", "period", name="uq_billing_usage_user_period"),
        {"extend_existing": True},
    )
    model_config = ConfigDict(protected_namespaces=())

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True, nullable=False)
    user_id: str = Field(foreign_key="user.id", nullable=False, index=True)
    period: str = Field(nullable=False, index=True)
    debates_created: int = Field(default=0, nullable=False)
    exports_count: int = Field(default=0, nullable=False)
    tokens_used: int = Field(default=0, nullable=False)
    model_tokens: Dict[str, int] = Field(
        default_factory=dict,
        sa_column=Column(JSON, nullable=False, server_default=text("'{}'")),
    )
    last_updated_at: datetime = Field(default_factory=utcnow, sa_column=Column(DateTime(timezone=True), nullable=False))
