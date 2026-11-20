"""P2-9: Score reasoning — lazy-generate + cache on GET /jobs/{id}/score/why."""

import uuid
from decimal import Decimal
from unittest.mock import AsyncMock, patch

import pytest
from sqlalchemy import text

from app.tests.conftest import engine


USER_ID = "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"
JOB_ID = "bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb"


async def _seed(*, with_score: bool = True, with_reasoning: str | None = None):
    from app.core.security import hash_password

    async with engine.begin() as conn:
        await conn.execute(text(
            "INSERT INTO users (id, email, password_hash, profile_complete) "
            "VALUES (:id, :email, :pw, true)"
        ), {"id": USER_ID, "email": "reason@test.com", "pw": hash_password("Test1234!")})

        await conn.execute(text(
            "INSERT INTO profiles (user_id, display_name, primary_category, skills, experience_level, profile_version) "
            "VALUES (:uid, 'Reasoner', 'Dev', :skills, 'senior', 1)"
        ), {"uid": USER_ID, "skills": ["python"]})

        await conn.execute(text(
            "INSERT INTO jobs (id, platform, external_id, title, description, url, raw) "
            "VALUES (:id, 'remoteok', 'r-1', 'Python Dev', 'Build stuff', 'https://x.com', '{}'::jsonb)"
        ), {"id": JOB_ID})

        if with_score:
            params = {
                "uid": USER_ID,
                "jid": JOB_ID,
                "dims": '{"skills":85,"seniority":70,"rate":50,"freshness":60}',
            }
            if with_reasoning:
                await conn.execute(text(
                    "INSERT INTO scores (user_id, job_id, profile_version, score, confidence, dimensions, reasoning) "
                    "VALUES (:uid, :jid, 1, 78, 0.80, CAST(:dims AS jsonb), :reasoning)"
                ), {**params, "reasoning": with_reasoning})
            else:
                await conn.execute(text(
                    "INSERT INTO scores (user_id, job_id, profile_version, score, confidence, dimensions) "
                    "VALUES (:uid, :jid, 1, 78, 0.80, CAST(:dims AS jsonb))"
                ), params)


@pytest.mark.asyncio
async def test_why_generates_reasoning(client) -> None:
    await _seed()
    from app.core.security import create_access_token
    token = create_access_token(USER_ID)

    mock_text = "Strong skills match (85/100). Good seniority fit."
    with patch("app.services.scoring.chat_text", new_callable=AsyncMock, return_value=mock_text):
        resp = await client.get(
            f"/jobs/{JOB_ID}/score/why",
            headers={"Authorization": f"Bearer {token}"},
        )

    assert resp.status_code == 200
    data = resp.json()
    assert "Strong skills" in data["reasoning"]
    assert data["score"] == 78
    assert data["dimensions"]["skills"] == 85


@pytest.mark.asyncio
async def test_why_returns_cached_reasoning(client) -> None:
    await _seed(with_reasoning="Cached reasoning text.")
    from app.core.security import create_access_token
    token = create_access_token(USER_ID)

    with patch("app.services.scoring.chat_text", new_callable=AsyncMock) as mock_llm:
        resp = await client.get(
            f"/jobs/{JOB_ID}/score/why",
            headers={"Authorization": f"Bearer {token}"},
        )

    assert resp.status_code == 200
    assert resp.json()["reasoning"] == "Cached reasoning text."
    mock_llm.assert_not_called()


@pytest.mark.asyncio
async def test_why_404_no_score(client) -> None:
    await _seed(with_score=False)
    from app.core.security import create_access_token
    token = create_access_token(USER_ID)

    resp = await client.get(
        f"/jobs/{JOB_ID}/score/why",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 404
