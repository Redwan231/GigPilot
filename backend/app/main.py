"""FastAPI application factory."""

from fastapi import FastAPI

from app.api.routes import auth


def create_app() -> FastAPI:
    app = FastAPI(title="GigPilot API", version="0.1.0")
    app.include_router(auth.router)
    return app


app = create_app()
