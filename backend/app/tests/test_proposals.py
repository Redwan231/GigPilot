"""P2-11/P2-12/P2-13: Draft + Credits + Proposals API."""

import uuid
from decimal import Decimal
from unittest.mock import AsyncMock, patch

import pytest
from sqlalchemy import text

from app.tests.conftest import engine

USER_ID = "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"
JOB_ID = "bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb"


async def _seed():
    from app.core.security import hash_password

    async with engine.begin() as conn:
        await conn.execute(text(
            "INSERT INTO users (id, email, password_hash, profile_complete) "
            "VALUES (:id, :email, :pw, true)"
        ), {"id": USER_ID, "email": "proposals@test.com", "pw": hash_password("Test1234!")})

        await conn.execute(text(
            "INSERT INTO profiles (user_id, display_name, primary_category, skills, experience_level, profile_version) "
            "VALUES (:uid, 'Proposer', 'Dev', :skills, 'mid', 1)"
        ), {"uid": USER_ID, "skills": ["python"]})

        await conn.execute(text(
            "INSERT INTO subscriptions (user_id, tier, period_end, drafts_quota, drafts_used) "
            "VALUES (:uid, 'free', '2027-12-31', 30, 0)"
        ), {"uid": USER_ID})

        await conn.execute(text(
            "INSERT INTO jobs (id, platform, external_id, title, description, url, raw) "
            "VALUES (:id, 'remoteok', 'p-1', 'Python Dev', 'Build stuff.', 'https://x.com', '{}'::jsonb)"
        ), {"id": JOB_ID})


_MOCK_GRAPH_RESULT = {
    "draft": "Dear hiring manager, I am a great fit for this role.",
    "voice_matched": False,
    "error": None,
}


@pytest.mark.asyncio
async def test_draft_creates_proposal(client) -> None:
    await _seed()
    from app.core.security import create_access_token
    token = create_access_token(USER_ID)

    with patch("app.api.routes.proposals.agent_graph") as mock_graph:
        mock_graph.ainvoke = AsyncMock(return_value=_MOCK_GRAPH_RESULT)
        resp = await client.post(
            f"/jobs/{JOB_ID}/draft",
            headers={"Authorization": f"Bearer {token}"},
        )

    assert resp.status_code == 200
    data = resp.json()
    assert "Dear hiring manager" in data["content"]
    assert data["credits_remaining"] == 29


@pytest.mark.asyncio
async def test_draft_deducts_credit_only_on_success(client) -> None:
    await _seed()
    from app.core.security import create_access_token
    token = create_access_token(USER_ID)

    with patch("app.api.routes.proposals.agent_graph") as mock_graph:
        mock_graph.ainvoke = AsyncMock(return_value={"draft": None, "voice_matched": False, "error": "LLM failed"})
        resp = await client.post(
            f"/jobs/{JOB_ID}/draft",
            headers={"Authorization": f"Bearer {token}"},
        )

    assert resp.status_code == 502

    # Credit should be released — verify drafts_used is still 0
    async with engine.begin() as conn:
        row = await conn.execute(text("SELECT drafts_used FROM subscriptions WHERE user_id = :uid"), {"uid": USER_ID})
        used = row.scalar()
    assert used == 0


@pytest.mark.asyncio
async def test_list_proposals_empty(client) -> None:
    await _seed()
    from app.core.security import create_access_token
    token = create_access_token(USER_ID)

    resp = await client.get("/proposals", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200
    assert resp.json() == []


@pytest.mark.asyncio
async def test_patch_proposal_outcome(client) -> None:
    await _seed()
    from app.core.security import create_access_token
    token = create_access_token(USER_ID)

    with patch("app.api.routes.proposals.agent_graph") as mock_graph:
        mock_graph.ainvoke = AsyncMock(return_value=_MOCK_GRAPH_RESULT)
        draft_resp = await client.post(
            f"/jobs/{JOB_ID}/draft",
            headers={"Authorization": f"Bearer {token}"},
        )
    assert draft_resp.status_code == 200
    proposal_id = draft_resp.json()["proposal_id"]

    patch_resp = await client.patch(
        f"/proposals/{proposal_id}",
        json={"outcome": "won"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert patch_resp.status_code == 200
    assert patch_resp.json()["outcome"] == "won"


@pytest.mark.asyncio
async def test_delete_proposal(client) -> None:
    await _seed()
    from app.core.security import create_access_token
    token = create_access_token(USER_ID)

    with patch("app.api.routes.proposals.agent_graph") as mock_graph:
        mock_graph.ainvoke = AsyncMock(return_value=_MOCK_GRAPH_RESULT)
        draft_resp = await client.post(
            f"/jobs/{JOB_ID}/draft",
            headers={"Authorization": f"Bearer {token}"},
        )
    proposal_id = draft_resp.json()["proposal_id"]

    del_resp = await client.delete(
        f"/proposals/{proposal_id}",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert del_resp.status_code == 204
