#!/usr/bin/env python3
"""P5-1 acceptance check: verify backend can reach Supabase Postgres + Upstash Redis.

Usage (from the backend/ directory, with DATABASE_URL / REDIS_URL in env or .env):
    python scripts/verify_connections.py

Exits 0 on success, 1 on any failure.
"""

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))


async def check_db() -> None:
    print("Checking PostgreSQL (Supabase)…")
    from app.db.session import engine
    from sqlalchemy import text

    async with engine.connect() as conn:
        row = (await conn.execute(text("SELECT version()"))).fetchone()
        print(f"  version : {row[0][:60]}")

        db_name = (await conn.execute(text("SELECT current_database()"))).scalar()
        print(f"  database: {db_name}")

        vec = (
            await conn.execute(
                text("SELECT extversion FROM pg_extension WHERE extname = 'vector'")
            )
        ).fetchone()
        if vec:
            print(f"  pgvector: {vec[0]} ✓")
        else:
            print("  pgvector: NOT INSTALLED — run: CREATE EXTENSION vector;")
            sys.exit(1)

        # Check Alembic has been run
        try:
            head = (
                await conn.execute(
                    text("SELECT version_num FROM alembic_version LIMIT 1")
                )
            ).fetchone()
            print(f"  alembic : head={head[0] if head else 'none'}")
        except Exception:
            print("  alembic : table not found — run: alembic upgrade head")
            sys.exit(1)

    print("  PostgreSQL: OK\n")
    await engine.dispose()


async def check_redis() -> None:
    print("Checking Redis (Upstash)…")
    from app.config import settings
    import redis.asyncio as aioredis

    r = aioredis.from_url(settings.redis_url, decode_responses=True, socket_timeout=5)
    try:
        pong = await r.ping()
        if not pong:
            raise RuntimeError("PING returned False")
        info = await r.info("server")
        print(f"  redis version: {info.get('redis_version', 'unknown')}")
        print(f"  mode         : {info.get('redis_mode', 'standalone')}")
        print(f"  url prefix   : {settings.redis_url[:20]}…")
    finally:
        await r.aclose()

    print("  Redis: OK\n")


async def main() -> None:
    errors: list[str] = []

    try:
        await check_db()
    except SystemExit:
        raise
    except Exception as exc:
        print(f"  PostgreSQL FAILED: {exc}\n")
        errors.append(f"postgres: {exc}")

    try:
        await check_redis()
    except Exception as exc:
        print(f"  Redis FAILED: {exc}\n")
        errors.append(f"redis: {exc}")

    if errors:
        print("❌ Connection verification FAILED:")
        for e in errors:
            print(f"   • {e}")
        sys.exit(1)

    print("✅ Both connections verified — P5-1 acceptance check PASSED")


if __name__ == "__main__":
    asyncio.run(main())
