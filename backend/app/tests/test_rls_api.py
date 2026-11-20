"""P4-7: RLS penetration test at API level — user A's token cannot access user B's
proposals, samples, stats, or profile. Re-asserts P1-10 at the HTTP boundary."""

import pytest
from sqlalchemy import text

from app.tests.conftest import engine

USER_A = "aaaaaa01-aaaa-aaaa-aaaa-aaaaaaaaaaaa"
USER_B = "bbbbbb02-bbbb-bbbb-bbbb-bbbbbbbbbbbb"
JOB_ID = "cccccc03-cccc-cccc-cccc-cccccccccccc"


async def _seed() -> tuple[str, str]:
    from app.core.security import create_access_token, hash_password

    async with engine.begin() as conn:
        for uid, email in [(USER_A, "rls_a@test.com"), (USER_B, "rls_b@test.com")]:
            await conn.execute(
                text(
                    "INSERT INTO users (id, email, password_hash, profile_complete) "
                    "VALUES (:id, :email, :pw, true)"
                ),
                {"id": uid, "email": email, "pw": hash_password("Test1234!")},
            )
            await conn.execute(
                text(
                    "INSERT INTO profiles (user_id, display_name, primary_category, skills, "
                    "experience_level, profile_version) "
                    "VALUES (:uid, :name, 'Development', :skills, 'mid', 1)"
                ),
                {"uid": uid, "name": f"User {uid[:4]}", "skills": ["python"]},
            )
            await conn.execute(
                text(
                    "INSERT INTO subscriptions (user_id, tier, period_end, drafts_quota) "
                    "VALUES (:uid, 'free', '2027-12-31', 30)"
                ),
                {"uid": uid},
            )

        await conn.execute(
            text(
                "INSERT INTO jobs (id, platform, external_id, title, description, url, raw) "
                "VALUES (:id, 'remoteok', 'rls-1', 'Job', 'Desc.', 'https://x.com', '{}'::jsonb)"
            ),
            {"id": JOB_ID},
        )

        # Seed User B's proposal
        await conn.execute(
            text(
                "INSERT INTO proposals (user_id, job_id, content) VALUES (:uid, :jid, 'B proposal')"
            ),
            {"uid": USER_B, "jid": JOB_ID},
        )

    return create_access_token(USER_A), create_access_token(USER_B)


@pytest.mark.asyncio
async def test_user_a_cannot_see_user_b_proposals(client) -> None:
    """GET /proposals with user A's token returns only A's proposals (B's are hidden)."""
    token_a, token_b = await _seed()

    resp_a = await client.get("/proposals", headers={"Authorization": f"Bearer {token_a}"})
    assert resp_a.status_code == 200
    proposal_ids_a = [p["id"] for p in resp_a.json()]

    resp_b = await client.get("/proposals", headers={"Authorization": f"Bearer {token_b}"})
    assert resp_b.status_code == 200
    proposal_ids_b = [p["id"] for p in resp_b.json()]

    # B has one proposal; A has none
    assert len(proposal_ids_b) == 1
    assert len(proposal_ids_a) == 0


@pytest.mark.asyncio
async def test_user_a_cannot_fetch_user_b_proposal_directly(client) -> None:
    """GET /proposals/{b_proposal_id} with user A's token returns 404."""
    token_a, token_b = await _seed()

    # Get B's proposal id
    resp_b = await client.get("/proposals", headers={"Authorization": f"Bearer {token_b}"})
    assert len(resp_b.json()) == 1
    b_proposal_id = resp_b.json()[0]["id"]

    # A tries to fetch it
    resp = await client.get(
        f"/proposals/{b_proposal_id}",
        headers={"Authorization": f"Bearer {token_a}"},
    )
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_user_a_cannot_patch_user_b_proposal(client) -> None:
    """PATCH /proposals/{b_proposal_id} with user A's token returns 404."""
    token_a, token_b = await _seed()

    resp_b = await client.get("/proposals", headers={"Authorization": f"Bearer {token_b}"})
    b_proposal_id = resp_b.json()[0]["id"]

    resp = await client.patch(
        f"/proposals/{b_proposal_id}",
        json={"outcome": "won"},
        headers={"Authorization": f"Bearer {token_a}"},
    )
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_user_a_cannot_delete_user_b_proposal(client) -> None:
    """DELETE /proposals/{b_proposal_id} with user A's token returns 404."""
    token_a, token_b = await _seed()

    resp_b = await client.get("/proposals", headers={"Authorization": f"Bearer {token_b}"})
    b_proposal_id = resp_b.json()[0]["id"]

    resp = await client.delete(
        f"/proposals/{b_proposal_id}",
        headers={"Authorization": f"Bearer {token_a}"},
    )
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_user_a_cannot_see_user_b_samples(client) -> None:
    """GET /me/samples returns only the authenticated user's samples."""
    token_a, token_b = await _seed()

    # Seed a sample for B
    await client.post(
        "/me/samples",
        json={"content": "This is my portfolio sample.", "title": "My Work"},
        headers={"Authorization": f"Bearer {token_b}"},
    )

    resp_a = await client.get("/me/samples", headers={"Authorization": f"Bearer {token_a}"})
    assert resp_a.status_code == 200
    assert len(resp_a.json()) == 0, "User A should see 0 samples (they're User B's)"


@pytest.mark.asyncio
async def test_forged_user_id_in_body_is_ignored(client) -> None:
    """user_id in request body is never used; server always uses the JWT sub claim."""
    token_a, _ = await _seed()

    # Try to PATCH user B's profile by guessing the user_id — the dep ignores body user_id
    resp = await client.patch(
        "/me/profile",
        json={
            "display_name": "Hacker",
            "user_id": USER_B,  # attempt injection via body
        },
        headers={"Authorization": f"Bearer {token_a}"},
    )
    # Should update A's profile, not B's (or succeed for A, 422 for unknown field)
    assert resp.status_code in (200, 422)
    if resp.status_code == 200:
        assert resp.json()["user_id"] == USER_A
