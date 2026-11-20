# 05 — Database Schema & Auth/RLS

**Product:** GigPilot
**Version:** 1.0 (MVP)
**Engine:** PostgreSQL 16 + pgvector
**Last updated:** 2026-11-20

> Complete relational schema: tables, columns, types, keys, indexes, enums, pgvector, and Row-Level Security.
> This is the contract for Alembic migrations. Column names here == model field names.

---

## 1. Conventions

- All PKs: `id UUID PRIMARY KEY DEFAULT gen_random_uuid()` (pgcrypto / `gen_random_uuid`).
- Timestamps: `created_at TIMESTAMPTZ NOT NULL DEFAULT now()`, `updated_at TIMESTAMPTZ NOT NULL DEFAULT now()` (trigger-updated).
- All FKs: `ON DELETE CASCADE` for user-owned data unless noted.
- Money: store as `NUMERIC(12,2)` (USD); never floats for currency.
- Enums: Postgres native `ENUM` types.
- Extensions required: `pgcrypto`, `vector`, `citext`.

```sql
CREATE EXTENSION IF NOT EXISTS pgcrypto;
CREATE EXTENSION IF NOT EXISTS vector;
CREATE EXTENSION IF NOT EXISTS citext;
```

---

## 2. Enum Types

```sql
CREATE TYPE plan_tier       AS ENUM ('free', 'pro');
CREATE TYPE experience_level AS ENUM ('junior', 'mid', 'senior');
CREATE TYPE sample_source   AS ENUM ('paste', 'upload');
CREATE TYPE proposal_status AS ENUM ('draft', 'used');
CREATE TYPE proposal_outcome AS ENUM ('pending', 'won', 'lost', 'no_response');
CREATE TYPE source_status   AS ENUM ('healthy', 'degraded', 'down');
CREATE TYPE ai_operation    AS ENUM ('score', 'score_reasoning', 'draft', 'embed');
```

---

## 3. Tables

### 3.1 `users` — identity
| Column | Type | Constraints |
|---|---|---|
| id | UUID | PK |
| email | CITEXT | UNIQUE NOT NULL |
| password_hash | TEXT | NOT NULL |
| email_verified | BOOLEAN | NOT NULL DEFAULT false |
| profile_complete | BOOLEAN | NOT NULL DEFAULT false |
| created_at | TIMESTAMPTZ | NOT NULL DEFAULT now() |
| updated_at | TIMESTAMPTZ | NOT NULL DEFAULT now() |

Indexes: UNIQUE(email). (CITEXT for case-insensitive email; enable `citext` extension or use `LOWER(email)` unique index.)

### 3.2 `profiles` — 1:1 with users
| Column | Type | Constraints |
|---|---|---|
| user_id | UUID | PK, FK→users.id ON DELETE CASCADE |
| display_name | TEXT | NOT NULL |
| primary_category | TEXT | NOT NULL |
| skills | TEXT[] | NOT NULL DEFAULT '{}' |
| experience_level | experience_level | NOT NULL |
| hourly_rate | NUMERIC(12,2) | NULL |
| bio | TEXT | NULL |
| style_tone | TEXT | NULL  (cold-start: formal/friendly/direct) |
| style_length | TEXT | NULL  (short/medium/long) |
| style_greeting | TEXT | NULL |
| profile_version | INTEGER | NOT NULL DEFAULT 1 (bumped on any change; invalidates cached scores) |
| updated_at | TIMESTAMPTZ | NOT NULL DEFAULT now() |

Indexes: GIN(skills) for overlap pre-filter.

### 3.3 `writing_samples` — raw voice sources
| Column | Type | Constraints |
|---|---|---|
| id | UUID | PK |
| user_id | UUID | FK→users.id ON DELETE CASCADE, NOT NULL |
| source_type | sample_source | NOT NULL |
| content | TEXT | NOT NULL (≤ ~20k chars enforced in app) |
| created_at | TIMESTAMPTZ | NOT NULL DEFAULT now() |

Indexes: INDEX(user_id).

