"""P2-5: aggregate_jobs task — per-source isolation, upsert, source_health."""

import pytest
from sqlalchemy import func, select, text
from unittest.mock import AsyncMock, patch, MagicMock

from app.db.models.job import Job
from app.db.models.source_health import SourceHealth
from app.db.session import system_session
from app.workers.tasks import _run_aggregate


@pytest.mark.asyncio
async def test_aggregate_upserts_jobs(clean_db) -> None:
    """Mock adapters return fixture data; jobs are upserted and source_health updated."""
    from app.adapters.base import RawJob
    import datetime

    fake_job = RawJob(
        platform="remoteok",
        external_id="test-1",
        title="Test Job",
        description="A test.",
        url="https://example.com/1",
        raw={"id": "test-1"},
    )

    class FakeAdapter:
        platform = "remoteok"
        async def fetch(self):
            return [fake_job.raw]
        def normalize(self, raw):
            return fake_job

    class FailAdapter:
        platform = "remotive"
        async def fetch(self):
            raise ConnectionError("down")
        def normalize(self, raw):
            return None

    class EmptyAdapter:
        platform = "himalayas"
        async def fetch(self):
            return []
        def normalize(self, raw):
            return None

    class EmptyAdapter2:
        platform = "weworkremotely"
        async def fetch(self):
            return []
        def normalize(self, raw):
            return None

    with patch("app.workers.tasks.ALL_ADAPTERS", [FakeAdapter(), FailAdapter(), EmptyAdapter(), EmptyAdapter2()]):
        results = await _run_aggregate()

    assert results["remoteok"] == 1
    assert results["remotive"] == "error"
    assert results["himalayas"] == 0

    # Verify job was inserted
    async with system_session() as session:
        count = await session.scalar(select(func.count()).select_from(Job))
        assert count == 1
        job = await session.scalar(select(Job).where(Job.external_id == "test-1"))
        assert job.title == "Test Job"
        assert job.platform == "remoteok"

    # Verify source_health updated
    async with system_session() as session:
        ok = await session.get(SourceHealth, "remoteok")
        assert ok.status == "healthy"
        assert ok.last_success_at is not None

        rem = await session.get(SourceHealth, "remotive")
        assert rem.status == "degraded"
        assert rem.consecutive_failures >= 1


@pytest.mark.asyncio
async def test_aggregate_upsert_idempotent(clean_db) -> None:
    """Running twice with same data should not duplicate jobs."""
    from app.adapters.base import RawJob

    fake_job = RawJob(
        platform="remoteok",
        external_id="dup-1",
        title="Dup Job",
        description="Dedup test.",
        url="https://example.com/dup",
        raw={"id": "dup-1"},
    )

    class FakeAdapter:
        platform = "remoteok"
        async def fetch(self):
            return [fake_job.raw]
        def normalize(self, raw):
            return fake_job

    noop = type("N", (), {"platform": "remotive", "fetch": AsyncMock(return_value=[]), "normalize": lambda s, r: None})()
    noop2 = type("N", (), {"platform": "himalayas", "fetch": AsyncMock(return_value=[]), "normalize": lambda s, r: None})()
    noop3 = type("N", (), {"platform": "weworkremotely", "fetch": AsyncMock(return_value=[]), "normalize": lambda s, r: None})()

    with patch("app.workers.tasks.ALL_ADAPTERS", [FakeAdapter(), noop, noop2, noop3]):
        await _run_aggregate()
        await _run_aggregate()

    async with system_session() as session:
        count = await session.scalar(select(func.count()).select_from(Job))
        assert count == 1
