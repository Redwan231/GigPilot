"""P4-13: MCP server smoke test.

Directly exercises call_tool() from backend/mcp/server.py:
  - bad token → error text, not exception
  - search_jobs → returns job list (tenant-scoped read, no credit)
  - draft_proposal → LLM mocked, credit consumed (drafts_used + 1)
  - list_proposals → returns user's proposals only
  - set_outcome → updates proposal; foreign user's proposal → "not found"
"""

import importlib.util
import os
import sys
import uuid
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest
from sqlalchemy import text

from app.tests.conftest import engine

# ── unique UUID namespace for this test file ──────────────────────────────────
USER_A = "1a1a1a1a-1a1a-1a1a-1a1a-1a1a1a1a1a1a"
USER_B = "2b2b2b2b-2b2b-2b2b-2b2b-2b2b2b2b2b2b"
JOB_ID = "3c3c3c3c-3c3c-3c3c-3c3c-3c3c3c3c3c3c"
MCP_TOKEN = "mcp-smoke-test-token"

# ── load backend/mcp/server.py under a collision-free name ───────────────────
_MCP_FILE = Path(__file__).parent.parent.parent / "mcp" / "server.py"


def _load_mcp_server():
    """Import backend/mcp/server.py as 'gigpilot_mcp_server' to avoid shadowing
    the installed 'mcp' library (which the server itself imports from)."""
    module_name = "gigpilot_mcp_server"
    if module_name in sys.modules:
        return sys.modules[module_name]
    spec = importlib.util.spec_from_file_location(module_name, _MCP_FILE)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = mod
    spec.loader.exec_module(mod)
    return mod


# ── seed helpers ─────────────────────────────────────────────────────────────

async def _seed_user(user_id: str, email: str) -> None:
    from app.core.security import hash_password

    async with engine.begin() as conn:
        await conn.execute(
            text(
                "INSERT INTO users (id, email, password_hash, profile_complete) "
                "VALUES (:id, :email, :pw, true)"
            ),
            {"id": user_id, "email": email, "pw": hash_password("Test1234!")},
        )
        await conn.execute(
            text(
                "INSERT INTO profiles (user_id, display_name, primary_category, skills, "
                "experience_level, hourly_rate, profile_version) "
                "VALUES (:uid, 'MCP User', 'Development', :skills, 'senior', 100.00, 1)"
            ),
            {"uid": user_id, "skills": ["python", "fastapi"]},
        )
        await conn.execute(
            text(
                "INSERT INTO subscriptions "
                "(user_id, tier, period_end, drafts_quota, drafts_used) "
                "VALUES (:uid, 'free', '2027-12-31', 30, 0)"
            ),
            {"uid": user_id},
        )


async def _seed_job() -> None:
    async with engine.begin() as conn:
        await conn.execute(
            text(
                "INSERT INTO jobs (id, platform, external_id, title, description, url, raw) "
                "VALUES (:id, 'remoteok', 'mcp-smoke-1', 'Python Job', "
                "'Build APIs.', 'https://x.com/1', '{}'::jsonb)"
            ),
            {"id": JOB_ID},
        )


def _patch_env(token: str, user_id: str):
    """Reload MCP_AUTH_TOKEN / MCP_USER_ID into the loaded module."""
    os.environ["MCP_AUTH_TOKEN"] = token
    os.environ["MCP_USER_ID"] = user_id
    mcp = _load_mcp_server()
    mcp.MCP_AUTH_TOKEN = token
    mcp.MCP_USER_ID = user_id


# ── tests ─────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_mcp_bad_token_returns_error(clean_db) -> None:
    """call_tool with wrong token must return error text, never raise."""
    _patch_env(MCP_TOKEN, USER_A)
    mcp = _load_mcp_server()

    result = await mcp.call_tool("search_jobs", {"token": "WRONG-TOKEN"})
    assert len(result) == 1
    text_out = result[0].text
    assert "Error" in text_out or "error" in text_out.lower()


