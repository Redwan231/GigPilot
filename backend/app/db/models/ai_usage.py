"""AI usage metering (05_Schema §3.9). user_id NULL for system ops."""

import datetime
import uuid
from decimal import Decimal

from sqlalchemy import ForeignKey, Integer, Numeric, Text, text
from sqlalchemy.dialects.postgresql import TIMESTAMP, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.db.types import pg_enum


class AiUsage(Base):
    __tablename__ = "ai_usage"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=True
    )
    operation: Mapped[str] = mapped_column(
        pg_enum("ai_operation", "score", "score_reasoning", "draft", "embed"),
        nullable=False,
    )
    model: Mapped[str] = mapped_column(Text, nullable=False)
    input_tokens: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("0"))
    output_tokens: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("0"))
    cost_usd: Mapped[Decimal] = mapped_column(
        Numeric(10, 6), nullable=False, server_default=text("0")
    )
    created_at: Mapped[datetime.datetime] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False, server_default=text("now()")
    )
