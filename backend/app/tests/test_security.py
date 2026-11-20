"""Unit tests for core/security.py (P1-7)."""

import datetime
import uuid

import jwt
import pytest

from app.core import security


def test_password_hash_and_verify() -> None:
    pw = "sup3r-secret"
    h = security.hash_password(pw)
    assert h != pw
    assert h.startswith("$2")  # bcrypt
    assert security.verify_password(pw, h) is True
    assert security.verify_password("wrong", h) is False


def test_password_hash_uses_random_salt() -> None:
    pw = "same-password-123"
    assert security.hash_password(pw) != security.hash_password(pw)


def test_access_token_roundtrip() -> None:
    uid = uuid.uuid4()
    token = security.create_access_token(uid)
    claims = security.decode_access_token(token)
    assert claims["sub"] == str(uid)
    assert claims["type"] == "access"
    assert claims["exp"] > claims["iat"]


def test_access_token_expired() -> None:
    token = security.create_access_token(uuid.uuid4(), expires_delta=datetime.timedelta(seconds=-1))
    with pytest.raises(jwt.ExpiredSignatureError):
        security.decode_access_token(token)


def test_access_token_bad_signature() -> None:
    token = security.create_access_token(uuid.uuid4())
    tampered = token[:-2] + ("aa" if not token.endswith("aa") else "bb")
    with pytest.raises(jwt.PyJWTError):
        security.decode_access_token(tampered)


def test_refresh_token_opaque_and_hash() -> None:
    t1 = security.generate_refresh_token()
    t2 = security.generate_refresh_token()
    assert t1 != t2
    assert len(t1) >= 40

    h = security.hash_refresh_token(t1)
    assert len(h) == 64  # sha256 hex
    assert all(c in "0123456789abcdef" for c in h)
    assert security.hash_refresh_token(t1) == h  # deterministic
    assert security.hash_refresh_token(t2) != h
