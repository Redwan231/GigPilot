"""P4-5: Adapter-down — one source errors; aggregation succeeds for the rest;
source_health updated with consecutive_failures."""

import pytest
from sqlalchemy import select
from unittest.mock import patch

from app.adapters.base import RawJob
from app.db.models.job import Job
from app.db.models.source_health import SourceHealth
from app.db.session import system_session
from app.workers.tasks import _run_aggregate


def _ok_adapter(platform: str, job: RawJob):
    class A:
        pass
    A.platform = platform
    async def fetch(self): return [job.raw]
    A.fetch = fetch
    A.normalize = lambda self, r: job
    return A()


def _fail_adapter(platform: str, exc: Exception = ConnectionError("down")):
    class A:
        pass
    A.platform = platform
    async def fetch(self): raise exc
    A.fetch = fetch
    A.normalize = lambda self, r: None
    return A()


def _empty_adapter(platform: str):
    class A:
        pass
    A.platform = platform
    async def fetch(self): return []
    A.fetch = fetch
    A.normalize = lambda self, r: None
    return A()


@pytest.mark.asyncio
async def test_one_down_others_succeed(clean_db) -> None:
    """remotive fails → aggregation returns partial results, remoteok still upserts."""
    good_job = RawJob(
        platform="remoteok", external_id="ok-1",
        title="Good Job", description="OK.", url="https://ok.com", raw={},
    )
    adapters = [
        _ok_adapter("remoteok", good_job),
        _fail_adapter("remotive"),
        _empty_adapter("himalayas"),
        _empty_adapter("weworkremotely"),
    ]

    with patch("app.workers.tasks.ALL_ADAPTERS", adapters):
        results = await _run_aggregate()

    assert results["remoteok"] == 1
    assert results["remotive"] == "error"

    async with system_session() as session:
        from sqlalchemy import func
        count = await session.scalar(select(func.count()).select_from(Job))
    assert count == 1, "remoteok job should still be upserted despite remotive failure"


@pytest.mark.asyncio
async def test_failing_adapter_increments_consecutive_failures(clean_db) -> None:
    """Consecutive failures increment source_health.consecutive_failures."""
    good_job = RawJob(
        platform="remoteok", external_id="hlt-1",
        title="Job", description="X.", url="https://x.com", raw={},
    )
    adapters = [
        _ok_adapter("remoteok", good_job),
        _fail_adapter("remotive"),
        _empty_adapter("himalayas"),
        _empty_adapter("weworkremotely"),
    ]

    with patch("app.workers.tasks.ALL_ADAPTERS", adapters):
        await _run_aggregate()
        await _run_aggregate()

    async with system_session() as session:
        health = await session.get(SourceHealth, "remotive")

    assert health is not None
    assert health.consecutive_failures >= 2
    assert health.last_error_at is not None


@pytest.mark.asyncio
async def test_failing_adapter_status_becomes_down_after_3(clean_db) -> None:
    """After 3 consecutive failures the status should be 'down'."""
    adapters = [
        _fail_adapter("remoteok"),
        _empty_adapter("remotive"),
        _empty_adapter("himalayas"),
        _empty_adapter("weworkremotely"),
    ]

    with patch("app.workers.tasks.ALL_ADAPTERS", adapters):
        await _run_aggregate()
        await _run_aggregate()
        await _run_aggregate()

    async with system_session() as session:
        health = await session.get(SourceHealth, "remoteok")

    assert health.status == "down", f"Expected 'down' after 3 failures, got {health.status!r}"
    assert health.consecutive_failures >= 3


@pytest.mark.asyncio
async def test_success_after_failure_resets_health(clean_db) -> None:
    """A successful run after failures resets status to 'healthy' and failures to 0."""
    good_job = RawJob(
        platform="remoteok", external_id="recover-1",
        title="Job", description="X.", url="https://x.com", raw={},
    )
    fail_adapters = [
        _fail_adapter("remoteok"),
        _empty_adapter("remotive"),
        _empty_adapter("himalayas"),
        _empty_adapter("weworkremotely"),
    ]
    ok_adapters = [
        _ok_adapter("remoteok", good_job),
        _empty_adapter("remotive"),
        _empty_adapter("himalayas"),
        _empty_adapter("weworkremotely"),
    ]

    with patch("app.workers.tasks.ALL_ADAPTERS", fail_adapters):
        await _run_aggregate()

    with patch("app.workers.tasks.ALL_ADAPTERS", ok_adapters):
        await _run_aggregate()

    async with system_session() as session:
        health = await session.get(SourceHealth, "remoteok")

    assert health.status == "healthy"
    assert health.consecutive_failures == 0
    assert health.last_success_at is not None
