"""extensions and enum types

Revision ID: 85563be81646
Revises: 
Create Date: 2026-11-20 18:24:23.937455

"""
from collections.abc import Sequence

from alembic import op

# revision identifiers, used by Alembic.
revision: str = '85563be81646'
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


# Extensions (05_Schema §1) and native ENUM types (05_Schema §2).
_ENUMS: dict[str, tuple[str, ...]] = {
    "plan_tier": ("free", "pro"),
    "experience_level": ("junior", "mid", "senior"),
    "sample_source": ("paste", "upload"),
    "proposal_status": ("draft", "used"),
    "proposal_outcome": ("pending", "won", "lost", "no_response"),
    "source_status": ("healthy", "degraded", "down"),
    "ai_operation": ("score", "score_reasoning", "draft", "embed"),
}


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS pgcrypto")
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")
    op.execute("CREATE EXTENSION IF NOT EXISTS citext")
    for name, labels in _ENUMS.items():
        values = ", ".join(f"'{label}'" for label in labels)
        op.execute(f"CREATE TYPE {name} AS ENUM ({values})")


def downgrade() -> None:
    for name in reversed(list(_ENUMS)):
        op.execute(f"DROP TYPE IF EXISTS {name}")
    # Extensions are left in place (harmless, often shared); re-upgrade is idempotent.
