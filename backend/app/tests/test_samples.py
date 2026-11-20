"""P2-2: Writing samples POST/GET/DELETE /me/samples (size/count limits)."""

import pytest
from httpx import AsyncClient


async def _auth(client: AsyncClient) -> dict[str, str]:
    r = await client.post(
        "/auth/signup", json={"email": "samples@example.com", "password": "password1"}
    )
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


@pytest.mark.asyncio
async def test_list_samples_empty(client: AsyncClient) -> None:
    h = await _auth(client)
    r = await client.get("/me/samples", headers=h)
    assert r.status_code == 200
    assert r.json() == []


@pytest.mark.asyncio
async def test_create_and_list_sample(client: AsyncClient) -> None:
    h = await _auth(client)
    r = await client.post(
        "/me/samples",
        json={"source_type": "paste", "content": "My sample proposal text."},
        headers=h,
    )
    assert r.status_code == 201
    body = r.json()
    assert body["source_type"] == "paste"
    assert body["content"] == "My sample proposal text."
    assert "id" in body

    r2 = await client.get("/me/samples", headers=h)
    assert len(r2.json()) == 1


@pytest.mark.asyncio
async def test_delete_sample(client: AsyncClient) -> None:
    h = await _auth(client)
    r = await client.post(
        "/me/samples",
        json={"content": "Delete me."},
        headers=h,
    )
    sid = r.json()["id"]
    r2 = await client.delete(f"/me/samples/{sid}", headers=h)
    assert r2.status_code == 204
    r3 = await client.get("/me/samples", headers=h)
    assert len(r3.json()) == 0


@pytest.mark.asyncio
async def test_max_samples_enforced(client: AsyncClient) -> None:
    h = await _auth(client)
    for i in range(5):
        r = await client.post(
            "/me/samples",
            json={"content": f"Sample {i} with enough text."},
            headers=h,
        )
        assert r.status_code == 201

    r = await client.post(
        "/me/samples",
        json={"content": "One too many."},
        headers=h,
    )
    assert r.status_code == 409


@pytest.mark.asyncio
async def test_content_too_long_rejected(client: AsyncClient) -> None:
    h = await _auth(client)
    r = await client.post(
        "/me/samples",
        json={"content": "x" * 20_001},
        headers=h,
    )
    assert r.status_code == 422


@pytest.mark.asyncio
async def test_empty_content_rejected(client: AsyncClient) -> None:
    h = await _auth(client)
    r = await client.post(
        "/me/samples",
        json={"content": "   "},
        headers=h,
    )
    assert r.status_code == 422


@pytest.mark.asyncio
async def test_delete_nonexistent_404(client: AsyncClient) -> None:
    h = await _auth(client)
    r = await client.delete(
        "/me/samples/00000000-0000-0000-0000-000000000099", headers=h
    )
    assert r.status_code == 404
