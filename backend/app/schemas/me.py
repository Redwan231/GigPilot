"""Schemas for /me endpoints (profile, credits)."""

import uuid
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, field_validator


class ProfileOut(BaseModel):
    user_id: uuid.UUID
    display_name: str
    primary_category: str
    skills: list[str]
    experience_level: str
    hourly_rate: Decimal | None
    bio: str | None
    style_tone: str | None
    style_length: str | None
    style_greeting: str | None
    profile_version: int


class MeOut(BaseModel):
    id: uuid.UUID
    email: str
    email_verified: bool
    profile_complete: bool
    profile: ProfileOut | None = None


_VALID_EXPERIENCE = {"junior", "mid", "senior"}
_VALID_TONE = {"formal", "friendly", "direct"}
_VALID_LENGTH = {"short", "medium", "long"}


class ProfileUpsert(BaseModel):
    model_config = ConfigDict(extra="forbid")

    display_name: str
    primary_category: str
    skills: list[str]
    experience_level: str
    hourly_rate: Decimal | None = None
    bio: str | None = None
    style_tone: str | None = None
    style_length: str | None = None
    style_greeting: str | None = None

    @field_validator("display_name")
    @classmethod
    def _nonempty_name(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("display_name must not be empty")
        return v

    @field_validator("primary_category")
    @classmethod
    def _nonempty_category(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("primary_category must not be empty")
        return v

    @field_validator("skills")
    @classmethod
    def _min_skills(cls, v: list[str]) -> list[str]:
        v = [s.strip() for s in v if s.strip()]
        if len(v) < 3:
            raise ValueError("at least 3 skills are required")
        return v

    @field_validator("experience_level")
    @classmethod
    def _valid_level(cls, v: str) -> str:
        if v not in _VALID_EXPERIENCE:
            raise ValueError(f"experience_level must be one of {_VALID_EXPERIENCE}")
        return v

    @field_validator("style_tone")
    @classmethod
    def _valid_tone(cls, v: str | None) -> str | None:
        if v is not None and v not in _VALID_TONE:
            raise ValueError(f"style_tone must be one of {_VALID_TONE}")
        return v

    @field_validator("style_length")
    @classmethod
    def _valid_length(cls, v: str | None) -> str | None:
        if v is not None and v not in _VALID_LENGTH:
            raise ValueError(f"style_length must be one of {_VALID_LENGTH}")
        return v
