"""Proposal drafting service (04_TRD §2, US-D1).

Voice RAG (top-K sample chunks) when available, cold-start template fallback.
Called via LangGraph draft_node. Endpoint: POST /jobs/{id}/draft."""

import logging

from app.ai.llm import chat_text
from app.guardrails.injection import delimit_untrusted
from app.guardrails.sanitize import sanitize_text

log = logging.getLogger(__name__)

_DRAFT_SYSTEM = """You are a freelance proposal writer. Write a professional, concise proposal for the job.

Guidelines:
- Match the tone and style from the voice examples if provided
- Address the job requirements directly
- 150-250 words, persuasive but not generic
- Do NOT invent credentials or experiences not mentioned in the profile
- End with a clear call to action"""

_COLD_START_SYSTEM = """You are a freelance proposal writer. Write a professional proposal using only the provided profile and job info.

Guidelines:
- 150-250 words, professional tone
- Address the job requirements directly
- Do NOT invent credentials
- End with a clear call to action"""


async def generate_draft(
    user_id: str,
    job_summary: str,
    profile_summary: str,
    voice_chunks: list[str],
    score: int | None = None,
) -> str:
    safe_job = delimit_untrusted(sanitize_text(job_summary), label="job_description")
    safe_profile = sanitize_text(profile_summary)

    if voice_chunks:
        voice_text = "\n---\n".join(voice_chunks[:5])
        user_msg = (
            f"Freelancer profile:\n{safe_profile}\n\n"
            f"Writing style examples (use these for tone/voice):\n{voice_text}\n\n"
            f"Job to apply for:\n{safe_job}\n\n"
            f"Write a proposal in the freelancer's voice."
        )
        system = _DRAFT_SYSTEM
    else:
        user_msg = (
            f"Freelancer profile:\n{safe_profile}\n\n"
            f"Job to apply for:\n{safe_job}\n\n"
            f"Write a professional proposal."
        )
        system = _COLD_START_SYSTEM

    draft = await chat_text(
        [
            {"role": "system", "content": system},
            {"role": "user", "content": user_msg},
        ],
        user_id=user_id,
        operation="draft",
        temperature=0.6,
        max_tokens=1024,
    )
    return draft.strip()