@pytest.mark.asyncio
async def test_mcp_search_jobs(clean_db) -> None:
    """search_jobs returns the seeded job."""
    await _seed_user(USER_A, "mcp_a@test.com")
    await _seed_job()
    _patch_env(MCP_TOKEN, USER_A)
    mcp = _load_mcp_server()

    result = await mcp.call_tool("search_jobs", {"token": MCP_TOKEN, "limit": 10})
    import json
    data = json.loads(result[0].text)
    assert "jobs" in data
    assert any(j["id"] == JOB_ID for j in data["jobs"])


@pytest.mark.asyncio
async def test_mcp_draft_consumes_credit(clean_db) -> None:
    """draft_proposal via MCP deducts exactly 1 credit."""
    await _seed_user(USER_A, "mcp_a@test.com")
    await _seed_job()
    _patch_env(MCP_TOKEN, USER_A)
    mcp = _load_mcp_server()

    _MOCK = {"draft": "Great proposal!", "voice_matched": False, "error": None}
    with patch("app.agents.graph.graph.ainvoke", new_callable=AsyncMock, return_value=_MOCK):
        result = await mcp.call_tool("draft_proposal", {"token": MCP_TOKEN, "job_id": JOB_ID})

    import json
    data = json.loads(result[0].text)
    assert "error" not in data or data.get("error") is None
    assert data.get("credits_remaining") == 29


@pytest.mark.asyncio
async def test_mcp_list_proposals(clean_db) -> None:
    """list_proposals returns user A's proposals only."""
    await _seed_user(USER_A, "mcp_a@test.com")
    await _seed_job()
    _patch_env(MCP_TOKEN, USER_A)
    mcp = _load_mcp_server()

    _MOCK = {"draft": "Proposal content.", "voice_matched": False, "error": None}
    with patch("app.agents.graph.graph.ainvoke", new_callable=AsyncMock, return_value=_MOCK):
        await mcp.call_tool("draft_proposal", {"token": MCP_TOKEN, "job_id": JOB_ID})

    result = await mcp.call_tool("list_proposals", {"token": MCP_TOKEN})
    import json
    data = json.loads(result[0].text)
    assert "proposals" in data
    assert len(data["proposals"]) == 1


@pytest.mark.asyncio
async def test_mcp_set_outcome(clean_db) -> None:
    """set_outcome updates the proposal's outcome field."""
    await _seed_user(USER_A, "mcp_a@test.com")
    await _seed_job()
    _patch_env(MCP_TOKEN, USER_A)
    mcp = _load_mcp_server()

    _MOCK = {"draft": "Proposal.", "voice_matched": False, "error": None}
    with patch("app.agents.graph.graph.ainvoke", new_callable=AsyncMock, return_value=_MOCK):
        draft_result_raw = await mcp.call_tool(
            "draft_proposal", {"token": MCP_TOKEN, "job_id": JOB_ID}
        )
    import json
    draft_data = json.loads(draft_result_raw[0].text)
    proposal_id = draft_data["proposal_id"]

    result = await mcp.call_tool(
        "set_outcome",
        {"token": MCP_TOKEN, "proposal_id": proposal_id, "outcome": "won"},
    )
    data = json.loads(result[0].text)
    assert data.get("outcome") == "won"


@pytest.mark.asyncio
async def test_mcp_tenant_isolation(clean_db) -> None:
    """User A cannot set_outcome on User B's proposal via MCP."""
    await _seed_user(USER_A, "mcp_a@test.com")
    await _seed_user(USER_B, "mcp_b@test.com")
    await _seed_job()

    # Create a proposal owned by user B
    async with engine.begin() as conn:
        result = await conn.execute(
            text(
                "INSERT INTO proposals (user_id, job_id, content, voice_matched) "
                "VALUES (:uid, :jid, 'B proposal', false) RETURNING id"
            ),
            {"uid": USER_B, "jid": JOB_ID},
        )
        b_proposal_id = str(result.fetchone()[0])

    # Authenticate as user A
    _patch_env(MCP_TOKEN, USER_A)
    mcp = _load_mcp_server()

    result = await mcp.call_tool(
        "set_outcome",
        {"token": MCP_TOKEN, "proposal_id": b_proposal_id, "outcome": "won"},
    )
    import json
    data = json.loads(result[0].text)
    assert "error" in data or "not found" in str(data).lower()
