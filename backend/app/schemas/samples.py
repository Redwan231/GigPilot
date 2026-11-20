"""Schemas for writing samples endpoints."""

import datetime
import uuid

from pydantic import BaseModel, ConfigDict, field_validator

MAX_SAMPLE_LENGTH = 20_000
MAX_SAMPLES_PER_USER = 5


class SampleCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    source_type: str = "paste"
    content: str

    @field_validator("source_type")
    @classmethod
    def _valid_source(cls, v: str) -> str:
        if v not in ("paste", "upload"):
            raise ValueError("source_type must be 'paste' or 'upload'")
        return v

    @field_validator("content")
    @classmethod
    def _content_limits(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("content must not be empty")
        if len(v) > MAX_SAMPLE_LENGTH:
            raise ValueError(f"content must be at most {MAX_SAMPLE_LENGTH} characters")
        return v


class SampleOut(BaseModel):
    id: uuid.UUID
    user_id: uuid.UUID
    source_type: str
    content: str
    created_at: datetime.datetime
