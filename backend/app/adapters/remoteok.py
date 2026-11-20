"""RemoteOK adapter (public JSON endpoint)."""

import datetime
import logging
from typing import Any

import httpx

from app.adapters.base import BaseAdapter, RawJob

log = logging.getLogger(__name__)


class RemoteOKAdapter(BaseAdapter):
    platform = "remoteok"
    _url = "https://remoteok.com/api"

    async def fetch(self) -> list[dict[str, Any]]:
        async with httpx.AsyncClient(timeout=30) as client:
            r = await client.get(self._url, headers={"User-Agent": self.user_agent})
            r.raise_for_status()
            data = r.json()
            # First element is legal notice, skip it
            return data[1:] if isinstance(data, list) and len(data) > 1 else []

    def normalize(self, raw: dict[str, Any]) -> RawJob | None:
        eid = str(raw.get("id", ""))
        title = raw.get("position") or raw.get("title") or ""
        if not eid or not title:
            return None
        posted = None
        if raw.get("date"):
            try:
                posted = datetime.datetime.fromisoformat(str(raw["date"]).replace("Z", "+00:00"))
            except (ValueError, TypeError):
                pass
        tags = raw.get("tags") or []
        return RawJob(
            platform=self.platform,
            external_id=eid,
            title=title,
            description=raw.get("description") or "",
            company=raw.get("company"),
            category=None,
            skills=tags if isinstance(tags, list) else [],
            url=f"https://remoteok.com/remote-jobs/{eid}",
            posted_at=posted,
            raw=raw,
        )
