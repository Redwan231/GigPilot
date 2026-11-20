"""Schemas for jobs endpoints."""

import datetime
import uuid
from decimal import Decimal

from pydantic import BaseModel


class JobOut(BaseModel):
    id: uuid.UUID
    platform: str
    external_id: str
    title: str
    description: str
    company: str | None
    category: str | None
    skills: list[str]
    budget_min: Decimal | None
    budget_max: Decimal | None
    currency: str
    url: str
    posted_at: datetime.datetime | None
    fetched_at: datetime.datetime
    is_active: bool


class ScoreOut(BaseModel):
    id: uuid.UUID
    score: int
    confidence: Decimal
    dimensions: dict
    reasoning: str | None
    profile_version: int
    created_at: datetime.datetime


class JobDetailOut(JobOut):
    user_score: ScoreOut | None = None


class JobListOut(BaseModel):
    items: list[JobOut]
    next_cursor: str | None = None
