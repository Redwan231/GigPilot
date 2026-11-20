"""Aggregated job listings (GLOBAL, not user-owned) (05_Schema §3.5)."""

import datetime
import uuid
from decimal import Decimal

from sqlalchemy import Boolean, Numeric, Text, UniqueConstraint, text
from sqlalchemy.dialects.postgresql import ARRAY, JSONB, TIMESTAMP, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base

_NOW = text("now()")


class Job(Base):
    __tablename__ = "jobs"
    __table_args__ = (
        UniqueConstraint("platform", "external_id", name="uq_jobs_platform_external"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    platform: Mapped[str] = mapped_column(Text, nullable=False)
    external_id: Mapped[str] = mapped_column(Text, nullable=False)
    title: Mapped[str] = mapped_column(Text, nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    company: Mapped[str | None] = mapped_column(Text, nullable=True)
    category: Mapped[str | None] = mapped_column(Text, nullable=True)
    skills: Mapped[list[str]] = mapped_column(
        ARRAY(Text), nullable=False, server_default=text("'{}'")
    )
    budget_min: Mapped[Decimal | None] = mapped_column(Numeric(12, 2), nullable=True)
    budget_max: Mapped[Decimal | None] = mapped_column(Numeric(12, 2), nullable=True)
    currency: Mapped[str] = mapped_column(Text, nullable=False, server_default=text("'USD'"))
    url: Mapped[str] = mapped_column(Text, nullable=False)
    posted_at: Mapped[datetime.datetime | None] = mapped_column(
        TIMESTAMP(timezone=True), nullable=True
    )
    fetched_at: Mapped[datetime.datetime] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False, server_default=_NOW
    )
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("true"))
    raw: Mapped[dict] = mapped_column(JSONB, nullable=False)
