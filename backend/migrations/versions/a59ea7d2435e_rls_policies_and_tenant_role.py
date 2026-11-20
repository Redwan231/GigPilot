"""rls policies and tenant role

Revision ID: a59ea7d2435e
Revises: 95ab058184fe
Create Date: 2026-11-20 18:29:00.000000

Enables Row-Level Security (ENABLE + FORCE) and the tenant_isolation policy on
every user-owned table (05_Schema §5.2), and creates the non-BYPASSRLS
application role `gigpilot_app`. The session layer runs `SET LOCAL ROLE
gigpilot_app` + sets `app.current_user_id`, so policies fail closed (zero rows)
when the GUC is unset — defense-in-depth behind app-layer user_id filtering.

Global tables (jobs, source_health, users, refresh_tokens) get NO RLS; they are
served/written only via the privileged (system) path, never the tenant role.
"""

from collections.abc import Sequence

from alembic import op

revision: str = "a59ea7d2435e"
down_revision: str | None = "95ab058184fe"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# Tables that carry a user_id and are restricted to the authenticated user.
USER_OWNED_TABLES = (
    "profiles",
    "writing_samples",
    "sample_chunks",
    "scores",
    "proposals",
    "subscriptions",
    "ai_usage",
)

# The app reads global job data under the tenant role, but never writes it.
TENANT_READONLY_TABLES = ("jobs", "source_health")

APP_ROLE = "gigpilot_app"


def upgrade() -> None:
    # 1) Dedicated non-BYPASSRLS application role (idempotent).
    op.execute(
        f"""
        DO $$
        BEGIN
            IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = '{APP_ROLE}') THEN
                CREATE ROLE {APP_ROLE} NOLOGIN NOSUPERUSER NOBYPASSRLS
                    NOCREATEDB NOCREATEROLE;
            END IF;
        END
        $$;
        """
    )

    # 2) Enable + FORCE RLS and install the tenant_isolation policy per table.
    for table in USER_OWNED_TABLES:
        op.execute(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY")
        op.execute(f"ALTER TABLE {table} FORCE ROW LEVEL SECURITY")
        op.execute(
            f"""
            CREATE POLICY tenant_isolation ON {table}
                USING (user_id = current_setting('app.current_user_id', true)::uuid)
                WITH CHECK (user_id = current_setting('app.current_user_id', true)::uuid);
            """
        )

    # 3) Privileges for the tenant role: DML on user-owned tables, read-only on globals.
    op.execute(f"GRANT USAGE ON SCHEMA public TO {APP_ROLE}")
    op.execute(
        f"GRANT SELECT, INSERT, UPDATE, DELETE ON "
        f"{', '.join(USER_OWNED_TABLES)} TO {APP_ROLE}"
    )
    op.execute(f"GRANT SELECT ON {', '.join(TENANT_READONLY_TABLES)} TO {APP_ROLE}")

    # 4) Allow the connecting (login) role to `SET ROLE gigpilot_app`. On a superuser
    #    login this is a no-op; on managed hosts (e.g. Supabase) it grants membership.
    op.execute(
        f"""
        DO $$
        BEGIN
            EXECUTE format('GRANT {APP_ROLE} TO %I', current_user);
        EXCEPTION WHEN OTHERS THEN
            NULL;  -- already a member, or host restricts self-grant; SET ROLE still ok
        END
        $$;
        """
    )


def downgrade() -> None:
    for table in USER_OWNED_TABLES:
        op.execute(f"DROP POLICY IF EXISTS tenant_isolation ON {table}")
        op.execute(f"ALTER TABLE {table} NO FORCE ROW LEVEL SECURITY")
        op.execute(f"ALTER TABLE {table} DISABLE ROW LEVEL SECURITY")

    # Remove all privileges granted to the role, then drop it (guarded).
    op.execute(
        f"""
        DO $$
        BEGIN
            IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = '{APP_ROLE}') THEN
                DROP OWNED BY {APP_ROLE};
                DROP ROLE {APP_ROLE};
            END IF;
        END
        $$;
        """
    )
