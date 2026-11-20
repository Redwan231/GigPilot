"""P2-3: Embeddings + chunking; embed samples on create, verify chunks+vectors dim=768."""

import uuid
from unittest.mock import MagicMock, patch

import pytest
from sqlalchemy import func, select, text

from app.ai.embeddings import CHUNK_OVERLAP, CHUNK_SIZE, chunk_text, embed_chunks
from app.db.models.sample import SampleChunk, WritingSample
from app.db.session import system_session


def test_chunk_text_short() -> None:
    chunks = chunk_text("Hello world")
    assert chunks == ["Hello world"]


def test_chunk_text_long() -> None:
    long = "a" * 1200
    chunks = chunk_text(long)
    assert len(chunks) >= 2
    assert all(len(c) <= CHUNK_SIZE for c in chunks)


def test_chunk_text_empty() -> None:
    assert chunk_text("") == []
    assert chunk_text("   ") == []


def test_chunk_overlap() -> None:
    text_val = "x" * (CHUNK_SIZE + 100)
    chunks = chunk_text(text_val)
    assert len(chunks) == 2
    # Second chunk should start at CHUNK_SIZE - OVERLAP
    assert len(chunks[1]) > CHUNK_OVERLAP


@pytest.mark.asyncio
async def test_embed_chunks_mock() -> None:
    fake_embedding = [0.1] * 768

    class FakeEmbedding:
        values = fake_embedding

    class FakeResult:
        embeddings = [FakeEmbedding(), FakeEmbedding()]

    fake_client = MagicMock()
    fake_client.models.embed_content.return_value = FakeResult()

    with patch("app.ai.embeddings.genai.Client", return_value=fake_client):
        result = await embed_chunks("Hello world. " * 100)
        assert len(result) >= 1
        idx, content, embedding = result[0]
        assert idx == 0
        assert len(embedding) == 768


@pytest.mark.asyncio
async def test_sample_create_embeds_chunks(client, clean_db) -> None:
    """Creating a sample with GEMINI_API_KEY set should produce chunks with dim=768 vectors."""
    fake_embedding = [0.01] * 768

    class FakeEmbedding:
        values = fake_embedding

    class FakeResult:
        embeddings: list

    def _mock_embed(model, contents):
        r = FakeResult()
        r.embeddings = [FakeEmbedding() for _ in contents]
        return r

    fake_client = MagicMock()
    fake_client.models.embed_content = _mock_embed

    r = await client.post(
        "/auth/signup", json={"email": "embed@example.com", "password": "password1"}
    )
    token = r.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    with (
        patch("app.api.routes.samples.settings") as mock_settings,
        patch("app.ai.embeddings.genai.Client", return_value=fake_client),
    ):
        # Copy real settings and set gemini key
        from app.config import settings as real_settings

        for field in real_settings.model_fields:
            setattr(mock_settings, field, getattr(real_settings, field))
        mock_settings.gemini_api_key = "fake-key"

        r = await client.post(
            "/me/samples",
            json={"content": "My writing sample for voice matching."},
            headers=headers,
        )
        assert r.status_code == 201
        sample_id = r.json()["id"]

    # Verify chunks were written with correct dim
    async with system_session() as session:
        count = await session.scalar(
            select(func.count()).select_from(SampleChunk).where(
                SampleChunk.sample_id == uuid.UUID(sample_id)
            )
        )
        assert count >= 1

        chunk = await session.scalar(
            select(SampleChunk).where(SampleChunk.sample_id == uuid.UUID(sample_id))
        )
        assert chunk is not None
        # Verify embedding dimension via raw SQL since the ORM type is custom
        dim = await session.scalar(
            text(
                "SELECT vector_dims(embedding) FROM sample_chunks WHERE id = :cid"
            ).bindparams(cid=chunk.id)
        )
        assert dim == 768
