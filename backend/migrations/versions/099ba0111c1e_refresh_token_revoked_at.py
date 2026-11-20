"""refresh token revoked_at

Revision ID: 099ba0111c1e
Revises: a59ea7d2435e
Create Date: 2026-11-20 18:33:00.000000

Adds refresh_tokens.revoked_at to support the refresh-reuse grace window in
05_Schema §6 (which §3.10's column list omitted). Nullable; set when a token is
revoked so a benign multi-tab race (revoked within ~10s) can be distinguished
from a genuine reuse attack.
"""

from collections.abc import Sequence

from alembic import op

revision: str = "099ba0111c1e"
down_revision: str | None = "a59ea7d2435e"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute("ALTER TABLE refresh_tokens ADD COLUMN revoked_at TIMESTAMPTZ")


def downgrade() -> None:
    op.execute("ALTER TABLE refresh_tokens DROP COLUMN IF EXISTS revoked_at")
