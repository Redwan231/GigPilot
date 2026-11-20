"""P2-1: GET /me (full) + PATCH /me/profile (upsert, version bump, onboarding)."""

import pytest
from httpx import AsyncClient

SIGNUP = {"email": "me@example.com", "password": "password1"}
PROFILE = {
    "display_name": "Rina",
    "primary_category": "Web Development",
    "skills": ["python", "react", "typescript"],
    "experience_level": "mid",
    "hourly_rate": 25.00,
    "bio": "Full-stack dev",
}


async def _auth_header(client: AsyncClient) -> dict[str, str]:
    r = await client.post("/auth/signup", json=SIGNUP)
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


@pytest.mark.asyncio
async def test_get_me_no_profile(client: AsyncClient) -> None:
    h = await _auth_header(client)
    r = await client.get("/me", headers=h)
    assert r.status_code == 200
    body = r.json()
    assert body["email"] == SIGNUP["email"]
    assert body["profile_complete"] is False
    assert body["profile"] is None


@pytest.mark.asyncio
async def test_patch_profile_creates_and_completes_onboarding(client: AsyncClient) -> None:
    h = await _auth_header(client)
    r = await client.patch("/me/profile", json=PROFILE, headers=h)
    assert r.status_code == 200
    body = r.json()
    assert body["profile_complete"] is True
    p = body["profile"]
    assert p["display_name"] == "Rina"
    assert p["skills"] == ["python", "react", "typescript"]
    assert p["experience_level"] == "mid"
    assert p["profile_version"] == 1


@pytest.mark.asyncio
async def test_patch_profile_bumps_version(client: AsyncClient) -> None:
    h = await _auth_header(client)
    await client.patch("/me/profile", json=PROFILE, headers=h)
    updated = {**PROFILE, "bio": "Updated bio"}
    r = await client.patch("/me/profile", json=updated, headers=h)
    assert r.status_code == 200
    assert r.json()["profile"]["profile_version"] == 2
    assert r.json()["profile"]["bio"] == "Updated bio"


@pytest.mark.asyncio
async def test_patch_profile_validation_errors(client: AsyncClient) -> None:
    h = await _auth_header(client)
    # Too few skills
    bad = {**PROFILE, "skills": ["python"]}
    r = await client.patch("/me/profile", json=bad, headers=h)
    assert r.status_code == 422
    # Invalid experience level
    bad2 = {**PROFILE, "experience_level": "guru"}
    r = await client.patch("/me/profile", json=bad2, headers=h)
    assert r.status_code == 422


@pytest.mark.asyncio
async def test_patch_profile_style_fields(client: AsyncClient) -> None:
    h = await _auth_header(client)
    with_style = {**PROFILE, "style_tone": "friendly", "style_length": "medium"}
    r = await client.patch("/me/profile", json=with_style, headers=h)
    assert r.status_code == 200
    p = r.json()["profile"]
    assert p["style_tone"] == "friendly"
    assert p["style_length"] == "medium"


@pytest.mark.asyncio
async def test_get_me_includes_profile_after_creation(client: AsyncClient) -> None:
    h = await _auth_header(client)
    await client.patch("/me/profile", json=PROFILE, headers=h)
    r = await client.get("/me", headers=h)
    assert r.status_code == 200
    body = r.json()
    assert body["profile_complete"] is True
    assert body["profile"]["display_name"] == "Rina"
