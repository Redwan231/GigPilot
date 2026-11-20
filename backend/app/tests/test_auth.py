"""Integration tests for the auth endpoints (P1-8): happy path, 401s, rotation,
and refresh-reuse detection."""

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text

from app.core import security
from app.db.session import engine
from app.main import app

EMAIL = "rina@example.com"
PASSWORD = "password1"


async def _signup(client: AsyncClient, email: str = EMAIL) -> dict:
    resp = await client.post("/auth/signup", json={"email": email, "password": PASSWORD})
    return resp


@pytest.mark.asyncio
async def test_signup_happy(client: AsyncClient) -> None:
    resp = await _signup(client)
    assert resp.status_code == 201
    body = resp.json()
    assert body["access_token"]
    assert body["token_type"] == "bearer"
    assert body["user"]["email"] == EMAIL
    assert body["user"]["profile_complete"] is False
    assert client.cookies.get("refresh_token")

    claims = security.decode_access_token(body["access_token"])
    assert claims["sub"] == body["user"]["id"]


@pytest.mark.asyncio
async def test_signup_duplicate_email(client: AsyncClient) -> None:
    assert (await _signup(client)).status_code == 201
    dup = await _signup(client)
    assert dup.status_code == 409


@pytest.mark.asyncio
async def test_signup_weak_password(client: AsyncClient) -> None:
    resp = await client.post("/auth/signup", json={"email": "x@y.com", "password": "short"})
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_login_happy(client: AsyncClient) -> None:
    await _signup(client)
    resp = await client.post("/auth/login", json={"email": EMAIL, "password": PASSWORD})
    assert resp.status_code == 200
    assert resp.json()["access_token"]


@pytest.mark.asyncio
async def test_login_wrong_password(client: AsyncClient) -> None:
    await _signup(client)
    resp = await client.post("/auth/login", json={"email": EMAIL, "password": "wrongpass1"})
    assert resp.status_code == 401
    assert resp.json()["detail"] == "Email or password is incorrect."


@pytest.mark.asyncio
async def test_login_unknown_email(client: AsyncClient) -> None:
    resp = await client.post(
        "/auth/login", json={"email": "nobody@example.com", "password": PASSWORD}
    )
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_refresh_rotation(client: AsyncClient) -> None:
    signup = await _signup(client)
    access1 = signup.json()["access_token"]
    r1 = client.cookies.get("refresh_token")

    resp = await client.post("/auth/refresh")
    assert resp.status_code == 200
    access2 = resp.json()["access_token"]
    r2 = client.cookies.get("refresh_token")

    assert r2 and r2 != r1  # rotated
    assert access2  # new access issued (may equal if same second; token itself fresh)

    # A second rotation also works (chain).
    resp2 = await client.post("/auth/refresh")
    assert resp2.status_code == 200
    assert client.cookies.get("refresh_token") not in (r1, r2)
    assert access1  # sanity


@pytest.mark.asyncio
async def test_refresh_missing_and_invalid(client: AsyncClient) -> None:
    # No cookie at all.
    bare = AsyncClient(transport=ASGITransport(app=app), base_url="http://testserver")
    async with bare as c:
        assert (await c.post("/auth/refresh")).status_code == 401
        c.cookies.set("refresh_token", "not-a-real-token")
        assert (await c.post("/auth/refresh")).status_code == 401


@pytest.mark.asyncio
async def test_refresh_reuse_outside_grace_revokes_all(client: AsyncClient) -> None:
    await _signup(client)
    r1 = client.cookies.get("refresh_token")

    # Rotate: r1 -> r2 (r1 now revoked).
    await client.post("/auth/refresh")
    r2 = client.cookies.get("refresh_token")

    # Age r1's revocation beyond the grace window.
    async with engine.begin() as conn:
        await conn.execute(
            text(
                "UPDATE refresh_tokens SET revoked_at = now() - interval '30 seconds' "
                "WHERE token_hash = :h"
            ),
            {"h": security.hash_refresh_token(r1)},
        )

    # Present the stale revoked r1 -> reuse attack -> 401 + revoke all.
    attacker = AsyncClient(transport=ASGITransport(app=app), base_url="http://testserver")
    async with attacker as c:
        c.cookies.set("refresh_token", r1)
        assert (await c.post("/auth/refresh")).status_code == 401

    # r2 (the previously-valid successor) must now also be revoked.
    legit = AsyncClient(transport=ASGITransport(app=app), base_url="http://testserver")
    async with legit as c:
        c.cookies.set("refresh_token", r2)
        assert (await c.post("/auth/refresh")).status_code == 401


@pytest.mark.asyncio
async def test_logout_is_final(client: AsyncClient) -> None:
    await _signup(client)
    r1 = client.cookies.get("refresh_token")

    out = await client.post("/auth/logout")
    assert out.status_code == 204

    # The logged-out token cannot be refreshed (no valid successor exists).
    c2 = AsyncClient(transport=ASGITransport(app=app), base_url="http://testserver")
    async with c2 as c:
        c.cookies.set("refresh_token", r1)
        assert (await c.post("/auth/refresh")).status_code == 401
