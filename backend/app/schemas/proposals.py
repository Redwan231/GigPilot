"""Proposal schemas."""

import datetime
import uuid
from typing import Literal

from pydantic import BaseModel, Field


class ProposalOut(BaseModel):
    id: uuid.UUID
    job_id: uuid.UUID
    content: str
    status: str
    outcome: str
    voice_matched: bool
    created_at: datetime.datetime
    updated_at: datetime.datetime


class ProposalPatch(BaseModel):
    content: str | None = None
    status: Literal["draft", "used"] | None = None
    outcome: Literal["pending", "won", "lost", "no_response"] | None = None


class DraftRequest(BaseModel):
    pass


class DraftOut(BaseModel):
    proposal_id: uuid.UUID
    content: str
    voice_matched: bool
    credits_remaining: int
