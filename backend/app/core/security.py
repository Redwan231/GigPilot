"""Crypto primitives: password hashing (bcrypt, cost >= 12), access JWTs
(HS256), and opaque refresh tokens hashed-at-rest with SHA-256 (04_TRD §7.2,
05_Schema §6)."""

import datetime
import hashlib
import secrets
import uuid
from typing import Any

import jwt
from passlib.context import CryptContext

from app.config import settings

ALGORITHM = "HS256"
ACCESS_TOKEN_TYPE = "access"

# bcrypt cost >= 12 (04_TRD §7.2).
_pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto", bcrypt__rounds=12)


# --- Passwords ---
def hash_password(password: str) -> str:
    return _pwd_context.hash(password)


def verify_password(password: str, password_hash: str) -> bool:
    return _pwd_context.verify(password, password_hash)


# --- Access JWTs (HS256, short-lived, held in memory on the client) ---
def create_access_token(
    user_id: uuid.UUID | str,
    expires_delta: datetime.timedelta | None = None,
) -> str:
    now = datetime.datetime.now(datetime.UTC)
    expire = now + (
        expires_delta
        if expires_delta is not None
        else datetime.timedelta(minutes=settings.access_token_ttl_min)
    )
    payload: dict[str, Any] = {
        "sub": str(user_id),
        "type": ACCESS_TOKEN_TYPE,
        "iat": int(now.timestamp()),
        "exp": int(expire.timestamp()),
    }
    return jwt.encode(payload, settings.secret_key, algorithm=ALGORITHM)


def decode_access_token(token: str) -> dict[str, Any]:
    """Verify signature + expiry and return the claims. Raises jwt.PyJWTError
    (ExpiredSignatureError / InvalidTokenError) on failure."""
    claims: dict[str, Any] = jwt.decode(
        token, settings.secret_key, algorithms=[ALGORITHM]
    )
    if claims.get("type") != ACCESS_TOKEN_TYPE:
        raise jwt.InvalidTokenError("wrong token type")
    return claims


# --- Opaque refresh tokens (random; only the SHA-256 is stored) ---
def generate_refresh_token() -> str:
    """A high-entropy opaque token. The raw value is sent to the client cookie
    and never stored; the DB keeps only its SHA-256 (05_Schema §3.10)."""
    return secrets.token_urlsafe(48)


def hash_refresh_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()
