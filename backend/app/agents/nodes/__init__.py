"""LangGraph node implementations (04_TRD §2)."""

import logging

from sqlalchemy import text

from app.agents.state import GigPilotState
from app.db.session import system_session

log = logging.getLogger(__name__)

VOICE_TOP_K = 5


async def retrieve_voice_node(state: GigPilotState) -> GigPilotState:
    """Retrieve top-K writing sample chunks for the user via ANN (cosine)."""
    user_id = state["user_id"]
    job_summary = state.get("job_summary", "")

    voice_chunks: list[str] = []
    voice_matched = False

    try:
        from app.ai.embeddings import embed_texts

        query_embeddings = await embed_texts([job_summary])
        if query_embeddings:
            query_vec = query_embeddings[0]
            vec_str = "[" + ",".join(str(v) for v in query_vec) + "]"

            async with system_session() as session:
                rows = await session.execute(
                    text(
                        "SELECT content FROM sample_chunks "
                        "WHERE user_id = :uid "
                        "ORDER BY embedding <=> CAST(:vec AS vector) "
                        f"LIMIT {VOICE_TOP_K}"
                    ),
                    {"uid": user_id, "vec": vec_str},
                )
                voice_chunks = [r[0] for r in rows.fetchall()]
                voice_matched = len(voice_chunks) > 0
    except Exception as exc:
        log.warning("Voice retrieval failed: %s", exc)

    return {**state, "voice_chunks": voice_chunks, "voice_matched": voice_matched}


async def draft_node(state: GigPilotState) -> GigPilotState:
    """Generate proposal draft using voice chunks or cold-start template."""
    from app.services.drafting import generate_draft

    try:
        draft = await generate_draft(
            user_id=state["user_id"],
            job_summary=state["job_summary"],
            profile_summary=state["profile_summary"],
            voice_chunks=state.get("voice_chunks", []),
            score=state.get("score"),
        )
        return {**state, "draft": draft, "error": None}
    except Exception as exc:
        log.error("Draft generation failed: %s", exc)
        return {**state, "draft": None, "error": str(exc)}