### 3.4 `sample_chunks` — Voice RAG vectors
| Column | Type | Constraints |
|---|---|---|
| id | UUID | PK |
| sample_id | UUID | FK→writing_samples.id ON DELETE CASCADE, NOT NULL |
| user_id | UUID | FK→users.id ON DELETE CASCADE, NOT NULL (denormalized for RLS + filter) |
| chunk_index | INTEGER | NOT NULL |
| content | TEXT | NOT NULL |
| embedding | vector(768) | NOT NULL  (Gemini gemini-embedding-001 dim = 768) |
| created_at | TIMESTAMPTZ | NOT NULL DEFAULT now() |

Indexes:
- `INDEX(user_id)`
- HNSW vector index, cosine:
```sql
CREATE INDEX idx_sample_chunks_embedding
  ON sample_chunks USING hnsw (embedding vector_cosine_ops);
```
Retrieval always filters `WHERE user_id = :uid` first (per-tenant ANN).

> **Embedding dimension is LOCKED to Gemini `gemini-embedding-001` output (768).** Verify the current default dimension in Google AI Studio docs before migration P1-4. If the embedding model changes, dimension and index must change via migration — never mix dimensions in one column.

### 3.5 `jobs` — aggregated listings (GLOBAL, not user-owned)
| Column | Type | Constraints |
|---|---|---|
| id | UUID | PK |
| platform | TEXT | NOT NULL (remoteok/remotive/himalayas/wwr) |
| external_id | TEXT | NOT NULL (id on source) |
| title | TEXT | NOT NULL |
| description | TEXT | NOT NULL |
| company | TEXT | NULL |
| category | TEXT | NULL |
| skills | TEXT[] | NOT NULL DEFAULT '{}' |
| budget_min | NUMERIC(12,2) | NULL |
| budget_max | NUMERIC(12,2) | NULL |
| currency | TEXT | NOT NULL DEFAULT 'USD' |
| url | TEXT | NOT NULL |
| posted_at | TIMESTAMPTZ | NULL |
| fetched_at | TIMESTAMPTZ | NOT NULL DEFAULT now() |
| is_active | BOOLEAN | NOT NULL DEFAULT true (set false when expired/stale) |
| raw | JSONB | NOT NULL (original payload) |

Indexes:
- `UNIQUE(platform, external_id)` ← idempotent upsert key
- `INDEX(posted_at DESC)`, `INDEX(category)`, `GIN(skills)`, `INDEX(is_active)`

