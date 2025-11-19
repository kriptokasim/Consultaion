from __future__ import annotations

import uuid
from datetime import datetime
from typing import Optional

from sqlmodel import SQLModel, Field
from sqlalchemy import Column, DateTime

from models import utcnow


class Promotion(SQLModel, table=True):
    __tablename__ = "promotions"

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True, nullable=False)
    location: str = Field(nullable=False, index=True)
    title: str = Field(nullable=False)
    body: str = Field(nullable=False)
    cta_label: Optional[str] = None
    cta_url: Optional[str] = None
    is_active: bool = Field(default=True, nullable=False)
    priority: int = Field(default=100, nullable=False)
    target_plan_slug: Optional[str] = Field(default=None, nullable=True)
    created_at: datetime = Field(default_factory=utcnow, sa_column=Column(DateTime(timezone=True), nullable=False))
    updated_at: datetime = Field(default_factory=utcnow, sa_column=Column(DateTime(timezone=True), nullable=False))
