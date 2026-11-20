"""Application settings (pydantic-settings). Values come from environment
variables (injected by Docker/host) or a local .env file; see 04_TRD §8.
Unknown env keys are ignored so the full .env can carry keys other modules read.
"""

from functools import lru_cache

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        # look in backend/.env then repo-root .env; env vars still win over both
        env_file=(".env", "../.env"),
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    environment: str = "development"

    # --- Database / Redis ---
    database_url: str = "postgresql+asyncpg://gigpilot:password@localhost:5432/gigpilot"
    # Set true for managed hosts that enforce SSL (e.g. Supabase). Causes the
    # engine to use ssl.create_default_context() on every connection.
    database_ssl_require: bool = False
    redis_url: str = "redis://localhost:6379/0"

    # Per-request RLS tenant role. The session layer runs `SET LOCAL ROLE <this>`
    # so Row-Level Security is enforced even when the connection's login role is
    # privileged (e.g. Supabase's). Must be NOSUPERUSER + NOBYPASSRLS. Empty string
    # disables the role switch (only safe when the login role is itself non-BYPASSRLS).
    db_tenant_role: str = "gigpilot_app"

    # --- Auth ---
    secret_key: str = "change-me"
    access_token_ttl_min: int = 15
    refresh_token_ttl_days: int = 7
    auth_auto_verify_email: bool = True

    # --- AI ---
    gemini_api_key: str = ""
    embedding_model: str = "gemini-embedding-001"
    embedding_dim: int = 768
    llm_base_url: str = ""
    llm_api_key: str = ""
    llm_model: str = "glm-5.3-flash"

    # --- Limits (04_TRD §8) ---
    free_drafts_per_month: int = 30
    pro_drafts_per_month: int = 500
    free_scores_per_day: int = 100
    pro_scores_per_day: int = 1000

    @field_validator("database_url")
    @classmethod
    def _force_asyncpg_driver(cls, v: str) -> str:
        """Normalize any libpq-style URL (e.g. Supabase's `postgresql://…`) to the
        async `postgresql+asyncpg://` driver this app uses everywhere."""
        if v.startswith("postgres://"):
            v = "postgresql://" + v[len("postgres://") :]
        if v.startswith("postgresql://"):
            v = "postgresql+asyncpg://" + v[len("postgresql://") :]
        return v


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
