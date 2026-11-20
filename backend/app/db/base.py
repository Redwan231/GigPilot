"""Declarative base for all ORM models (SQLAlchemy 2.0 typed)."""

from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    """Shared declarative base. Models live in app/db/models/ and all inherit
    from this so `Base.metadata` holds the full schema."""
