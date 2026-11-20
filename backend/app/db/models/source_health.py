"""Adapter observability (GLOBAL) (05_Schema §3.11)."""

import datetime

from sqlalchemy import Integer, Text, text
from sqlalchemy.dialects.postgresql import TIMESTAMP
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.db.types import pg_enum


class SourceHealth(Base):
    __tablename__ = "source_health"

    platform: Mapped[str] = mapped_column(Text, primary_key=True)
    status: Mapped[str] = mapped_column(
        pg_enum("source_status", "healthy", "degraded", "down"),
        nullable=False,
        server_default=text("'healthy'"),
    )
    last_success_at: Mapped[datetime.datetime | None] = mapped_column(
        TIMESTAMP(timezone=True), nullable=True
    )
    last_error_at: Mapped[datetime.datetime | None] = mapped_column(
        TIMESTAMP(timezone=True), nullable=True
    )
    consecutive_failures: Mapped[int] = mapped_column(
        Integer, nullable=False, server_default=text("0")
    )
