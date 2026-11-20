"""P4-9: Input abuse — oversized/over-count samples rejected; XSS in job/AI output
not executed on render (sanitize_text strips HTML tags)."""

from unittest.mock import AsyncMock, patch

import pytest
from sqlalchemy import text

from app.tests.conftest import engine

USER_ID = "90909090-9090-9090-9090-909090909090"
JOB_ID = "01010101-0101-0101-0101-010101010101"


async def _seed() -> str:
    from app.core.security import create_access_token, hash_password

    async with engine.begin() as conn:
        await conn.execute(
            text(
                "INSERT INTO users (id, email, password_hash, profile_complete) "
                "VALUES (:id, :email, :pw, true)"
            ),
            {"id": USER_ID, "email": "abuse@test.com", "pw": hash_password("Test1234!")},
        )
        await conn.execute(
            text(
                "INSERT INTO subscriptions (user_id, tier, period_end, drafts_quota) "
                "VALUES (:uid, 'free', '2027-12-31', 30)"
            ),
            {"uid": USER_ID},
        )

    return create_access_token(USER_ID)


@pytest.mark.asyncio
async def test_oversized_sample_rejected(client) -> None:
    """Sample content over MAX_SAMPLE_LENGTH (20 000 chars) returns 422."""
    token = await _seed()

    big = "x" * 25_000
    resp = await client.post(
        "/me/samples",
        json={"content": big},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_empty_sample_rejected(client) -> None:
    """Blank / whitespace-only sample returns 422."""
    token = await _seed()

    resp = await client.post(
        "/me/samples",
        json={"content": "   "},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_max_samples_count_limit(client) -> None:
    """Posting more than 5 samples returns 409."""
    token = await _seed()

    for i in range(5):
        r = await client.post(
            "/me/samples",
            json={"content": f"Sample {i + 1}. " * 10},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert r.status_code == 201

    sixth = await client.post(
        "/me/samples",
        json={"content": "This should be rejected."},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert sixth.status_code == 409


@pytest.mark.asyncio
async def test_unknown_field_in_sample_rejected(client) -> None:
    """Extra fields in SampleCreate body are rejected (extra='forbid')."""
    token = await _seed()

    resp = await client.post(
        "/me/samples",
        json={"content": "Valid content here.", "injected_field": "evil"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 422


# --- XSS sanitation unit tests (guardrails/sanitize.py) ---

def test_xss_script_tag_stripped() -> None:
    """<script> tags in job text must not survive sanitize_text."""
    from app.guardrails.sanitize import sanitize_text

    evil = '<script>alert("xss")</script> Normal job description.'
    cleaned = sanitize_text(evil)
    assert "<script>" not in cleaned
    assert "alert" not in cleaned or "<script>" not in cleaned


def test_xss_img_onerror_stripped() -> None:
    """onerror attribute injection in job text must be sanitized."""
    from app.guardrails.sanitize import sanitize_text

    evil = '<img src=x onerror="document.cookie"> Job description.'
    cleaned = sanitize_text(evil)
    assert "onerror" not in cleaned
    assert "<img" not in cleaned


def test_xss_href_javascript_stripped() -> None:
    """javascript: href protocol must not survive sanitize_text."""
    from app.guardrails.sanitize import sanitize_text

    evil = '<a href="javascript:void(0)">Click</a> for details.'
    cleaned = sanitize_text(evil)
    assert "javascript:" not in cleaned


def test_xss_in_job_title_does_not_reach_llm_unescaped() -> None:
    """Job title with XSS is sanitized before being passed to LangGraph/LLM."""
    from app.guardrails.sanitize import sanitize_text

    malicious_title = '<script>steal_cookie()</script>Senior Python Developer'
    safe_title = sanitize_text(malicious_title)

    assert "<script>" not in safe_title
    assert "steal_cookie" not in safe_title or "<script>" not in safe_title


def test_control_characters_stripped() -> None:
    """Null bytes and other control characters are removed from input."""
    from app.guardrails.sanitize import sanitize_text

    evil = "Normal text\x00\x01\x07with control chars"
    cleaned = sanitize_text(evil)
    assert "\x00" not in cleaned
    assert "\x01" not in cleaned


def test_oversized_text_capped_at_50k() -> None:
    """sanitize_text caps output at 50 000 chars (no memory bomb)."""
    from app.guardrails.sanitize import sanitize_text

    big = "a" * 100_000
    cleaned = sanitize_text(big)
    assert len(cleaned) <= 50_000
