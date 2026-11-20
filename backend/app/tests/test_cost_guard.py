"""P4-8: Cost guard — same (user,job,profile_version) not re-scored; ai_usage
written on every new LLM call with tokens + cost."""

from unittest.mock import AsyncMock, patch

import pytest
from sqlalchemy import func, select, text

from app.db.models.ai_usage import AiUsage
from app.db.session import system_session
from app.tests.conftest import engine

USER_ID = "77777701-7777-7777-7777-777777777777"
JOB_ID = "88888802-8888-8888-8888-888888888888"

_MOCK_SCORE = {
    "score": 80,
    "confidence": 0.90,
    "dims": {"skills": 85, "seniority": 80, "rate": 75, "freshness": 80},
}


async def _seed() -> str:
    from app.core.security import create_access_token, hash_password

    async with engine.begin() as conn:
        await conn.execute(
            text(
                "INSERT INTO users (id, email, password_hash, profile_complete) "
                "VALUES (:id, :email, :pw, true)"
            ),
            {"id": USER_ID, "email": "costguard@test.com", "pw": hash_password("Test1234!")},
        )
        await conn.execute(
            text(
                "INSERT INTO profiles (user_id, display_name, primary_category, skills, "
                "experience_level, hourly_rate, profile_version) "
                "VALUES (:uid, 'CostUser', 'Development', :skills, 'senior', 90.00, 1)"
            ),
            {"uid": USER_ID, "skills": ["python", "fastapi"]},
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
                "VALUES (:id, 'remoteok', 'cg-1', 'FastAPI Dev', 'Build APIs.', 'https://x.com', '{}'::jsonb)"
            ),
            {"id": JOB_ID},
        )

    return create_access_token(USER_ID)


@pytest.mark.asyncio
async def test_same_profile_version_not_rescored(client) -> None:
    """POST /jobs/{id}/score called twice → LLM invoked only once (cached)."""
    token = await _seed()

    with patch("app.services.scoring.chat_json", new_callable=AsyncMock, return_value=_MOCK_SCORE) as mock_llm:
        with patch("app.services.scoring._check_daily_cap", new_callable=AsyncMock, return_value=True):
            r1 = await client.post(
                f"/jobs/{JOB_ID}/score",
                headers={"Authorization": f"Bearer {token}"},
            )
            r2 = await client.post(
                f"/jobs/{JOB_ID}/score",
                headers={"Authorization": f"Bearer {token}"},
            )

    assert r1.status_code == 200
    assert r2.status_code == 200
    assert mock_llm.call_count == 1, (
        f"LLM should be called only once for the same (user,job,profile_version); got {mock_llm.call_count}"
    )
    assert r1.json()["score"] == r2.json()["score"]


@pytest.mark.asyncio
async def test_profile_version_bump_triggers_rescore(client) -> None:
    """After a profile update (profile_version incremented), scoring re-runs the LLM."""
    token = await _seed()

    with patch("app.services.scoring.chat_json", new_callable=AsyncMock, return_value=_MOCK_SCORE):
        with patch("app.services.scoring._check_daily_cap", new_callable=AsyncMock, return_value=True):
            await client.post(
                f"/jobs/{JOB_ID}/score",
                headers={"Authorization": f"Bearer {token}"},
            )

    # Bump profile_version
    async with engine.begin() as conn:
        await conn.execute(
            text("UPDATE profiles SET profile_version = 2 WHERE user_id = :uid"),
            {"uid": USER_ID},
        )

    with patch("app.services.scoring.chat_json", new_callable=AsyncMock, return_value=_MOCK_SCORE) as mock_llm2:
        with patch("app.services.scoring._check_daily_cap", new_callable=AsyncMock, return_value=True):
            r3 = await client.post(
                f"/jobs/{JOB_ID}/score",
                headers={"Authorization": f"Bearer {token}"},
            )

    assert r3.status_code == 200
    assert mock_llm2.call_count == 1, "New profile version should trigger a new LLM call"


@pytest.mark.asyncio
async def test_ai_usage_written_on_score(client) -> None:
    """chat_json writes an ai_usage row with operation='score' on each new score."""
    token = await _seed()

    mock_response = type("R", (), {
        "choices": [type("C", (), {
            "message": type("M", (), {"content": '{"score": 75, "confidence": 0.8, "dims": {"skills": 75, "seniority": 70, "rate": 80, "freshness": 75}}'})()
        })()],
        "usage": type("U", (), {"prompt_tokens": 200, "completion_tokens": 50})(),
    })()

    with patch("app.ai.llm.AsyncOpenAI") as mock_openai:
        mock_client = AsyncMock()
        mock_openai.return_value = mock_client
        mock_client.chat.completions.create = AsyncMock(return_value=mock_response)

        with patch("app.services.scoring._check_daily_cap", new_callable=AsyncMock, return_value=True):
            resp = await client.post(
                f"/jobs/{JOB_ID}/score",
                headers={"Authorization": f"Bearer {token}"},
            )

    assert resp.status_code == 200

    async with system_session() as session:
        count = await session.scalar(
            select(func.count()).select_from(AiUsage)
            .where(AiUsage.user_id == USER_ID, AiUsage.operation == "score")
        )
    assert count >= 1, "ai_usage row should have been written for the score operation"


@pytest.mark.asyncio
async def test_ai_usage_includes_cost(client) -> None:
    """ai_usage row has non-zero cost_usd when tokens are reported."""
    token = await _seed()

    mock_response = type("R", (), {
        "choices": [type("C", (), {
            "message": type("M", (), {"content": '{"score": 70, "confidence": 0.75, "dims": {"skills": 70, "seniority": 70, "rate": 70, "freshness": 70}}'})()
        })()],
        "usage": type("U", (), {"prompt_tokens": 300, "completion_tokens": 80})(),
    })()

    with patch("app.ai.llm.AsyncOpenAI") as mock_openai:
        mock_client = AsyncMock()
        mock_openai.return_value = mock_client
        mock_client.chat.completions.create = AsyncMock(return_value=mock_response)

        with patch("app.services.scoring._check_daily_cap", new_callable=AsyncMock, return_value=True):
            await client.post(
                f"/jobs/{JOB_ID}/score",
                headers={"Authorization": f"Bearer {token}"},
            )

    async with system_session() as session:
        row = await session.scalar(
            select(AiUsage)
            .where(AiUsage.user_id == USER_ID, AiUsage.operation == "score")
            .order_by(AiUsage.created_at.desc())
        )

    assert row is not None
    assert row.input_tokens == 300
    assert row.output_tokens == 80
    assert row.cost_usd > 0, f"Expected non-zero cost, got {row.cost_usd}"
