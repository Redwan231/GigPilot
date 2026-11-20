"""Shared API dependencies: authentication (verify access JWT) and the two DB
session dependencies — a tenant-scoped session that sets the RLS GUC, and the
current-user loader (privileged read of the user's own row)."""

import uuid
from collections.abc import AsyncGenerator

import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession

from app.core import security
from app.db.models.user import User
from app.db.session import system_session, tenant_session

_bearer = HTTPBearer(auto_error=False)


def _unauthenticated() -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Not authenticated",
        headers={"WWW-Authenticate": "Bearer"},
    )


async def get_current_user_id(
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer),
) -> uuid.UUID:
    """Validate the Bearer access token and return the user id (claim `sub`)."""
    if credentials is None or not credentials.credentials:
        raise _unauthenticated()
    try:
        claims = security.decode_access_token(credentials.credentials)
        return uuid.UUID(claims["sub"])
    except (jwt.PyJWTError, KeyError, ValueError) as exc:
        raise _unauthenticated() from exc


async def get_tenant_db(
    user_id: uuid.UUID = Depends(get_current_user_id),
) -> AsyncGenerator[AsyncSession, None]:
    """A DB session for the authenticated request, with the RLS GUC set to this
    user (SET LOCAL ROLE gigpilot_app + app.current_user_id). All user-owned
    queries go through this."""
    async with tenant_session(user_id) as session:
        yield session


async def get_current_user(
    user_id: uuid.UUID = Depends(get_current_user_id),
) -> User:
    """Load the authenticated user's own row (privileged read by exact id; the
    tenant role has no SELECT on `users`)."""
    async with system_session() as session:
        user = await session.get(User, user_id)
    if user is None:
        raise _unauthenticated()
    return user
