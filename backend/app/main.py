"""FastAPI application factory."""

from fastapi import FastAPI
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware

from app.api.routes import auth, jobs, me, samples
from app.core.rate_limit import limiter


def _rate_limit_handler(request, exc):  # type: ignore[no-untyped-def]
    from slowapi import _rate_limit_exceeded_handler

    return _rate_limit_exceeded_handler(request, exc)


def create_app() -> FastAPI:
    app = FastAPI(title="GigPilot API", version="0.1.0")

    # Rate-limit infrastructure (specific limits are applied per-route later).
    app.state.limiter = limiter
    app.add_exception_handler(RateLimitExceeded, _rate_limit_handler)
    app.add_middleware(SlowAPIMiddleware)

    app.include_router(auth.router)
    app.include_router(me.router)
    app.include_router(samples.router)
    app.include_router(jobs.router)
    return app


app = create_app()
