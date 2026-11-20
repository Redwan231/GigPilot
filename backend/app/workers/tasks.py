"""Celery tasks. `aggregate_jobs` fetches from all adapters with per-source
isolation, upserts into the jobs table, and updates source_health (04_TRD §6)."""

import asyncio
import datetime
import logging

from sqlalchemy import text

from app.adapters.himalayas import HimalayasAdapter
from app.adapters.remoteok import RemoteOKAdapter
from app.adapters.remotive import RemotiveAdapter
from app.adapters.weworkremotely import WeWorkRemotelyAdapter
from app.db.session import system_session
from app.workers.celery_app import celery

log = logging.getLogger(__name__)

ALL_ADAPTERS = [
    RemoteOKAdapter(),
    RemotiveAdapter(),
    HimalayasAdapter(),
    WeWorkRemotelyAdapter(),
]

_UPSERT_SQL = text("""
    INSERT INTO jobs (platform, external_id, title, description, company,
                      category, skills, budget_min, budget_max, currency,
                      url, posted_at, fetched_at, is_active, raw)
    VALUES (:platform, :external_id, :title, :description, :company,
            :category, :skills, :budget_min, :budget_max, :currency,
            :url, :posted_at, now(), true, :raw)
    ON CONFLICT (platform, external_id) DO UPDATE SET
        title = EXCLUDED.title,
        description = EXCLUDED.description,
        company = EXCLUDED.company,
        category = EXCLUDED.category,
        skills = EXCLUDED.skills,
        budget_min = EXCLUDED.budget_min,
        budget_max = EXCLUDED.budget_max,
        currency = EXCLUDED.currency,
        url = EXCLUDED.url,
        posted_at = EXCLUDED.posted_at,
        fetched_at = now(),
        is_active = true,
        raw = EXCLUDED.raw
""")


async def _run_aggregate() -> dict[str, int | str]:
    results: dict[str, int | str] = {}
    for adapter in ALL_ADAPTERS:
        platform = adapter.platform
        try:
            raw_items = await adapter.fetch()
            count = 0
            async with system_session() as session:
                for raw in raw_items:
                    job = adapter.normalize(raw)
                    if job is None:
                        continue
                    import json
                    await session.execute(
                        _UPSERT_SQL,
                        {
                            "platform": job.platform,
                            "external_id": job.external_id,
                            "title": job.title,
                            "description": job.description,
                            "company": job.company,
                            "category": job.category,
                            "skills": job.skills,
                            "budget_min": job.budget_min,
                            "budget_max": job.budget_max,
                            "currency": job.currency,
                            "url": job.url,
                            "posted_at": job.posted_at,
                            "raw": json.dumps(job.raw),
                        },
                    )
                    count += 1
                # Update source health on success
                await session.execute(
                    text("""
                        UPDATE source_health
                        SET status = 'healthy',
                            last_success_at = now(),
                            consecutive_failures = 0
                        WHERE platform = :platform
                    """),
                    {"platform": platform},
                )
            results[platform] = count
            log.info("Adapter %s: upserted %d jobs", platform, count)
        except Exception:
            log.exception("Adapter %s failed", platform)
            results[platform] = "error"
            try:
                async with system_session() as session:
                    await session.execute(
                        text("""
                            UPDATE source_health
                            SET last_error_at = now(),
                                consecutive_failures = consecutive_failures + 1,
                                status = CASE
                                    WHEN consecutive_failures + 1 >= 3 THEN 'down'::source_status
                                    ELSE 'degraded'::source_status
                                END
                            WHERE platform = :platform
                        """),
                        {"platform": platform},
                    )
            except Exception:
                log.exception("Failed to update source_health for %s", platform)
    return results


@celery.task(name="app.workers.tasks.aggregate_jobs", max_retries=2, default_retry_delay=60)
def aggregate_jobs() -> dict[str, int | str]:
    return asyncio.run(_run_aggregate())
