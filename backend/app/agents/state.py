"""GigPilot LangGraph agent state (04_TRD §2)."""

import uuid
from typing import TypedDict


class GigPilotState(TypedDict):
    user_id: str
    job_id: str
    profile_summary: str
    job_summary: str
    score: int | None
    voice_chunks: list[str]
    draft: str | None
    voice_matched: bool
    error: str | None
