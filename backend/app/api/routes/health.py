"""Health check endpoints (P2-16). GET /health (liveness), GET /health/ready (readiness)."""

from fastapi import APIRouter, status
from fastapi.responses import JSONResponse

router = APIRouter(tags=["health"])


@router.get("/health")
async def health() -> dict:
    return {"status": "ok"}


@router.get("/health/ready")
async def ready() -> JSONResponse:
    errors: list[str] = []

    # Check DB
    try:
        from app.db.session import system_session
        from sqlalchemy import text
        async with system_session() as session:
            await session.execute(text("SELECT 1"))
    except Exception as exc:
        errors.append(f"db: {exc}")

    # Check Redis
    try:
        from app.config import settings
        import redis.asyncio as aioredis
        r = aioredis.from_url(settings.redis_url, decode_responses=True)
        await r.ping()
        await r.aclose()
    except Exception as exc:
        errors.append(f"redis: {exc}")

    if errors:
        return JSONResponse(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            content={"status": "not ready", "errors": errors},
        )

    return JSONResponse(content={"status": "ready"})
