"""P4-2: Daily scoring cap — cap blocks with 429, response includes reset messaging."""

import datetime
from unittest.mock import AsyncMock, patch

import pytest
from sqlalchemy import text

from app.tests.conftest import engine

USER_ID = "c3c3c3c3-c3c3-c3c3-c3c3-c3c3c3c3c3c3"
JOB_ID = "d4d4d4d4-d4d4-d4d4-d4d4-d4d4d4d4d4d4"

_MOCK_SCORE = {
    "score": 75,
    "confidence": 0.80,
    "dims": {"skills": 80, "seniority": 70, "rate": 75, "freshness": 75},
}


async def _seed() -> str:
    from app.core.security import create_access_token, hash_password

    async with engine.begin() as conn:
        await conn.execute(
            text(
                "INSERT INTO users (id, email, password_hash, profile_complete) "
                "VALUES (:id, :email, :pw, true)"
            ),
            {"id": USER_ID, "email": "cap@test.com", "pw": hash_password("Test1234!")},
        )
        await conn.execute(
            text(
                "INSERT INTO profiles (user_id, display_name, primary_category, skills, experience_level, hourly_rate, profile_version) "
                "VALUES (:uid, 'CapUser', 'Development', :skills, 'senior', 80.00, 1)"
            ),
            {"uid": USER_ID, "skills": ["python", "django"]},
        )
        await conn.execute(
            text(
                "INSERT INTO subscriptions (user_id, tier, period_end, drafts_quota) "
                "VALUES (:uid, 'free', '2027-12-31', 30)"
            ),
            {"uid": USER_ID},
        )
        await conn.execute(
            text(
                "INSERT INTO jobs (id, platform, external_id, title, description, url, raw) "
                "VALUES (:id, 'remoteok', 'cap-1', 'Django Dev', 'Build web apps.', 'https://x.com', '{}'::jsonb)"
            ),
            {"id": JOB_ID},
        )

    return create_access_token(USER_ID)


@pytest.mark.asyncio
async def test_daily_cap_returns_429(client) -> None:
    """When daily cap is exhausted, /score returns 429."""
    token = await _seed()

    with patch("app.services.scoring._check_daily_cap", new_callable=AsyncMock, return_value=False):
        resp = await client.post(
            f"/jobs/{JOB_ID}/score",
            headers={"Authorization": f"Bearer {token}"},
        )

    assert resp.status_code == 429


@pytest.mark.asyncio
async def test_daily_cap_message_mentions_limit(client) -> None:
    """429 detail should mention the daily limit."""
    token = await _seed()

    with patch("app.services.scoring._check_daily_cap", new_callable=AsyncMock, return_value=False):
        resp = await client.post(
            f"/jobs/{JOB_ID}/score",
            headers={"Authorization": f"Bearer {token}"},
        )

    assert resp.status_code == 429
    detail = resp.json().get("detail", "").lower()
    assert "daily" in detail or "limit" in detail or "cap" in detail, (
        f"Expected limit messaging in detail, got: {detail!r}"
    )


@pytest.mark.asyncio
async def test_cap_allowed_when_redis_unavailable(client) -> None:
    """When Redis is unreachable, scoring is allowed (fail-open per 04_TRD §5)."""
    token = await _seed()

    async def _redis_unavailable(*a, **kw):
        raise ConnectionError("Redis down")

    with patch("app.services.scoring._check_daily_cap", new_callable=AsyncMock, return_value=True):
        with patch("app.services.scoring.chat_json", new_callable=AsyncMock, return_value=_MOCK_SCORE):
            resp = await client.post(
                f"/jobs/{JOB_ID}/score",
                headers={"Authorization": f"Bearer {token}"},
            )

    assert resp.status_code == 200
    assert resp.json()["score"] == 75


@pytest.mark.asyncio
async def test_cache_hit_bypasses_cap(client) -> None:
    """A cached score is returned without hitting the cap."""
    token = await _seed()

    with patch("app.services.scoring.chat_json", new_callable=AsyncMock, return_value=_MOCK_SCORE):
        with patch("app.services.scoring._check_daily_cap", new_callable=AsyncMock, return_value=True) as mock_cap:
            resp1 = await client.post(
                f"/jobs/{JOB_ID}/score",
                headers={"Authorization": f"Bearer {token}"},
            )
            assert resp1.status_code == 200
            first_cap_calls = mock_cap.call_count

        with patch("app.services.scoring._check_daily_cap", new_callable=AsyncMock, return_value=False) as mock_cap2:
            resp2 = await client.post(
                f"/jobs/{JOB_ID}/score",
                headers={"Authorization": f"Bearer {token}"},
            )

    assert resp2.status_code == 200
    assert mock_cap2.call_count == 0, "Cap should not be checked for a cached score"
