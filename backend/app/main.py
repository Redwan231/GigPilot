"""FastAPI application factory."""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware

from app.api.routes import auth, health, jobs, me, proposals, samples
from app.config import settings
from app.core.rate_limit import limiter


def _rate_limit_handler(request, exc):  # type: ignore[no-untyped-def]
    from slowapi import _rate_limit_exceeded_handler

    return _rate_limit_exceeded_handler(request, exc)


def create_app() -> FastAPI:
    app = FastAPI(title="GigPilot API", version="0.1.0")

    # CORS — credentials=True required for cross-domain refresh cookie (04_TRD §7.6).
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Rate-limit infrastructure (specific limits are applied per-route later).
    app.state.limiter = limiter
    app.add_exception_handler(RateLimitExceeded, _rate_limit_handler)
    app.add_middleware(SlowAPIMiddleware)

    app.include_router(auth.router)
    app.include_router(me.router)
    app.include_router(samples.router)
    app.include_router(jobs.router)
    app.include_router(proposals.router)
    app.include_router(health.router)
    return app


app = create_app()
