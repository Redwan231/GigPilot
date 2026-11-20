"""Per-user job scores (05_Schema §3.6)."""

import datetime
import uuid
from decimal import Decimal

from sqlalchemy import (
    CheckConstraint,
    ForeignKey,
    Integer,
    Numeric,
    SmallInteger,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB, TIMESTAMP, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class Score(Base):
    __tablename__ = "scores"
    __table_args__ = (
        UniqueConstraint("user_id", "job_id", "profile_version", name="uq_scores_user_job_version"),
        CheckConstraint("score BETWEEN 0 AND 100", name="scores_score_check"),
        CheckConstraint("confidence BETWEEN 0 AND 1", name="scores_confidence_check"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    job_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("jobs.id", ondelete="CASCADE"), nullable=False
    )
    profile_version: Mapped[int] = mapped_column(Integer, nullable=False)
    score: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    confidence: Mapped[Decimal] = mapped_column(Numeric(3, 2), nullable=False)
    dimensions: Mapped[dict] = mapped_column(JSONB, nullable=False)
    reasoning: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime.datetime] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False, server_default=text("now()")
    )
