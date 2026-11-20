"""P4-3: Cold-start path — no writing samples → template draft, voice_matched=False."""

from unittest.mock import AsyncMock, patch

import pytest
from sqlalchemy import text

from app.tests.conftest import engine

USER_ID = "e5e5e5e5-e5e5-e5e5-e5e5-e5e5e5e5e5e5"
JOB_ID = "f6f6f6f6-f6f6-f6f6-f6f6-f6f6f6f6f6f6"


async def _seed() -> str:
    from app.core.security import create_access_token, hash_password

    async with engine.begin() as conn:
        await conn.execute(
            text(
                "INSERT INTO users (id, email, password_hash, profile_complete) "
                "VALUES (:id, :email, :pw, true)"
            ),
            {"id": USER_ID, "email": "coldstart@test.com", "pw": hash_password("Test1234!")},
        )
        await conn.execute(
            text(
                "INSERT INTO profiles (user_id, display_name, primary_category, skills, experience_level, profile_version) "
                "VALUES (:uid, 'NewUser', 'Development', :skills, 'mid', 1)"
            ),
            {"uid": USER_ID, "skills": ["javascript", "nodejs"]},
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
                "VALUES (:id, 'remoteok', 'cold-1', 'Node.js Dev', 'Build APIs.', 'https://x.com', '{}'::jsonb)"
            ),
            {"id": JOB_ID},
        )
        # NO writing_samples seeded → cold-start path

    return create_access_token(USER_ID)


_COLD_DRAFT = "Dear Hiring Manager, I am an experienced Node.js developer."


@pytest.mark.asyncio
async def test_cold_start_draft_voice_matched_false(client) -> None:
    """With no samples, voice_matched must be False."""
    token = await _seed()

    mock_result = {"draft": _COLD_DRAFT, "voice_matched": False, "error": None}

    with patch("app.api.routes.proposals.agent_graph") as mock_graph:
        mock_graph.ainvoke = AsyncMock(return_value=mock_result)
        resp = await client.post(
            f"/jobs/{JOB_ID}/draft",
            headers={"Authorization": f"Bearer {token}"},
        )

    assert resp.status_code == 200
    data = resp.json()
    assert data["voice_matched"] is False, "Cold-start draft must have voice_matched=False"
    assert _COLD_DRAFT in data["content"]


@pytest.mark.asyncio
async def test_cold_start_draft_still_succeeds(client) -> None:
    """Cold-start never blocks drafting — it falls back to template."""
    token = await _seed()

    mock_result = {"draft": "Professional proposal for Node.js role.", "voice_matched": False, "error": None}

    with patch("app.api.routes.proposals.agent_graph") as mock_graph:
        mock_graph.ainvoke = AsyncMock(return_value=mock_result)
        resp = await client.post(
            f"/jobs/{JOB_ID}/draft",
            headers={"Authorization": f"Bearer {token}"},
        )

    assert resp.status_code == 200
    assert resp.json()["credits_remaining"] == 29


@pytest.mark.asyncio
async def test_generate_draft_service_no_chunks_uses_cold_start_system(client) -> None:
    """Unit: generate_draft() with no voice_chunks uses the cold-start system prompt."""
    from unittest.mock import AsyncMock, patch

    from app.services.drafting import generate_draft

    with patch("app.services.drafting.chat_text", new_callable=AsyncMock, return_value="Cold draft.") as mock_llm:
        result = await generate_draft(
            user_id=USER_ID,
            job_summary="Node.js backend role",
            profile_summary="Skills: javascript, nodejs. Experience: mid.",
            voice_chunks=[],  # no samples
        )

    assert result == "Cold draft."
    call_args = mock_llm.call_args
    messages = call_args[0][0]
    system_msg = messages[0]["content"]
    assert "cold" in system_msg.lower() or "professional" in system_msg.lower(), (
        "Cold-start system prompt should not use voice-based framing"
    )


@pytest.mark.asyncio
async def test_generate_draft_service_with_chunks_uses_voice_system(client) -> None:
    """Unit: generate_draft() with voice_chunks uses the voice-based system prompt."""
    from app.services.drafting import generate_draft

    with patch("app.services.drafting.chat_text", new_callable=AsyncMock, return_value="Voice draft.") as mock_llm:
        result = await generate_draft(
            user_id=USER_ID,
            job_summary="Node.js backend role",
            profile_summary="Skills: javascript. Experience: mid.",
            voice_chunks=["Sample writing from portfolio...", "Another writing sample."],
        )

    assert result == "Voice draft."
    call_args = mock_llm.call_args
    messages = call_args[0][0]
    user_msg = messages[1]["content"]
    assert "voice" in user_msg.lower() or "style" in user_msg.lower() or "examples" in user_msg.lower(), (
        "Voice path should include voice examples in the user message"
    )
