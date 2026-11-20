"""Gemini gemini-embedding-001 embeddings via google-genai SDK (04_TRD §4.2).

Provides chunking + embedding for writing samples (Voice RAG). Embedding dim
is locked to 768. Chunks are ~500 chars with overlap to preserve context."""

from google import genai

from app.config import settings

CHUNK_SIZE = 500
CHUNK_OVERLAP = 100


def chunk_text(text: str) -> list[str]:
    text = text.strip()
    if not text:
        return []
    if len(text) <= CHUNK_SIZE:
        return [text]
    chunks: list[str] = []
    start = 0
    while start < len(text):
        end = start + CHUNK_SIZE
        chunk = text[start:end]
        if chunk.strip():
            chunks.append(chunk.strip())
        start += CHUNK_SIZE - CHUNK_OVERLAP
    return chunks


async def embed_texts(texts: list[str]) -> list[list[float]]:
    if not texts:
        return []
    client = genai.Client(api_key=settings.gemini_api_key)
    result = client.models.embed_content(
        model=settings.embedding_model,
        contents=texts,
    )
    return [list(e.values) for e in result.embeddings]


async def embed_chunks(text: str) -> list[tuple[int, str, list[float]]]:
    """Chunk text and embed each chunk. Returns [(chunk_index, content, embedding)]."""
    chunks = chunk_text(text)
    if not chunks:
        return []
    embeddings = await embed_texts(chunks)
    return [(i, c, e) for i, (c, e) in enumerate(zip(chunks, embeddings))]
