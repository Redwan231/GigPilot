"""Auth request/response schemas (Pydantic v2). Unknown fields rejected."""

import re
import uuid

from pydantic import BaseModel, ConfigDict, field_validator

# Simple email check — avoids adding the email-validator dependency (not in 04_TRD §1).
_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


class SignupRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    email: str
    password: str

    @field_validator("email")
    @classmethod
    def _valid_email(cls, v: str) -> str:
        v = v.strip()
        if not _EMAIL_RE.match(v):
            raise ValueError("invalid email address")
        return v

    @field_validator("password")
    @classmethod
    def _strong_password(cls, v: str) -> str:
        # 02_AppFlow §4.2: min 8, at least one number.
        if len(v) < 8 or not any(c.isdigit() for c in v):
            raise ValueError("password must be at least 8 characters and contain a number")
        return v


class LoginRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    email: str
    password: str


class UserPublic(BaseModel):
    id: uuid.UUID
    email: str
    profile_complete: bool


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserPublic
