"""P2-6: Jobs API GET /jobs (filters, sort, pagination) + GET /jobs/{id}."""

import uuid

import pytest
from httpx import AsyncClient
from sqlalchemy import text

from app.db.models.job import Job
from app.db.session import system_session


async def _auth(client: AsyncClient) -> dict[str, str]:
    r = await client.post(
        "/auth/signup", json={"email": "jobs@example.com", "password": "password1"}
    )
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


async def _seed_jobs() -> None:
    async with system_session() as session:
        session.add(
            Job(
                platform="remoteok",
                external_id="j1",
                title="Python Dev",
                description="Build APIs.",
                category="engineering",
                skills=["python", "fastapi"],
                budget_min=50,
                budget_max=100,
                url="https://example.com/j1",
                raw={"id": "j1"},
            )
        )
        session.add(
            Job(
                platform="remotive",
                external_id="j2",
                title="React Dev",
                description="Build UIs.",
                category="frontend",
                skills=["react", "typescript"],
                url="https://example.com/j2",
                raw={"id": "j2"},
            )
        )
        session.add(
            Job(
                platform="himalayas",
                external_id="j3",
                title="DevOps",
                description="K8s.",
                category="engineering",
                skills=["kubernetes"],
                budget_min=80,
                budget_max=150,
                url="https://example.com/j3",
                is_active=False,
                raw={"id": "j3"},
            )
        )


@pytest.mark.asyncio
async def test_list_jobs_empty(client: AsyncClient) -> None:
    h = await _auth(client)
    r = await client.get("/jobs", headers=h)
    assert r.status_code == 200
    assert r.json()["items"] == []


@pytest.mark.asyncio
async def test_list_jobs_returns_active_only(client: AsyncClient) -> None:
    h = await _auth(client)
    await _seed_jobs()
    r = await client.get("/jobs", headers=h)
    assert r.status_code == 200
    titles = [j["title"] for j in r.json()["items"]]
    assert "DevOps" not in titles
    assert len(titles) == 2


@pytest.mark.asyncio
async def test_list_jobs_filter_platform(client: AsyncClient) -> None:
    h = await _auth(client)
    await _seed_jobs()
    r = await client.get("/jobs?platform=remoteok", headers=h)
    items = r.json()["items"]
    assert len(items) == 1
    assert items[0]["platform"] == "remoteok"


@pytest.mark.asyncio
async def test_list_jobs_filter_category(client: AsyncClient) -> None:
    h = await _auth(client)
    await _seed_jobs()
    r = await client.get("/jobs?category=frontend", headers=h)
    items = r.json()["items"]
    assert len(items) == 1
    assert items[0]["title"] == "React Dev"


@pytest.mark.asyncio
async def test_list_jobs_filter_skill(client: AsyncClient) -> None:
    h = await _auth(client)
    await _seed_jobs()
    r = await client.get("/jobs?skill=python", headers=h)
    items = r.json()["items"]
    assert len(items) == 1
    assert items[0]["title"] == "Python Dev"


@pytest.mark.asyncio
async def test_list_jobs_budget_filter_includes_null(client: AsyncClient) -> None:
    h = await _auth(client)
    await _seed_jobs()
    # React Dev has no budget — should still appear
    r = await client.get("/jobs?budget_min=40", headers=h)
    titles = {j["title"] for j in r.json()["items"]}
    assert "React Dev" in titles
    assert "Python Dev" in titles


@pytest.mark.asyncio
async def test_get_job_detail(client: AsyncClient) -> None:
    h = await _auth(client)
    await _seed_jobs()
    r = await client.get("/jobs", headers=h)
    job_id = r.json()["items"][0]["id"]

    r2 = await client.get(f"/jobs/{job_id}", headers=h)
    assert r2.status_code == 200
    assert r2.json()["id"] == job_id
    assert r2.json()["user_score"] is None


@pytest.mark.asyncio
async def test_get_job_404(client: AsyncClient) -> None:
    h = await _auth(client)
    r = await client.get(f"/jobs/{uuid.uuid4()}", headers=h)
    assert r.status_code == 404


@pytest.mark.asyncio
async def test_list_jobs_pagination(client: AsyncClient) -> None:
    h = await _auth(client)
    await _seed_jobs()
    r = await client.get("/jobs?limit=1", headers=h)
    body = r.json()
    assert len(body["items"]) == 1
    assert body["next_cursor"] is not None

    r2 = await client.get(f"/jobs?limit=1&cursor={body['next_cursor']}", headers=h)
    body2 = r2.json()
    assert len(body2["items"]) == 1
    assert body2["items"][0]["id"] != body["items"][0]["id"]
