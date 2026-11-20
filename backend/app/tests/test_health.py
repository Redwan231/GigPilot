"""P2-16: Health check endpoints."""

import pytest


@pytest.mark.asyncio
async def test_health_liveness(client) -> None:
    resp = await client.get("/health")
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"


@pytest.mark.asyncio
async def test_health_ready(client) -> None:
    resp = await client.get("/health/ready")
    # DB is up in tests; Redis may not be — just check the response schema
    assert resp.status_code in (200, 503)
    data = resp.json()
    assert "status" in data
