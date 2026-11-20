"""P2-14: Stats endpoint GET /me/stats."""

import pytest
from sqlalchemy import text

from app.tests.conftest import engine

USER_ID = "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"
JOB_ID = "bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb"


async def _seed():
    from app.core.security import hash_password

    async with engine.begin() as conn:
        await conn.execute(text(
            "INSERT INTO users (id, email, password_hash, profile_complete) VALUES (:id, :email, :pw, true)"
        ), {"id": USER_ID, "email": "stats@test.com", "pw": hash_password("Test1234!")})

        await conn.execute(text(
            "INSERT INTO profiles (user_id, display_name, primary_category, skills, experience_level, profile_version) "
            "VALUES (:uid, 'Stats', 'Dev', :skills, 'mid', 1)"
        ), {"uid": USER_ID, "skills": ["python"]})

        await conn.execute(text(
            "INSERT INTO subscriptions (user_id, tier, period_end, drafts_quota, drafts_used) "
            "VALUES (:uid, 'free', '2027-12-31', 30, 5)"
        ), {"uid": USER_ID})

        await conn.execute(text(
            "INSERT INTO jobs (id, platform, external_id, title, description, url, raw) "
            "VALUES (:id, 'remoteok', 's-1', 'Job', 'Desc', 'https://x.com', '{}'::jsonb)"
        ), {"id": JOB_ID})

        # Insert a won proposal
        await conn.execute(text(
            "INSERT INTO proposals (user_id, job_id, content, status, outcome, voice_matched) "
            "VALUES (:uid, :jid, 'content', 'used', 'won', false)"
        ), {"uid": USER_ID, "jid": JOB_ID})


@pytest.mark.asyncio
async def test_stats_endpoint(client) -> None:
    await _seed()
    from app.core.security import create_access_token
    token = create_access_token(USER_ID)

    resp = await client.get("/me/stats", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200
    data = resp.json()
    assert data["proposals_total"] == 1
    assert data["proposals_won"] == 1
    assert data["win_rate"] == 1.0
    assert data["credits"]["drafts_used"] == 5


@pytest.mark.asyncio
async def test_stats_empty(client) -> None:
    from app.core.security import create_access_token, hash_password

    uid = "cccccccc-cccc-cccc-cccc-cccccccccccc"
    async with engine.begin() as conn:
        await conn.execute(text(
            "INSERT INTO users (id, email, password_hash) VALUES (:id, :email, :pw)"
        ), {"id": uid, "email": "empty@test.com", "pw": hash_password("Test1234!")})

    token = create_access_token(uid)
    resp = await client.get("/me/stats", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200
    assert resp.json()["proposals_total"] == 0
    assert resp.json()["win_rate"] == 0.0
