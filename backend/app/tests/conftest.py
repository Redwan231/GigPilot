"""Test harness: point the app at the local Docker Postgres (never Supabase),
truncate between tests, and provide an ASGI httpx client.

The DATABASE_URL override is set before any app module is imported so the engine
and settings build against the test DB. The schema is assumed migrated
(`alembic upgrade head` against the local DB); see the repo README/Progress Log.
"""

import os

os.environ["DATABASE_URL"] = "postgresql+asyncpg://gigpilot:password@localhost:5432/gigpilot"
os.environ["SECRET_KEY"] = "test-secret-key-not-for-prod"
os.environ["ENVIRONMENT"] = "test"
os.environ["AUTH_AUTO_VERIFY_EMAIL"] = "true"

import pytest_asyncio  # noqa: E402
from httpx import ASGITransport, AsyncClient  # noqa: E402
from sqlalchemy import text  # noqa: E402
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine  # noqa: E402
from sqlalchemy.pool import NullPool  # noqa: E402

import app.db.session as dbsession  # noqa: E402

# pytest-asyncio runs each test on its own event loop; a pooled asyncpg connection
# created on one loop can't be reused on another. NullPool opens/closes a fresh
# connection per checkout, avoiding cross-loop reuse. Rebind the app's engine +
# sessionmaker (the session helpers read these module globals at call time).
_test_engine = create_async_engine(os.environ["DATABASE_URL"], poolclass=NullPool)
dbsession.engine = _test_engine
dbsession.SessionLocal = async_sessionmaker(_test_engine, expire_on_commit=False)

from app.main import app  # noqa: E402

engine = _test_engine


async def _truncate() -> None:
    async with engine.begin() as conn:
        # users/jobs cascade to all user-owned + dependent rows.
        await conn.execute(text("TRUNCATE users, jobs RESTART IDENTITY CASCADE"))


@pytest_asyncio.fixture
async def client() -> AsyncClient:
    await _truncate()
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as c:
        yield c
