"""P1-9: a protected route rejects missing/invalid tokens and accepts a valid one."""

import pytest
from httpx import AsyncClient

EMAIL = "deps@example.com"
PASSWORD = "password1"


@pytest.mark.asyncio
async def test_me_requires_token(client: AsyncClient) -> None:
    resp = await client.get("/me")
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_me_rejects_invalid_token(client: AsyncClient) -> None:
    resp = await client.get("/me", headers={"Authorization": "Bearer not.a.valid.jwt"})
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_me_accepts_valid_token(client: AsyncClient) -> None:
    signup = await client.post("/auth/signup", json={"email": EMAIL, "password": PASSWORD})
    token = signup.json()["access_token"]
    resp = await client.get("/me", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200
    body = resp.json()
    assert body["email"] == EMAIL
    assert body["profile_complete"] is False
