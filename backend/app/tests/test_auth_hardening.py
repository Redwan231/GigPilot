"""P4-6: Auth hardening — brute-force rate limit (10/min on /login), refresh
reuse → full revoke, expired access token → 401."""

import datetime

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text

from app.core import security
from app.tests.conftest import engine
from app.main import app

EMAIL = "brute@test.com"
PASSWORD = "password1"


async def _signup(client: AsyncClient, email: str = EMAIL) -> dict:
    return await client.post("/auth/signup", json={"email": email, "password": PASSWORD})


@pytest.mark.asyncio
async def test_brute_force_login_rate_limited(client: AsyncClient) -> None:
    """More than 10 login attempts per minute from the same IP should trigger 429."""
    await _signup(client)

    responses = []
    for _ in range(12):
        r = await client.post(
            "/auth/login",
            json={"email": EMAIL, "password": "wrongpass1"},
        )
        responses.append(r.status_code)

    assert 429 in responses, (
        f"Expected at least one 429 after 12 rapid login attempts; got: {responses}"
    )


@pytest.mark.asyncio
async def test_refresh_reuse_outside_grace_revokes_all_tokens(client: AsyncClient) -> None:
    """Re-assert P1-8: stale revoked refresh token → 401 + all tokens revoked."""
    await _signup(client)
    r1 = client.cookies.get("refresh_token")

    await client.post("/auth/refresh")
    r2 = client.cookies.get("refresh_token")

    async with engine.begin() as conn:
        await conn.execute(
            text(
                "UPDATE refresh_tokens SET revoked_at = now() - interval '30 seconds' "
                "WHERE token_hash = :h"
            ),
            {"h": security.hash_refresh_token(r1)},
        )

    attacker = AsyncClient(transport=ASGITransport(app=app), base_url="http://testserver")
    async with attacker as c:
        c.cookies.set("refresh_token", r1)
        resp = await c.post("/auth/refresh")
    assert resp.status_code == 401

    legit = AsyncClient(transport=ASGITransport(app=app), base_url="http://testserver")
    async with legit as c:
        c.cookies.set("refresh_token", r2)
        resp2 = await c.post("/auth/refresh")
    assert resp2.status_code == 401, "Successor token must also be revoked after reuse attack"


@pytest.mark.asyncio
async def test_expired_access_token_returns_401(client: AsyncClient) -> None:
    """An access token past its expiry is rejected with 401."""
    signup = await _signup(client)
    user_id = signup.json()["user"]["id"]

    expired_token = security.create_access_token(
        user_id, expires_delta=datetime.timedelta(minutes=-1)
    )

    resp = await client.get("/me", headers={"Authorization": f"Bearer {expired_token}"})
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_malformed_token_returns_401(client: AsyncClient) -> None:
    """Tampered / garbage JWT is rejected."""
    await _signup(client)

    resp = await client.get("/me", headers={"Authorization": "Bearer not.a.real.token"})
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_missing_bearer_returns_401(client: AsyncClient) -> None:
    """Missing Authorization header returns 401."""
    resp = await client.get("/me")
    assert resp.status_code == 401
