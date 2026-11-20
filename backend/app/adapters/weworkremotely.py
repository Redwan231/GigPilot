"""WeWorkRemotely adapter (RSS/Atom feeds, parsed with BS4)."""

import datetime
import hashlib
import logging
from typing import Any

import httpx
from bs4 import BeautifulSoup

from app.adapters.base import BaseAdapter, RawJob

log = logging.getLogger(__name__)

_FEED_URLS = [
    "https://weworkremotely.com/categories/remote-programming-jobs.rss",
    "https://weworkremotely.com/categories/remote-design-jobs.rss",
    "https://weworkremotely.com/categories/remote-devops-sysadmin-jobs.rss",
]


class WeWorkRemotelyAdapter(BaseAdapter):
    platform = "weworkremotely"

    async def fetch(self) -> list[dict[str, Any]]:
        all_items: list[dict[str, Any]] = []
        async with httpx.AsyncClient(timeout=30) as client:
            for url in _FEED_URLS:
                try:
                    r = await client.get(url, headers={"User-Agent": self.user_agent})
                    r.raise_for_status()
                    soup = BeautifulSoup(r.text, "html.parser")
                    for item in soup.find_all("item"):
                        entry: dict[str, Any] = {}
                        for tag in ("title", "link", "description", "pubDate", "category"):
                            el = item.find(tag)
                            entry[tag] = el.get_text(strip=True) if el else None
                        all_items.append(entry)
                except Exception:
                    log.exception("Failed to fetch WWR feed: %s", url)
        return all_items

    def normalize(self, raw: dict[str, Any]) -> RawJob | None:
        title = raw.get("title") or ""
        link = raw.get("link") or ""
        if not title or not link:
            return None
        eid = hashlib.md5(link.encode()).hexdigest()
        posted = None
        if raw.get("pubDate"):
            try:
                from email.utils import parsedate_to_datetime

                posted = parsedate_to_datetime(raw["pubDate"])
            except (ValueError, TypeError):
                pass
        desc = raw.get("description") or ""
        # Strip HTML from description
        desc_text = BeautifulSoup(desc, "html.parser").get_text(separator=" ", strip=True)
        company = None
        if ":" in title:
            company = title.split(":")[0].strip()
        return RawJob(
            platform=self.platform,
            external_id=eid,
            title=title,
            description=desc_text,
            company=company,
            category=raw.get("category"),
            skills=[],
            url=link,
            posted_at=posted,
            raw=raw,
        )
