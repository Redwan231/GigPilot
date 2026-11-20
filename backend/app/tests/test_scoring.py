"""P2-8: Scoring service — skill overlap, caching, daily cap, endpoint."""

import uuid
from decimal import Decimal
from unittest.mock import AsyncMock, patch

import pytest
from sqlalchemy import text

from app.services.scoring import compute_skill_overlap


def test_skill_overlap_exact_match() -> None:
    assert compute_skill_overlap(["Python", "React"], ["python", "react"], "") == 1.0


def test_skill_overlap_partial() -> None:
    overlap = compute_skill_overlap(["Python", "React", "Go"], ["python"], "")
    assert abs(overlap - 1 / 3) < 0.01


def test_skill_overlap_description_fallback() -> None:
    overlap = compute_skill_overlap(["kubernetes"], [], "We use Kubernetes and Docker")
    assert overlap == 1.0


def test_skill_overlap_no_match() -> None:
    assert compute_skill_overlap(["Rust"], ["Python", "Go"], "web development") == 0.0


def test_skill_overlap_empty_profile() -> None:
    assert compute_skill_overlap([], ["Python"], "any") == 0.0


USER_ID = "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"
JOB_ID = "bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb"

_MOCK_SCORE_RESULT = {
    "score": 82,
    "confidence": 0.85,
    "dims": {"skills": 90, "seniority": 80, "rate": 75, "freshness": 70},
}


async def _seed_user_job(client) -> tuple[str, str]:
    """Create user with profile + subscription + a job via raw SQL,
    then return (access_token, job_id)."""
    from app.core.security import create_access_token, hash_password

    from app.tests.conftest import engine

    async with engine.begin() as conn:
        await conn.execute(text(
            "INSERT INTO users (id, email, password_hash, profile_complete) "
            "VALUES (:id, :email, :pw, true)"
        ), {"id": USER_ID, "email": "scorer@test.com", "pw": hash_password("Test1234!")})

        await conn.execute(text(
            "INSERT INTO profiles (user_id, display_name, primary_category, skills, experience_level, hourly_rate, profile_version) "
            "VALUES (:uid, 'Scorer', 'Development', :skills, 'senior', 100.00, 1)"
        ), {"uid": USER_ID, "skills": ["python", "react", "fastapi"]})

        await conn.execute(text(
            "INSERT INTO subscriptions (user_id, tier, period_end, drafts_quota) "
            "VALUES (:uid, 'free', '2027-12-31', 30)"
        ), {"uid": USER_ID})

        await conn.execute(text(
            "INSERT INTO jobs (id, platform, external_id, title, description, skills, url, raw) "
            "VALUES (:id, 'remoteok', 'test-123', 'Senior Python Developer', "
            "'Looking for a senior Python developer with React experience.', "
            ":skills, 'https://example.com/job', '{}'::jsonb)"
        ), {"id": JOB_ID, "skills": ["python", "react", "postgresql"]})

    token = create_access_token(USER_ID)
    return token, JOB_ID


@pytest.mark.asyncio
async def test_score_endpoint_success(client) -> None:
    token, job_id = await _seed_user_job(client)

    with patch("app.services.scoring.chat_json", new_callable=AsyncMock, return_value=_MOCK_SCORE_RESULT):
        with patch("app.services.scoring._check_daily_cap", new_callable=AsyncMock, return_value=True):
            resp = await client.post(
                f"/jobs/{job_id}/score",
                headers={"Authorization": f"Bearer {token}"},
            )

    assert resp.status_code == 200
    data = resp.json()
    assert data["score"] == 82
    assert data["dimensions"]["skills"] == 90
    assert data["profile_version"] == 1


@pytest.mark.asyncio
async def test_score_endpoint_cached(client) -> None:
    token, job_id = await _seed_user_job(client)

    with patch("app.services.scoring.chat_json", new_callable=AsyncMock, return_value=_MOCK_SCORE_RESULT) as mock_llm:
        with patch("app.services.scoring._check_daily_cap", new_callable=AsyncMock, return_value=True):
            resp1 = await client.post(
                f"/jobs/{job_id}/score",
                headers={"Authorization": f"Bearer {token}"},
            )
            resp2 = await client.post(
                f"/jobs/{job_id}/score",
                headers={"Authorization": f"Bearer {token}"},
            )

    assert resp1.status_code == 200
    assert resp2.status_code == 200
    assert mock_llm.call_count == 1


@pytest.mark.asyncio
async def test_score_endpoint_daily_cap_429(client) -> None:
    token, job_id = await _seed_user_job(client)

    with patch("app.services.scoring._check_daily_cap", new_callable=AsyncMock, return_value=False):
        resp = await client.post(
            f"/jobs/{job_id}/score",
            headers={"Authorization": f"Bearer {token}"},
        )

    assert resp.status_code == 429


@pytest.mark.asyncio
async def test_score_endpoint_no_profile(client) -> None:
    """User without profile gets 404."""
    from app.core.security import create_access_token, hash_password
    from app.tests.conftest import engine

    uid = "eeeeeeee-eeee-eeee-eeee-eeeeeeeeeeee"
    async with engine.begin() as conn:
        await conn.execute(text(
            "INSERT INTO users (id, email, password_hash) VALUES (:id, :email, :pw)"
        ), {"id": uid, "email": "noprofile@test.com", "pw": hash_password("Test1234!")})
        await conn.execute(text(
            "INSERT INTO jobs (id, platform, external_id, title, description, url, raw) "
            "VALUES (:id, 'remoteok', 'x', 'Job', 'Desc', 'https://x.com', '{}'::jsonb)"
        ), {"id": JOB_ID})

    token = create_access_token(uid)
    resp = await client.post(
        f"/jobs/{JOB_ID}/score",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_score_endpoint_job_not_found(client) -> None:
    from app.core.security import create_access_token, hash_password
    from app.tests.conftest import engine

    uid = "ffffffff-ffff-ffff-ffff-ffffffffffff"
    fake_job = "99999999-9999-9999-9999-999999999999"
    async with engine.begin() as conn:
        await conn.execute(text(
            "INSERT INTO users (id, email, password_hash, profile_complete) "
            "VALUES (:id, :email, :pw, true)"
        ), {"id": uid, "email": "nojob@test.com", "pw": hash_password("Test1234!")})
        await conn.execute(text(
            "INSERT INTO profiles (user_id, display_name, primary_category, skills, experience_level, profile_version) "
            "VALUES (:uid, 'X', 'Dev', :skills, 'mid', 1)"
        ), {"uid": uid, "skills": ["python"]})

    token = create_access_token(uid)
    resp = await client.post(
        f"/jobs/{fake_job}/score",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 404
