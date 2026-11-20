"""Himalayas adapter (public JSON API with pagination)."""

import datetime
import logging
from typing import Any

import httpx

from app.adapters.base import BaseAdapter, RawJob

log = logging.getLogger(__name__)


class HimalayasAdapter(BaseAdapter):
    platform = "himalayas"
    _url = "https://himalayas.app/jobs/api"

    async def fetch(self) -> list[dict[str, Any]]:
        all_jobs: list[dict[str, Any]] = []
        page = 1
        async with httpx.AsyncClient(timeout=30) as client:
            while page <= 3:
                r = await client.get(
                    self._url,
                    params={"limit": 50, "offset": (page - 1) * 50},
                    headers={"User-Agent": self.user_agent},
                )
                r.raise_for_status()
                data = r.json()
                jobs = data.get("jobs", [])
                if not jobs:
                    break
                all_jobs.extend(jobs)
                page += 1
        return all_jobs

    def normalize(self, raw: dict[str, Any]) -> RawJob | None:
        eid = str(raw.get("id") or raw.get("slug") or "")
        title = raw.get("title") or ""
        if not eid or not title:
            return None
        posted = None
        if raw.get("publishedDate"):
            try:
                posted = datetime.datetime.fromisoformat(
                    str(raw["publishedDate"]).replace("Z", "+00:00")
                )
            except (ValueError, TypeError):
                pass
        skills = raw.get("skills") or raw.get("categories") or []
        if isinstance(skills, list):
            skills = [s if isinstance(s, str) else s.get("name", "") for s in skills]
        else:
            skills = []
        salary_min = raw.get("salaryCurrencyMinValue")
        salary_max = raw.get("salaryCurrencyMaxValue")
        return RawJob(
            platform=self.platform,
            external_id=eid,
            title=title,
            description=raw.get("description") or raw.get("excerpt") or "",
            company=raw.get("companyName"),
            category=raw.get("categoryName"),
            skills=[s for s in skills if s],
            budget_min=float(salary_min) if salary_min else None,
            budget_max=float(salary_max) if salary_max else None,
            url=raw.get("applicationLink") or f"https://himalayas.app/jobs/{eid}",
            posted_at=posted,
            raw=raw,
        )
