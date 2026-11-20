"""data tables and vector index

Revision ID: 95ab058184fe
Revises: 3d5c9c9161f9
Create Date: 2026-11-20 18:27:00.000000

Creates writing_samples, sample_chunks (vector(768) + HNSW cosine), jobs,
scores, proposals, ai_usage, source_health (05_Schema §3.3-3.7, §3.9, §3.11).
Embedding dim is LOCKED to 768 (Gemini gemini-embedding-001 via Matryoshka
truncation; 04_TRD §4.2 / 05_Schema §3.4).
"""

from collections.abc import Sequence

from alembic import op

revision: str = "95ab058184fe"
down_revision: str | None = "3d5c9c9161f9"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

EMBEDDING_DIM = 768


def upgrade() -> None:
    # writing_samples
    op.execute(
        """
        CREATE TABLE writing_samples (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            source_type sample_source NOT NULL,
            content TEXT NOT NULL,
            created_at TIMESTAMPTZ NOT NULL DEFAULT now()
        );
        """
    )
    op.execute("CREATE INDEX idx_writing_samples_user_id ON writing_samples(user_id)")

    # sample_chunks (voice RAG vectors); user_id denormalized for RLS + per-tenant ANN
    op.execute(
        f"""
        CREATE TABLE sample_chunks (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            sample_id UUID NOT NULL REFERENCES writing_samples(id) ON DELETE CASCADE,
            user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            chunk_index INTEGER NOT NULL,
            content TEXT NOT NULL,
            embedding vector({EMBEDDING_DIM}) NOT NULL,
            created_at TIMESTAMPTZ NOT NULL DEFAULT now()
        );
        """
    )
    op.execute("CREATE INDEX idx_sample_chunks_user_id ON sample_chunks(user_id)")
    op.execute(
        "CREATE INDEX idx_sample_chunks_embedding ON sample_chunks "
        "USING hnsw (embedding vector_cosine_ops)"
    )

    # jobs (GLOBAL, not user-owned)
    op.execute(
        """
        CREATE TABLE jobs (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            platform TEXT NOT NULL,
            external_id TEXT NOT NULL,
            title TEXT NOT NULL,
            description TEXT NOT NULL,
            company TEXT,
            category TEXT,
            skills TEXT[] NOT NULL DEFAULT '{}',
            budget_min NUMERIC(12,2),
            budget_max NUMERIC(12,2),
            currency TEXT NOT NULL DEFAULT 'USD',
            url TEXT NOT NULL,
            posted_at TIMESTAMPTZ,
            fetched_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            is_active BOOLEAN NOT NULL DEFAULT true,
            raw JSONB NOT NULL,
            CONSTRAINT uq_jobs_platform_external UNIQUE (platform, external_id)
        );
        """
    )
    op.execute("CREATE INDEX idx_jobs_posted_at ON jobs(posted_at DESC)")
    op.execute("CREATE INDEX idx_jobs_category ON jobs(category)")
    op.execute("CREATE INDEX idx_jobs_skills ON jobs USING gin (skills)")
    op.execute("CREATE INDEX idx_jobs_is_active ON jobs(is_active)")

    # scores (per-user job scores; cache key is the unique triple)
    op.execute(
        """
        CREATE TABLE scores (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            job_id UUID NOT NULL REFERENCES jobs(id) ON DELETE CASCADE,
            profile_version INTEGER NOT NULL,
            score SMALLINT NOT NULL CHECK (score BETWEEN 0 AND 100),
            confidence NUMERIC(3,2) NOT NULL CHECK (confidence BETWEEN 0 AND 1),
            dimensions JSONB NOT NULL,
            reasoning TEXT,
            created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            CONSTRAINT uq_scores_user_job_version UNIQUE (user_id, job_id, profile_version)
        );
        """
    )
    op.execute("CREATE INDEX idx_scores_user_score ON scores(user_id, score DESC)")

    # proposals (drafts + outcomes)
    op.execute(
        """
        CREATE TABLE proposals (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            job_id UUID NOT NULL REFERENCES jobs(id) ON DELETE CASCADE,
            content TEXT NOT NULL,
            status proposal_status NOT NULL DEFAULT 'draft',
            outcome proposal_outcome NOT NULL DEFAULT 'pending',
            voice_matched BOOLEAN NOT NULL DEFAULT false,
            created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
        );
        """
    )
    op.execute("CREATE INDEX idx_proposals_user_created ON proposals(user_id, created_at DESC)")
    op.execute("CREATE INDEX idx_proposals_user_outcome ON proposals(user_id, outcome)")
    op.execute(
        "CREATE TRIGGER trg_proposals_updated_at BEFORE UPDATE ON proposals "
        "FOR EACH ROW EXECUTE FUNCTION set_updated_at()"
    )

    # ai_usage (metering; user_id NULL for system ops)
    op.execute(
        """
        CREATE TABLE ai_usage (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            user_id UUID REFERENCES users(id) ON DELETE CASCADE,
            operation ai_operation NOT NULL,
            model TEXT NOT NULL,
            input_tokens INTEGER NOT NULL DEFAULT 0,
            output_tokens INTEGER NOT NULL DEFAULT 0,
            cost_usd NUMERIC(10,6) NOT NULL DEFAULT 0,
            created_at TIMESTAMPTZ NOT NULL DEFAULT now()
        );
        """
    )
    op.execute("CREATE INDEX idx_ai_usage_user_created ON ai_usage(user_id, created_at)")
    op.execute("CREATE INDEX idx_ai_usage_created ON ai_usage(created_at)")

    # source_health (GLOBAL adapter observability) + seed the 4 MVP platforms (05_Schema §7.7)
    op.execute(
        """
        CREATE TABLE source_health (
            platform TEXT PRIMARY KEY,
            status source_status NOT NULL DEFAULT 'healthy',
            last_success_at TIMESTAMPTZ,
            last_error_at TIMESTAMPTZ,
            consecutive_failures INTEGER NOT NULL DEFAULT 0
        );
        """
    )
    op.execute(
        """
        INSERT INTO source_health (platform) VALUES
            ('remoteok'), ('remotive'), ('himalayas'), ('weworkremotely')
        ON CONFLICT (platform) DO NOTHING;
        """
    )


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS source_health")
    op.execute("DROP TABLE IF EXISTS ai_usage")
    op.execute("DROP TABLE IF EXISTS proposals")
    op.execute("DROP TABLE IF EXISTS scores")
    op.execute("DROP TABLE IF EXISTS jobs")
    op.execute("DROP TABLE IF EXISTS sample_chunks")
    op.execute("DROP TABLE IF EXISTS writing_samples")
