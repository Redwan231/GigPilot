"""Remotive adapter (public JSON API)."""

import datetime
import logging
from typing import Any

import httpx

from app.adapters.base import BaseAdapter, RawJob

log = logging.getLogger(__name__)


class RemotiveAdapter(BaseAdapter):
    platform = "remotive"
    _url = "https://remotive.com/api/remote-jobs"

    async def fetch(self) -> list[dict[str, Any]]:
        async with httpx.AsyncClient(timeout=30) as client:
            r = await client.get(self._url, headers={"User-Agent": self.user_agent})
            r.raise_for_status()
            data = r.json()
            return data.get("jobs", [])

    def normalize(self, raw: dict[str, Any]) -> RawJob | None:
        eid = str(raw.get("id", ""))
        title = raw.get("title") or ""
        if not eid or not title:
            return None
        posted = None
        if raw.get("publication_date"):
            try:
                posted = datetime.datetime.fromisoformat(
                    str(raw["publication_date"]).replace("Z", "+00:00")
                )
            except (ValueError, TypeError):
                pass
        tags = raw.get("tags") or []
        salary_raw = raw.get("salary") or ""
        budget_min = budget_max = None
        if salary_raw and "-" in salary_raw:
            parts = salary_raw.replace("$", "").replace(",", "").split("-")
            try:
                budget_min = float(parts[0].strip())
                budget_max = float(parts[1].strip())
            except (ValueError, IndexError):
                pass
        return RawJob(
            platform=self.platform,
            external_id=eid,
            title=title,
            description=raw.get("description") or "",
            company=raw.get("company_name"),
            category=raw.get("category"),
            skills=tags if isinstance(tags, list) else [],
            budget_min=budget_min,
            budget_max=budget_max,
            url=raw.get("url") or f"https://remotive.com/remote-jobs/{eid}",
            posted_at=posted,
            raw=raw,
        )
