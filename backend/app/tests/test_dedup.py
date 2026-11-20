"""P4-4: Dedup — same (platform, external_id) stored once; re-fetch updates title."""

import pytest
from sqlalchemy import func, select, text
from unittest.mock import patch

from app.adapters.base import RawJob
from app.db.models.job import Job
from app.db.session import system_session
from app.workers.tasks import _run_aggregate


def _make_adapter(platform: str, job: RawJob, *, fail: bool = False, empty: bool = False):
    class A:
        pass
    A.platform = platform
    if fail:
        async def fetch(self): raise ConnectionError("down")
        A.fetch = fetch
        A.normalize = lambda self, r: None
    elif empty:
        async def fetch(self): return []
        A.fetch = fetch
        A.normalize = lambda self, r: None
    else:
        async def fetch(self): return [job.raw]
        A.fetch = fetch
        A.normalize = lambda self, r: job
    return A()


@pytest.mark.asyncio
async def test_same_platform_external_id_stored_once(clean_db) -> None:
    """Running the aggregator twice with the same job produces exactly 1 row."""
    job = RawJob(
        platform="remoteok", external_id="dedup-1",
        title="Python Dev", description="A test.", url="https://x.com", raw={},
    )
    adapters = [
        _make_adapter("remoteok", job),
        _make_adapter("remotive", job, empty=True),
        _make_adapter("himalayas", job, empty=True),
        _make_adapter("weworkremotely", job, empty=True),
    ]

    with patch("app.workers.tasks.ALL_ADAPTERS", adapters):
        await _run_aggregate()
        await _run_aggregate()

    async with system_session() as session:
        count = await session.scalar(select(func.count()).select_from(Job))
    assert count == 1, f"Expected 1 row, got {count}"


@pytest.mark.asyncio
async def test_upsert_updates_title_on_refetch(clean_db) -> None:
    """Re-fetching an existing job with a changed title updates the stored row."""
    job_v1 = RawJob(
        platform="remoteok", external_id="update-1",
        title="Old Title", description="Old.", url="https://x.com", raw={},
    )
    job_v2 = RawJob(
        platform="remoteok", external_id="update-1",
        title="New Title", description="Updated.", url="https://x.com", raw={},
    )
    empties = [
        _make_adapter("remotive", job_v1, empty=True),
        _make_adapter("himalayas", job_v1, empty=True),
        _make_adapter("weworkremotely", job_v1, empty=True),
    ]

    with patch("app.workers.tasks.ALL_ADAPTERS", [_make_adapter("remoteok", job_v1)] + empties):
        await _run_aggregate()

    with patch("app.workers.tasks.ALL_ADAPTERS", [_make_adapter("remoteok", job_v2)] + empties):
        await _run_aggregate()

    async with system_session() as session:
        count = await session.scalar(select(func.count()).select_from(Job))
        job = await session.scalar(select(Job).where(Job.external_id == "update-1"))

    assert count == 1
    assert job.title == "New Title", f"Expected updated title, got {job.title!r}"


@pytest.mark.asyncio
async def test_different_platform_same_external_id_stores_two_rows(clean_db) -> None:
    """Same external_id on different platforms = 2 distinct rows (not deduped)."""
    job_a = RawJob(
        platform="remoteok", external_id="x-1",
        title="Job A", description="A.", url="https://a.com", raw={},
    )
    job_b = RawJob(
        platform="remotive", external_id="x-1",
        title="Job B", description="B.", url="https://b.com", raw={},
    )

    adapters = [
        _make_adapter("remoteok", job_a),
        _make_adapter("remotive", job_b),
        _make_adapter("himalayas", job_a, empty=True),
        _make_adapter("weworkremotely", job_a, empty=True),
    ]

    with patch("app.workers.tasks.ALL_ADAPTERS", adapters):
        await _run_aggregate()

    async with system_session() as session:
        count = await session.scalar(select(func.count()).select_from(Job))
    assert count == 2, f"Expected 2 rows (different platforms), got {count}"