### 3.6 `scores` — per-user job scores
| Column | Type | Constraints |
|---|---|---|
| id | UUID | PK |
| user_id | UUID | FK→users.id ON DELETE CASCADE, NOT NULL |
| job_id | UUID | FK→jobs.id ON DELETE CASCADE, NOT NULL |
| profile_version | INTEGER | NOT NULL (profile version at scoring time) |
| score | SMALLINT | NOT NULL CHECK (score BETWEEN 0 AND 100) |
| confidence | NUMERIC(3,2) | NOT NULL CHECK (confidence BETWEEN 0 AND 1) |
| dimensions | JSONB | NOT NULL — MVP keys: `{skills, seniority, rate, freshness}` ints (see `04_TRD §5b`; NO client/competition keys, that data doesn't exist for job boards) |
| reasoning | TEXT | NULL (lazily filled on "Why?") |
| created_at | TIMESTAMPTZ | NOT NULL DEFAULT now() |

Indexes: `UNIQUE(user_id, job_id, profile_version)` (cache key), `INDEX(user_id, score DESC)`.

### 3.7 `proposals` — drafts + outcomes
| Column | Type | Constraints |
|---|---|---|
| id | UUID | PK |
| user_id | UUID | FK→users.id ON DELETE CASCADE, NOT NULL |
| job_id | UUID | FK→jobs.id ON DELETE CASCADE, NOT NULL |
| content | TEXT | NOT NULL |
| status | proposal_status | NOT NULL DEFAULT 'draft' |
| outcome | proposal_outcome | NOT NULL DEFAULT 'pending' |
| voice_matched | BOOLEAN | NOT NULL DEFAULT false (false = cold-start template) |
| created_at | TIMESTAMPTZ | NOT NULL DEFAULT now() |
| updated_at | TIMESTAMPTZ | NOT NULL DEFAULT now() |

Indexes: `INDEX(user_id, created_at DESC)`, `INDEX(user_id, outcome)`.

### 3.8 `subscriptions` — plan + credit quota state (1:1 user)
| Column | Type | Constraints |
|---|---|---|
| user_id | UUID | PK, FK→users.id ON DELETE CASCADE |
| tier | plan_tier | NOT NULL DEFAULT 'free' |
| period_start | DATE | NOT NULL DEFAULT current_date |
| period_end | DATE | NOT NULL (period_start + 1 month) |
| drafts_quota | INTEGER | NOT NULL (30 free / 500 pro) |
| drafts_used | INTEGER | NOT NULL DEFAULT 0 |
| updated_at | TIMESTAMPTZ | NOT NULL DEFAULT now() |

> Draft enforcement: DB is source of truth (`drafts_used < drafts_quota`), checked+incremented in the same transaction as proposal creation (atomic, `SELECT ... FOR UPDATE`). Redis holds a fast mirror for pre-checks only. Daily scoring cap lives in Redis (ephemeral), keyed `score:{user_id}:{yyyymmdd}`.

### 3.9 `ai_usage` — metering (cost observability)
| Column | Type | Constraints |
|---|---|---|
| id | UUID | PK |
| user_id | UUID | FK→users.id ON DELETE CASCADE, NULL (null for system ops) |
| operation | ai_operation | NOT NULL |
| model | TEXT | NOT NULL |
| input_tokens | INTEGER | NOT NULL DEFAULT 0 |
| output_tokens | INTEGER | NOT NULL DEFAULT 0 |
| cost_usd | NUMERIC(10,6) | NOT NULL DEFAULT 0 |
| created_at | TIMESTAMPTZ | NOT NULL DEFAULT now() |

Indexes: `INDEX(user_id, created_at)`, `INDEX(created_at)`.

### 3.10 `refresh_tokens` — session management (backend-only)
| Column | Type | Constraints |
|---|---|---|
| id | UUID | PK |
| user_id | UUID | FK→users.id ON DELETE CASCADE, NOT NULL |
| token_hash | TEXT | NOT NULL (SHA-256 of opaque token; raw never stored) |
| expires_at | TIMESTAMPTZ | NOT NULL |
| revoked | BOOLEAN | NOT NULL DEFAULT false |
| created_at | TIMESTAMPTZ | NOT NULL DEFAULT now() |

Indexes: `UNIQUE(token_hash)`, `INDEX(user_id)`. Rotation: on use, mark old revoked, insert new.

### 3.11 `source_health` — adapter observability (GLOBAL)
| Column | Type | Constraints |
|---|---|---|
| platform | TEXT | PK |
| status | source_status | NOT NULL DEFAULT 'healthy' |
| last_success_at | TIMESTAMPTZ | NULL |
| last_error_at | TIMESTAMPTZ | NULL |
| consecutive_failures | INTEGER | NOT NULL DEFAULT 0 |

---

## 4. Entity Relationships

```
users 1───1 profiles
users 1───1 subscriptions
users 1───* writing_samples 1───* sample_chunks
users 1───* scores *───1 jobs
users 1───* proposals *───1 jobs
users 1───* ai_usage
users 1───* refresh_tokens
jobs  (global)       source_health (global)
```

---

## 5. Row-Level Security (RLS)

**Model:** the API authenticates the user (JWT), then, per request transaction, sets a Postgres GUC with the user id. RLS policies restrict user-owned tables to that id. This is defense-in-depth *behind* app-layer filtering — not a replacement for it.

### 5.1 Per-request setup (in `db/session.py`) — READ THIS CAREFULLY
```sql
-- executed as the FIRST statement inside each authed request's transaction
SET LOCAL app.current_user_id = '<uuid-from-validated-jwt>';
```

**Non-negotiable connection rules (these prevent a silent "zero rows" break):**
1. `SET LOCAL` is **transaction-scoped**. Therefore **every authed request — reads included — MUST run inside one explicit transaction**, with the `SET LOCAL` as its first statement. If a query runs in autocommit mode, the GUC is not applied and the policy fails closed (returns nothing). The session layer must `begin()` a transaction per authed request and run all ORM queries within it.
2. The app connects with a **dedicated, non-superuser role that does NOT have `BYPASSRLS`**. Superusers and table owners bypass RLS and would defeat this entirely (hence `FORCE ROW LEVEL SECURITY` on every table).
3. Transaction-scoped GUC is **compatible with transaction-mode connection poolers** (pgbouncer, as used by some managed Postgres hosts). **Never** use session-level `SET` (without `LOCAL`) — it leaks across pooled connections and breaks tenancy.
4. A **separate privileged connection** (own role, RLS-subject but allowed on global tables) is used only by Celery system jobs that write global tables (`jobs`, `source_health`) and cross-user `ai_usage`. This connection never serves user API requests.

A missing/invalid GUC → `current_setting('app.current_user_id', true)` returns NULL → policy matches no rows (fail-closed). Good: a bug can only *hide* data, never *leak* it.

### 5.2 Enable + policies (user-owned tables)
```sql
-- repeat for: profiles, writing_samples, sample_chunks, scores,
--             proposals, subscriptions, ai_usage
ALTER TABLE profiles ENABLE ROW LEVEL SECURITY;
ALTER TABLE profiles FORCE ROW LEVEL SECURITY;

CREATE POLICY tenant_isolation ON profiles
  USING (user_id = current_setting('app.current_user_id', true)::uuid)
  WITH CHECK (user_id = current_setting('app.current_user_id', true)::uuid);
```
- `current_setting(..., true)` returns NULL if unset → policy fails closed (no rows) when the GUC is missing.
- `profiles` keys on `user_id` as its PK; all others use their `user_id` column (that's why `sample_chunks` denormalizes `user_id`).

### 5.3 Global tables
- `jobs`, `source_health`: **no RLS**; readable by all authed users through the API (API never exposes write). Written only by the privileged Celery connection.
- `refresh_tokens`: no RLS; touched only by the backend auth service (never via the user-scoped connection path exposed to RLS-tenant queries).

---

## 6. Auth Flow (end-to-end)

### Signup
1. `POST /auth/signup {email, password}` → validate, check unique email.
2. Hash password (bcrypt cost ≥ 12). Insert `users` and create `subscriptions` (free, quota 30) **in one transaction**. **No `profiles` row is created yet** — `profiles` has NOT NULL columns and is created at onboarding (US via `PATCH /me/profile`, which upserts). `GET /me` must tolerate a missing profile (returns `profile_complete=false`).
3. Issue access JWT (15 min) + refresh token (opaque; store SHA-256 in `refresh_tokens`; set httpOnly cookie).
4. **Email verification (MVP):** no email provider is in the MVP stack. In `ENVIRONMENT=development`/demo, accounts are **auto-verified** (`email_verified=true`) so the demo is frictionless. A real provider (e.g., Resend/SMTP) is required before production and is tracked as a post-MVP item — until then `email_verified` gating is a no-op in demo mode. Drafting checks `email_verified`; scoring/browsing never require it.

### Login
1. `POST /auth/login {email, password}` → fetch by email, `verify(password, hash)`. Generic 401 on failure.
2. Issue access + refresh (new row). Return access token in body; refresh as httpOnly cookie.

### Authenticated request
1. Client sends `Authorization: Bearer <access>`.
2. `deps.get_current_user` verifies JWT signature + expiry, loads user, and the session layer sets `app.current_user_id` GUC for the transaction.
3. All queries additionally filter by `user_id` in app code (belt-and-suspenders with RLS).

### Refresh (rotation)
1. `POST /auth/refresh` (refresh cookie sent automatically).
2. Hash incoming token, look up non-revoked, unexpired row. If missing/expired/revoked → 401 (+ if reuse of a revoked token detected, revoke all user tokens — reuse detection).
3. Revoke old, insert new (rotation), set new cookie, return new access token.
4. **Rotation race (multi-tab):** strict rotation + reuse-detection can falsely nuke sessions when two tabs refresh at once. Mitigate on the **client** with single-flight refresh (one in-flight refresh shared across tabs via a lock / BroadcastChannel), and on the **server** with a short reuse grace: a token revoked within the last ~10s by its immediate successor is treated as a benign race (return the current valid token's session), not an attack. Only reuse outside that window triggers full revocation.

### Logout
1. `POST /auth/logout` → revoke current refresh token, clear cookie.

---

## 7. Seed / Migration Order (Alembic)

1. Extensions (`pgcrypto`, `vector`, `citext`).
2. Enum types.
3. Tables in FK order: users → profiles, subscriptions, refresh_tokens → writing_samples → sample_chunks → jobs → scores → proposals → ai_usage → source_health.
4. Indexes (incl. HNSW, GIN).
5. `updated_at` trigger function + triggers.
6. RLS enable + policies.
7. Seed `source_health` rows (4 platforms).
