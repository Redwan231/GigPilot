"""Adapter ABC + unified RawJob schema (04_TRD §4.1).

Each source adapter implements `fetch` and `normalize`. Adapters must set a
descriptive User-Agent, back off on 429, and never hard-fail the aggregation."""

import abc
import datetime
from typing import Any

from pydantic import BaseModel


class RawJob(BaseModel):
    """Normalized job representation produced by every adapter."""

    platform: str
    external_id: str
    title: str
    description: str
    company: str | None = None
    category: str | None = None
    skills: list[str] = []
    budget_min: float | None = None
    budget_max: float | None = None
    currency: str = "USD"
    url: str
    posted_at: datetime.datetime | None = None
    raw: dict[str, Any] = {}


class BaseAdapter(abc.ABC):
    platform: str
    user_agent: str = "GigPilot/1.0 (job aggregator; https://gigpilot.app)"

    @abc.abstractmethod
    async def fetch(self) -> list[dict[str, Any]]:
        """Fetch raw job data from the source."""

    @abc.abstractmethod
    def normalize(self, raw: dict[str, Any]) -> RawJob | None:
        """Convert a raw payload into a RawJob, or None to skip."""
