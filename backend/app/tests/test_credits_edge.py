"""P4-1: Credit edge cases — 0 credits blocks draft (402), AI failure does NOT
deduct, monthly reset resets drafts_used to 0."""

import datetime
from unittest.mock import AsyncMock, patch

import pytest
from sqlalchemy import text

from app.tests.conftest import engine

USER_ID = "a1a1a1a1-a1a1-a1a1-a1a1-a1a1a1a1a1a1"
JOB_ID = "b2b2b2b2-b2b2-b2b2-b2b2-b2b2b2b2b2b2"

_FAR_FUTURE = datetime.date(2027, 12, 31)


async def _seed(
    drafts_used: int = 0,
    drafts_quota: int = 30,
    period_end: datetime.date | None = None,
) -> str:
    from app.core.security import create_access_token, hash_password

    if period_end is None:
        period_end = _FAR_FUTURE

    async with engine.begin() as conn:
        await conn.execute(
            text(
                "INSERT INTO users (id, email, password_hash, profile_complete) "
                "VALUES (:id, :email, :pw, true)"
            ),
            {"id": USER_ID, "email": "credits@test.com", "pw": hash_password("Test1234!")},
        )
        await conn.execute(
            text(
                "INSERT INTO profiles (user_id, display_name, primary_category, skills, experience_level, profile_version) "
                "VALUES (:uid, 'CreditUser', 'Dev', :skills, 'mid', 1)"
            ),
            {"uid": USER_ID, "skills": ["python"]},
        )
        await conn.execute(
            text(
                "INSERT INTO subscriptions (user_id, tier, period_end, drafts_quota, drafts_used) "
                "VALUES (:uid, 'free', :pe, :quota, :used)"
            ),
            {"uid": USER_ID, "pe": period_end, "quota": drafts_quota, "used": drafts_used},
        )
        await conn.execute(
            text(
                "INSERT INTO jobs (id, platform, external_id, title, description, url, raw) "
                "VALUES (:id, 'remoteok', 'cred-1', 'Python Job', 'Build stuff.', 'https://x.com', '{}'::jsonb)"
            ),
            {"id": JOB_ID},
        )

    return create_access_token(USER_ID)


@pytest.mark.asyncio
async def test_zero_credits_blocks_draft(client) -> None:
    """With 0 credits remaining, POST /jobs/{id}/draft returns 402."""
    token = await _seed(drafts_used=30, drafts_quota=30)

    resp = await client.post(
        f"/jobs/{JOB_ID}/draft",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert resp.status_code == 402
    assert "limit" in resp.json()["detail"].lower() or "credit" in resp.json()["detail"].lower()


@pytest.mark.asyncio
async def test_ai_failure_does_not_deduct_credit(client) -> None:
    """When the AI/LangGraph call fails, the reserved credit is released."""
    token = await _seed(drafts_used=0, drafts_quota=30)

    with patch("app.api.routes.proposals.agent_graph") as mock_graph:
        mock_graph.ainvoke = AsyncMock(
            return_value={"draft": None, "voice_matched": False, "error": "LLM unavailable"}
        )
        resp = await client.post(
            f"/jobs/{JOB_ID}/draft",
            headers={"Authorization": f"Bearer {token}"},
        )

    assert resp.status_code == 502

    async with engine.begin() as conn:
        row = await conn.execute(
            text("SELECT drafts_used FROM subscriptions WHERE user_id = :uid"), {"uid": USER_ID}
        )
        used = row.scalar()
    assert used == 0, f"Expected 0 drafts_used after AI failure, got {used}"


@pytest.mark.asyncio
async def test_monthly_reset_clears_quota(client) -> None:
    """When period_end is in the past, next draft request triggers a quota reset."""
    past = datetime.date.today() - datetime.timedelta(days=5)
    token = await _seed(drafts_used=25, drafts_quota=30, period_end=past)  # type: ignore[arg-type]

    _MOCK = {"draft": "Great proposal!", "voice_matched": False, "error": None}

    with patch("app.api.routes.proposals.agent_graph") as mock_graph:
        mock_graph.ainvoke = AsyncMock(return_value=_MOCK)
        resp = await client.post(
            f"/jobs/{JOB_ID}/draft",
            headers={"Authorization": f"Bearer {token}"},
        )

    assert resp.status_code == 200
    data = resp.json()
    assert data["credits_remaining"] == 29, (
        f"After monthly reset + 1 draft, expected 29 remaining, got {data['credits_remaining']}"
    )


@pytest.mark.asyncio
async def test_successful_draft_decrements_credit(client) -> None:
    """A successful draft deducts exactly 1 credit."""
    token = await _seed(drafts_used=10, drafts_quota=30)

    _MOCK = {"draft": "Professional proposal.", "voice_matched": False, "error": None}

    with patch("app.api.routes.proposals.agent_graph") as mock_graph:
        mock_graph.ainvoke = AsyncMock(return_value=_MOCK)
        resp = await client.post(
            f"/jobs/{JOB_ID}/draft",
            headers={"Authorization": f"Bearer {token}"},
        )

    assert resp.status_code == 200
    assert resp.json()["credits_remaining"] == 19
