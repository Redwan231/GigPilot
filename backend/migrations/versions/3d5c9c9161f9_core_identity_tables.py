"""core identity tables

Revision ID: 3d5c9c9161f9
Revises: 85563be81646
Create Date: 2026-11-20 18:25:36.738572

Creates users, profiles, subscriptions, refresh_tokens with indexes and the
shared updated_at trigger (05_Schema §3.1-3.2, §3.8, §3.10, §7).
"""

from collections.abc import Sequence

from alembic import op

revision: str = "3d5c9c9161f9"
down_revision: str | None = "85563be81646"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Shared trigger function to maintain updated_at on row changes.
    op.execute(
        """
        CREATE OR REPLACE FUNCTION set_updated_at() RETURNS trigger AS $$
        BEGIN
            NEW.updated_at = now();
            RETURN NEW;
        END;
        $$ LANGUAGE plpgsql;
        """
    )

    # users
    op.execute(
        """
        CREATE TABLE users (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            email CITEXT NOT NULL UNIQUE,
            password_hash TEXT NOT NULL,
            email_verified BOOLEAN NOT NULL DEFAULT false,
            profile_complete BOOLEAN NOT NULL DEFAULT false,
            created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
        );
        """
    )

    # profiles (1:1 users; user_id is PK)
    op.execute(
        """
        CREATE TABLE profiles (
            user_id UUID PRIMARY KEY REFERENCES users(id) ON DELETE CASCADE,
            display_name TEXT NOT NULL,
            primary_category TEXT NOT NULL,
            skills TEXT[] NOT NULL DEFAULT '{}',
            experience_level experience_level NOT NULL,
            hourly_rate NUMERIC(12,2),
            bio TEXT,
            style_tone TEXT,
            style_length TEXT,
            style_greeting TEXT,
            profile_version INTEGER NOT NULL DEFAULT 1,
            updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
        );
        """
    )
    op.execute("CREATE INDEX idx_profiles_skills ON profiles USING gin (skills)")

    # subscriptions (1:1 users)
    op.execute(
        """
        CREATE TABLE subscriptions (
            user_id UUID PRIMARY KEY REFERENCES users(id) ON DELETE CASCADE,
            tier plan_tier NOT NULL DEFAULT 'free',
            period_start DATE NOT NULL DEFAULT current_date,
            period_end DATE NOT NULL,
            drafts_quota INTEGER NOT NULL,
            drafts_used INTEGER NOT NULL DEFAULT 0,
            updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
        );
        """
    )

    # refresh_tokens (backend-only session mgmt; no updated_at)
    op.execute(
        """
        CREATE TABLE refresh_tokens (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            token_hash TEXT NOT NULL UNIQUE,
            expires_at TIMESTAMPTZ NOT NULL,
            revoked BOOLEAN NOT NULL DEFAULT false,
            created_at TIMESTAMPTZ NOT NULL DEFAULT now()
        );
        """
    )
    op.execute("CREATE INDEX idx_refresh_tokens_user_id ON refresh_tokens(user_id)")

    # updated_at triggers (tables that carry updated_at)
    for table in ("users", "profiles", "subscriptions"):
        op.execute(
            f"CREATE TRIGGER trg_{table}_updated_at BEFORE UPDATE ON {table} "
            f"FOR EACH ROW EXECUTE FUNCTION set_updated_at()"
        )


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS refresh_tokens")
    op.execute("DROP TABLE IF EXISTS subscriptions")
    op.execute("DROP TABLE IF EXISTS profiles")
    op.execute("DROP TABLE IF EXISTS users")
    op.execute("DROP FUNCTION IF EXISTS set_updated_at()")
