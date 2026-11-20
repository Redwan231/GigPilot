"""Async engine + session factory, with the Row-Level Security GUC setter
(05_Schema §5.1).

Two session entry points:

* ``tenant_session(user_id)`` — used by every authenticated API request. Opens a
  single transaction and, as its first statements, (1) switches to the
  non-BYPASSRLS tenant role and (2) sets ``app.current_user_id`` for the
  transaction. RLS policies then restrict every user-owned table to that id.
  Fail-closed: if the GUC is unset the policies match no rows.

* ``system_session()`` — privileged session for system jobs (Celery writes to the
  global ``jobs``/``source_health`` tables, auth service touching
  ``refresh_tokens``). It does NOT switch to the tenant role and is never used to
  serve user-scoped queries.
"""

import ssl
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from sqlalchemy import text
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.config import settings

_engine_kwargs: dict = {"pool_pre_ping": True, "future": True}
if settings.database_ssl_require:
    _engine_kwargs["connect_args"] = {"ssl": ssl.create_default_context()}

engine = create_async_engine(settings.database_url, **_engine_kwargs)

SessionLocal = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


async def set_tenant_guc(session: AsyncSession, user_id: str) -> None:
    """Switch to the tenant role and set the per-transaction RLS GUC.

    Must run as the first statement(s) inside the request transaction. The role
    name comes from trusted config (never user input); the user id is bound.
    ``set_config(..., true)`` makes the GUC transaction-local (safe under a
    transaction-mode connection pooler; never a session-level SET).
    """
    if settings.db_tenant_role:
        await session.execute(text(f'SET LOCAL ROLE "{settings.db_tenant_role}"'))
    await session.execute(
        text("SELECT set_config('app.current_user_id', :uid, true)"),
        {"uid": str(user_id)},
    )


@asynccontextmanager
async def tenant_session(user_id: str) -> AsyncGenerator[AsyncSession, None]:
    """Session scoped to one authenticated user, inside one RLS-guarded transaction."""
    async with SessionLocal() as session:
        async with session.begin():
            await set_tenant_guc(session, user_id)
            yield session


@asynccontextmanager
async def system_session() -> AsyncGenerator[AsyncSession, None]:
    """Privileged (non-tenant) session for system jobs; never serves user requests."""
    async with SessionLocal() as session:
        async with session.begin():
            yield session
