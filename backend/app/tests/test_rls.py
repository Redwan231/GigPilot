"""P1-10 — critical security gate: Row-Level Security tenant isolation.

Proves at the real session layer (SET LOCAL ROLE gigpilot_app + app.current_user_id
GUC) that one user cannot read or write another user's rows, even when a forged
user_id is supplied. This exercises the same `tenant_session` the API uses, against
real Postgres with the non-BYPASSRLS tenant role.
"""

import uuid

import pytest
from sqlalchemy import func, select
from sqlalchemy.exc import DBAPIError

from app.db.models.job import Job
from app.db.models.proposal import Proposal
from app.db.models.sample import WritingSample
from app.db.models.user import User
from app.db.session import system_session, tenant_session


async def _seed_user(session, email: str) -> uuid.UUID:
    user = User(email=email, password_hash="x", email_verified=True)
    session.add(user)
    await session.flush()
    session.add(WritingSample(user_id=user.id, source_type="paste", content=f"voice-{email}"))
    return user.id


@pytest.mark.asyncio
async def test_rls_tenant_cannot_read_other_users_rows(clean_db: None) -> None:
    # Seed two users + one global job + a proposal each (privileged system session).
    async with system_session() as s:
        a_id = await _seed_user(s, "a@example.com")
        b_id = await _seed_user(s, "b@example.com")
        job = Job(platform="t", external_id="1", title="t", description="d", url="u", raw={})
        s.add(job)
        await s.flush()
        s.add(Proposal(user_id=a_id, job_id=job.id, content="A proposal"))
        s.add(Proposal(user_id=b_id, job_id=job.id, content="B proposal"))

    # Under A's tenant session: only A's rows are visible.
    async with tenant_session(a_id) as s:
        sample_owners = set((await s.scalars(select(WritingSample.user_id))).all())
        assert sample_owners == {a_id}

        proposal_owners = set((await s.scalars(select(Proposal.user_id))).all())
        assert proposal_owners == {a_id}

        # Forged id: explicitly query for B's rows while acting as A -> nothing.
        b_sample = await s.scalar(select(WritingSample).where(WritingSample.user_id == b_id))
        assert b_sample is None
        b_count = await s.scalar(
            select(func.count()).select_from(Proposal).where(Proposal.user_id == b_id)
        )
        assert b_count == 0

    # Symmetric: B sees only B.
    async with tenant_session(b_id) as s:
        assert set((await s.scalars(select(WritingSample.user_id))).all()) == {b_id}


@pytest.mark.asyncio
async def test_rls_forged_insert_is_rejected(clean_db: None) -> None:
    async with system_session() as s:
        a_id = await _seed_user(s, "a2@example.com")
        b_id = await _seed_user(s, "b2@example.com")
        job = Job(platform="t", external_id="2", title="t", description="d", url="u", raw={})
        s.add(job)
        await s.flush()
        job_id = job.id

    # Acting as A, inserting a row owned by B must violate the WITH CHECK policy.
    with pytest.raises(DBAPIError):
        async with tenant_session(a_id) as s:
            s.add(Proposal(user_id=b_id, job_id=job_id, content="forged for B"))
            await s.flush()

    # And nothing leaked: B still has no proposals (checked privileged).
    async with system_session() as s:
        count = await s.scalar(
            select(func.count()).select_from(Proposal).where(Proposal.user_id == b_id)
        )
        assert count == 0


@pytest.mark.asyncio
async def test_rls_forged_update_delete_affect_no_rows(clean_db: None) -> None:
    async with system_session() as s:
        a_id = await _seed_user(s, "a3@example.com")
        b_id = await _seed_user(s, "b3@example.com")

    # Acting as A, try to delete B's sample by its (forged) owner id -> 0 rows.
    async with tenant_session(a_id) as s:
        from sqlalchemy import delete, update

        deleted = await s.execute(delete(WritingSample).where(WritingSample.user_id == b_id))
        assert deleted.rowcount == 0
        updated = await s.execute(
            update(WritingSample).where(WritingSample.user_id == b_id).values(content="hacked")
        )
        assert updated.rowcount == 0

    # B's sample is intact.
    async with system_session() as s:
        sample = await s.scalar(select(WritingSample).where(WritingSample.user_id == b_id))
        assert sample is not None
        assert sample.content == "voice-b3@example.com"


@pytest.mark.asyncio
async def test_api_token_maps_to_own_user_only(client) -> None:
    a = await client.post(
        "/auth/signup", json={"email": "api-a@example.com", "password": "password1"}
    )
    token_a = a.json()["access_token"]
    b = await client.post(
        "/auth/signup", json={"email": "api-b@example.com", "password": "password1"}
    )
    token_b = b.json()["access_token"]

    me_a = await client.get("/me", headers={"Authorization": f"Bearer {token_a}"})
    me_b = await client.get("/me", headers={"Authorization": f"Bearer {token_b}"})
    assert me_a.json()["email"] == "api-a@example.com"
    assert me_b.json()["email"] == "api-b@example.com"
    # Identity is taken from the signed token (sub), never from any request input.
    assert me_a.json()["id"] != me_b.json()["id"]
