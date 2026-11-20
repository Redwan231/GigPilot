# 04 — Technical Requirements Document (TRD)

**Product:** GigPilot
**Version:** 1.0 (MVP)
**Last updated:** 2026-11-20

> The locked tech stack, versions, folder structure, external APIs, resilience, cost controls, and security.
> Versions are pinned at the MINOR level; the coding agent pins exact patch versions in lockfiles on first install and records them here.

---

## 1. Locked Stack

### Backend
| Concern | Choice | Version (minor) |
|---|---|---|
| Language | Python | 3.12 |
| API framework | FastAPI | 0.115.x |
| ASGI server | Uvicorn (+ Gunicorn in prod) | 0.30.x / 22.0.x |
| ORM | SQLAlchemy (async) | 2.0.x |
| Migrations | Alembic | 1.13.x |
| Validation/serialization | Pydantic | 2.10.x ¹ |
| DB driver | asyncpg | 0.30.x ² |
| Task queue | Celery | 5.4.x |
| Beat scheduler | celery[beat] | 5.4.x |
| Broker/cache | Redis | 7.4 (server) / redis-py 5.0.x |
| Agent orchestration | LangGraph | 0.2.x |
| LLM client | openai (OpenAI-compatible, points at Open Inference) | 1.40.x |
| Embeddings client | google-genai (Gemini `gemini-embedding-001`) | 1.x |
| MCP server | mcp (official Python SDK) | 1.2.x |
| Process manager (single-container deploy) | honcho (or supervisord) | 2.0.x |
| HTTP client | httpx | 0.28.x ³ |
| HTML parsing | beautifulsoup4 | 4.12.x |
| Auth / JWT | PyJWT | 2.9.x |
| Password hashing | passlib[bcrypt] | 1.7.4 |
| Rate limiting | slowapi (or Redis token bucket) | 0.1.9 |
| Settings | pydantic-settings | 2.6.x ⁴ |
| Testing | pytest + pytest-asyncio + httpx test client | 8.x / 0.24.x |
| Lint/format | ruff + black | latest pinned |

> **Resolved patch versions (locked at P0-4, backend).** Exact pins live in `backend/requirements.lock`
> (`pip freeze`); `backend/pyproject.toml` constrains at the minor via `~=`. First install into the
> project venv (`backend/.venv`, **Python 3.13** — the docs target 3.12; `requires-python=">=3.12"`
> admits both) resolved: fastapi 0.115.14 · uvicorn 0.30.6 · gunicorn 22.0.0 · sqlalchemy 2.0.58 ·
> alembic 1.13.3 · **pydantic 2.10.6** · **pydantic-settings 2.6.1** · **asyncpg 0.30.0** · celery 5.4.0 ·
> redis-py 5.0.8 · langgraph 0.2.76 · openai 1.40.8 · google-genai 1.75.0 · mcp 1.2.1 · honcho 2.0.0 ·
> **httpx 0.28.1** · beautifulsoup4 4.12.3 · PyJWT 2.9.0 · passlib 1.7.4 (bcrypt 5.0.0) · slowapi 0.1.9 ·
> pytest 8.4.2 · pytest-asyncio 0.24.0 · ruff 0.17.6 · black 26.10.1.
>
> **Four pins were raised from the original minors to resolve real conflicts — flagged, not silent:**
> ¹ Pydantic 2.9→**2.10.x**: `mcp 1.2.x` requires `pydantic>=2.10.1`.
> ² asyncpg 0.29→**0.30.x**: 0.29 ships no cp313 wheel and the local venv is Python 3.13 (0.30 adds it).
> ³ httpx 0.27→**0.28.x**: `google-genai 1.x` requires `httpx>=0.28.1`.
> ⁴ pydantic-settings 2.5→**2.6.x**: `mcp 1.2.x` requires `pydantic-settings>=2.6.1`.
> All four stay within the same major and change no architectural choice; they are the minimal moves
> that make the locked `mcp 1.2.x` + `google-genai 1.x` set installable on this runtime.

### Frontend
| Concern | Choice | Version (minor) |
|---|---|---|
| Framework | Next.js (App Router) | 14.2.x |
| Runtime | React | 18.3.x |
| Language | TypeScript | 5.4.x |
| Styling | Tailwind CSS | 3.4.x |
| Data fetching/cache | TanStack Query | 5.x |
| Forms | React Hook Form + Zod | 7.x / 3.x |
| Charts | Recharts | 2.12.x |
| HTTP | native fetch wrapper | — |
| Icons | lucide-react | 0.4xx |
| Testing | Vitest + React Testing Library + Playwright (e2e smoke) | pinned |
| Lint/format | eslint + prettier | pinned |

### Database & Infra
| Concern | Choice | Version |
|---|---|---|
| RDBMS | PostgreSQL | 16 |
| Vector | pgvector extension | 0.7.x+ |
| Containers | Docker + Docker Compose | v2 |
| Node | Node.js | 20 LTS |

**No stack additions without updating this file.** If the agent needs a library not listed, it must stop and flag it, not silently add it.

---

## 2. System Architecture (logical)

```
┌─────────────┐     HTTPS/JSON      ┌──────────────────────────┐
│ Next.js 14  │◄───────────────────►│  FastAPI (API gateway)   │
│ (Vercel)    │   access JWT +      │  - auth, REST endpoints  │
│             │   refresh cookie    │  - enqueues Celery tasks │
└─────────────┘                     └───────┬───────┬──────────┘
                                            │       │
                              enqueue       │       │ sync reads/writes
                                            ▼       ▼
                                   ┌──────────┐  ┌──────────────────┐
                                   │ Redis 7  │  │ PostgreSQL 16    │
                                   │ broker + │  │ + pgvector       │
                                   │ cache    │  └──────────────────┘
                                   └────┬─────┘
                                        │ consume
                                        ▼
                            ┌──────────────────────────┐
                            │ Celery workers           │
                            │  + LangGraph StateGraph  │
                            │  nodes: score/retrieve/  │
                            │  draft/review (aggregate │
                            │  = separate beat job)    │
                            └───────┬───────┬──────────┘
                                    │       │
                         GLM 5.3 Flash   Gemini embedding-001
                        (Open Inference) (google-genai, 768-d)
```

Also exposed: an **MCP server** wrapping the same `services/` so MCP clients (Claude Desktop, Cursor) can call `search_jobs` / `score_job` / `draft_proposal` under a user's auth, credits, and guardrails (see §10).

**Control-flow boundary (important):** LangGraph owns the *agent logic* (which node runs next, conditional routing, state shape). Celery owns *distributed execution* (running the graph/task, retries, scheduling). A Celery task invokes a compiled LangGraph — they do not duplicate routing logic.

**What is in the graph vs not (be precise — the submission must match this):**
- **LangGraph StateGraph** = the per-job agent flow: `score → route(conditional) → retrieve_voice → draft → await_review`. Nodes read/write `GigPilotState`. The conditional edge after `score` routes high scores to drafting, mid to user-review, low to end/archive.
- **NOT in the graph:** job **aggregation** is a scheduled Celery beat pipeline that populates the global `jobs` table upstream of the graph. It is infrastructure, not agent reasoning. Do not model it as a graph node.
- A single Celery task compiles and runs the graph for one (user, job) request; the graph's long-running `await_review` state is persisted so it survives restarts.

---

## 3. Folder Structure

```
gigpilot/
├── docs/                      # the 6 context docs (this directory)
├── CLAUDE.md                  # agent entry rules (root)
├── .cursorrules               # mirror of CLAUDE.md for Cursor
├── docker-compose.yml
├── .env.example               # every required env var, no secrets
├── backend/
│   ├── pyproject.toml
│   ├── alembic.ini
│   ├── migrations/            # Alembic versions
│   └── app/
│       ├── main.py            # FastAPI app factory
│       ├── config.py          # pydantic-settings
│       ├── db/
│       │   ├── session.py     # async engine/session, RLS GUC setter
│       │   ├── base.py
│       │   └── models/        # SQLAlchemy models (one file per aggregate)
│       ├── schemas/           # Pydantic request/response models
│       ├── api/
│       │   ├── deps.py        # auth dependency, current_user, rate limits
│       │   └── routes/        # auth.py, jobs.py, proposals.py, me.py
│       ├── core/
│       │   ├── security.py    # jwt, hashing
│       │   └── rate_limit.py
│       ├── services/          # business logic (no framework code)
│       │   ├── scoring.py
│       │   ├── drafting.py
│       │   ├── credits.py
│       │   └── stats.py
│       ├── agents/            # LangGraph
│       │   ├── state.py       # GigPilotState TypedDict
│       │   ├── graph.py       # StateGraph wiring
│       │   └── nodes/         # aggregate.py, score.py, retrieve.py, draft.py
│       ├── adapters/          # platform source adapters
│       │   ├── base.py        # Adapter ABC + unified Job mapping
│       │   ├── remoteok.py
│       │   ├── remotive.py
│       │   ├── himalayas.py
│       │   └── weworkremotely.py
│       ├── ai/                # provider clients
│       │   ├── llm.py         # GLM 5.3 Flash via OpenAI-compatible client
│       │   └── embeddings.py  # Gemini gemini-embedding-001 (google-genai)
│       ├── guardrails/        # input/output safety (see §7b)
│       │   ├── sanitize.py    # strip/neutralize untrusted job + sample text
│       │   ├── injection.py   # prompt-injection detection + delimiting
│       │   └── pii.py         # PII scrub on uploaded samples
│       ├── mcp/               # MCP server exposing GigPilot tools (see §10)
│       │   └── server.py
│       ├── evals/             # offline eval harness (see §11-evals)
│       │   ├── datasets/      # fixtures: sample jobs, gold drafts, outcomes
│       │   └── run_evals.py   # LLM-as-judge + scoring-accuracy metrics
│       ├── workers/
│       │   ├── celery_app.py
│       │   ├── beat.py        # schedules
│       │   └── tasks.py       # aggregate_jobs, run_pipeline, etc.
│       └── tests/
├── Procfile                   # honcho: web + worker + beat (single-container deploy)
└── (backend/) supervisord.conf # alt process manager for the HF Space container
└── frontend/
    ├── package.json
    ├── tailwind.config.ts     # extends tokens from 03_UI_Spec.md
    ├── app/                   # App Router routes (see 02_AppFlow.md)
    ├── components/            # ui/ (tokens-based primitives) + feature/
    ├── lib/                   # api client, auth, query hooks
    ├── styles/                # globals.css with CSS variables
    └── tests/
```

---

## 4. External APIs & Providers

### 4.1 Job source adapters (read-only, free)
| Source | Method | Notes |
|---|---|---|
| RemoteOK | public JSON endpoint | respect attribution/ToS; set UA; cache |
| Remotive | public JSON API | category params |
| Himalayas | public JSON API | pagination |
| WeWorkRemotely | RSS/Atom feeds per category | parse with feed/BS4 |

**Adapter contract (`adapters/base.py`):** each adapter implements `async fetch(since) -> list[RawJob]` and `normalize(raw) -> Job`. All adapters map to one unified `Job` schema (see `05_Schema.md`). Adapters must: set a descriptive User-Agent, honor robots/ToS, back off on 429, and never hard-fail the whole aggregation if one source errors (isolate per-source).

### 4.2 AI providers
| Provider | Model | Endpoint | Use |
|---|---|---|---|
| Open Inference | GLM 5.3 Flash | OpenAI-compatible `/v1/chat/completions` | scoring + drafting |
| Google Gemini | `gemini-embedding-001` | google-genai SDK (Google AI Studio free tier) | embeddings |

- **Embedding dimension = 768** (Gemini `gemini-embedding-001` default output; it supports Matryoshka truncation but we use 768). The pgvector column and HNSW index are sized to 768 (see `05_Schema.md §3.4`). Verify the current default dimension against Google AI Studio docs before running migration P1-4; if it differs, update the column + index in the same migration.
- GLM pricing (for cost accounting): input `$0.05/M`, output `$0.45/M`, cache read `$0.025/M`. Gemini embeddings: free tier via AI Studio (verify current quota).
- All LLM calls: `response_format=json_object` where structured output is required, temperature low (≤0.3) for scoring, moderate (~0.6) for drafting, hard `max_tokens`, request timeout 30s, 2 retries with jitter, then graceful failure.

### 4.3 API Surface (single source of truth for FE ↔ BE)

All `/me/*`, `/jobs/*`, `/proposals/*` require a valid access token. List endpoints are cursor-paginated: `?limit=<=50&cursor=<opaque>` → `{items, next_cursor}`.

| Method | Path | Purpose | Derives |
|---|---|---|---|
| POST | `/auth/signup` | create account | US-A1 |
| POST | `/auth/login` | login | US-A2 |
| POST | `/auth/refresh` | rotate refresh, new access | §6 Schema |
| POST | `/auth/logout` | revoke refresh | §6 Schema |
| GET | `/me` | current user + profile_complete | US-A2 |
| PATCH | `/me/profile` | upsert profile (bumps profile_version) | US-A3 |
| GET | `/me/samples` | list writing samples | US-A4 |
| POST | `/me/samples` | add sample (embeds) | US-A4 |
| DELETE | `/me/samples/{id}` | delete sample (+chunks) | US-A4 |
| GET | `/me/stats` | dashboard stats | US-E2 |
| GET | `/me/credits` | tier, remaining, reset date | US-F2 |
| GET | `/jobs` | feed (filters: platform, category, skill, budget_min/max, min_score; sort=newest\|score; paginated) | US-B1–B2 |
| GET | `/jobs/{id}` | job detail (+ user's score/drafts) | US-B3 |
| POST | `/jobs/{id}/score` | compute/get cached score (daily cap) | US-C1 |
| GET | `/jobs/{id}/score/why` | lazy reasoning (cached) | US-C2 |
| POST | `/jobs/{id}/draft` | generate proposal (−1 credit on success) | US-D1 |
| GET | `/proposals` | list (filter status/outcome, paginated) | US-E1 |
| POST | `/proposals` | save a draft as a proposal (mark used) | US-D3 |
| GET | `/proposals/{id}` | detail | — |
| PATCH | `/proposals/{id}` | edit content / set outcome | US-E1 |
| DELETE | `/proposals/{id}` | delete | — |
| GET | `/health`, `/health/ready` | liveness / readiness | P2-16 |

**Budget filter semantics:** jobs with `NULL` budget are **included** by default (most board jobs lack budget); a budget filter only constrains jobs that *have* a value. Never hide null-budget jobs implicitly.

---

## 5. Cost Controls (hard requirements)

1. **Reactive scoring only.** Never batch-score all jobs for all users. Score on view/request.
2. **Cheap pre-filter before AI.** Compute non-AI skill-keyword overlap; only AI-score jobs above a threshold or explicitly requested.
3. **Terse scoring output.** Scoring returns minimal JSON (`score`, `confidence`, per-dimension integers). Full natural-language reasoning is generated **only on "Why?" request** and cached.
4. **Cache & dedup.** Cache a job's score per (user, job, profile-version); invalidate when profile/samples change. Never re-score unchanged pairs.
5. **Prompt caching.** Static system prompts sent via cache-eligible path ($0.025/M).
6. **Metering table.** Every LLM call writes tokens+cost to `ai_usage` for observability and per-user cost tracking.
7. **Daily scoring cap** per tier (e.g., Free 100/day, Pro 1000/day) enforced in Redis.
8. **Draft credit deducted only on success** (never on AI failure/timeout).

---

## 5b. Scoring Model (MVP) — data-honest dimensions

> **Important:** MVP sources are **job boards** (RemoteOK, Remotive, Himalayas, WWR), NOT bidding platforms. They do **not** expose client hire-rate or competing-proposal counts. The scoring rubric must only use data we actually have. Do not prompt the model to assess "client history" or "number of proposals" in MVP.

Win-probability score (0–100) is computed from four **computable** dimensions:

| Dimension | Signal (available in MVP) |
|---|---|
| **Skills match** | overlap between profile `skills` and job `skills`/description (also used as the cheap non-AI pre-filter) |
| **Seniority fit** | job's implied level vs. profile `experience_level` |
| **Rate/budget fit** | job `budget_min/max` vs. profile `hourly_rate` **when present**; neutral (no penalty) when the job has no budget (most board jobs) |
| **Freshness/competition proxy** | `posted_at` recency — newer = better odds; a proxy for competition since we can't see proposal counts |

- The scoring prompt receives: profile summary, job summary, and (for the feedback loop) a short line of the user's recent outcome stats (see §5c). It returns terse JSON: `{score, confidence, dims:{skills,seniority,rate,freshness}}`.
- `dimensions` JSONB in `scores` stores these four integer sub-scores. The UI "Why?" expander maps to these labels.

## 5c. Feedback Loop (MVP) — bounded, no training

US-E3 is intentionally minimal to avoid scope creep:
- When scoring, inject one line into the prompt: *"This user's recent outcomes: won N, lost M, no-response K; they tend to win jobs with <top skills of won jobs>."* computed from their `proposals`.
- No model training, no weight files, no online learning. The "recalibration" is this retrieved-context nudge plus surfacing win-rate on the dashboard.
- This keeps the loop honest (it does use outcomes) and cheap (one extra context line).

## 6. Resilience

- **Per-source isolation:** one adapter failing does not fail aggregation; record source health.
- **Circuit breaker** per adapter and per AI provider (open after N consecutive failures, half-open probe).
- **Retries with exponential backoff + jitter** on 429/5xx; capped.
- **Idempotent aggregation:** upsert on unique `(platform, external_id)`; no duplicates.
- **Celery:** `acks_late=true`, `task_time_limit`, dead-letter via max_retries; idempotent task bodies.
- **Graceful AI degradation:** if drafting provider is down, surface a clear error and do not charge a credit.

---

## 7. Security Constraints

1. **Secrets:** only via environment variables; `.env` git-ignored; `.env.example` lists every key with dummy values. No secret ever committed or logged.
2. **Auth:** access JWT (15 min, in-memory on client), refresh token (opaque, hashed-at-rest in DB, 7 days, httpOnly+Secure+SameSite=Lax cookie, rotated on use, revocable). Passwords bcrypt (cost ≥ 12). Generic auth errors (no user enumeration).
3. **Tenant isolation (two layers):**
   - **App layer:** every query filters by `current_user_id` from the validated JWT (never from client body).
   - **DB layer (defense-in-depth):** Postgres RLS on all user-owned tables; the request sets `SET LOCAL app.current_user_id = :uid` per transaction; policies restrict rows to that id. (See `05_Schema.md` §RLS.)
4. **Input validation:** all input via Pydantic/Zod; reject unknown fields; size limits on uploads (≤1MB/sample, ≤5 samples).
5. **Rate limiting:** per-IP on auth endpoints (anti-brute-force); per-user on scoring/drafting/manual-refresh.
6. **CORS:** allow-list the frontend origin only; credentials mode for the refresh cookie.
7. **Output handling:** treat source job text and AI output as untrusted; sanitize before render (no `dangerouslySetInnerHTML` on job/AI content); external links `rel="noopener noreferrer"`.
8. **PII minimization:** store only what's needed; user can delete account + samples (cascades).
9. **Abuse control:** email verification required before drafting; soft device/IP heuristics on free-tier signup (log, don't hard-block in MVP).
10. **Transport:** HTTPS everywhere; HSTS at the edge.

---

## 8. Environment Variables (`.env.example`)

```
# --- Core ---
ENVIRONMENT=development
SECRET_KEY=change-me                 # JWT signing (HS256) or use RS256 keypair
ACCESS_TOKEN_TTL_MIN=15
REFRESH_TOKEN_TTL_DAYS=7
AUTH_AUTO_VERIFY_EMAIL=true          # demo: skip email verification (no provider in MVP). Set false + add provider for prod.
# --- Database ---
DATABASE_URL=postgresql+asyncpg://gigpilot:password@db:5432/gigpilot
# --- Redis ---
REDIS_URL=redis://redis:6379/0
# --- AI ---
LLM_BASE_URL=https://<open-inference-endpoint>/v1
LLM_API_KEY=change-me
LLM_MODEL=glm-5.3-flash
GEMINI_API_KEY=change-me             # Google AI Studio key (free tier)
EMBEDDING_MODEL=gemini-embedding-001
EMBEDDING_DIM=768
# --- MCP ---
MCP_ENABLED=true
MCP_AUTH_TOKEN=change-me             # bearer token MCP clients present to act for a user
# --- Frontend ---
NEXT_PUBLIC_API_BASE_URL=http://localhost:8000
# --- Limits ---
FREE_DRAFTS_PER_MONTH=30
PRO_DRAFTS_PER_MONTH=500
FREE_SCORES_PER_DAY=100
PRO_SCORES_PER_DAY=1000
```

**Deploy note:** on Hugging Face Spaces, `DATABASE_URL` points at Supabase, `REDIS_URL` at Upstash (use their `rediss://` TLS URL). Set all secrets as Space "Secrets", never in the repo.

---

## 9. Deployment (demo) — LOCKED: no-card, free, always-on

Constraints: zero credit card, free, and **always reachable** so judges can open it at any time. Nothing is cut from the architecture — Celery, Redis, LangGraph, pgvector all remain.

| Layer | Host | Card? | Notes |
|---|---|---|---|
| Frontend (Next.js) | **Vercel** free | no | `NEXT_PUBLIC_API_BASE_URL` → backend URL |
| Backend: FastAPI + Celery worker + beat **in one container** | **Hugging Face Spaces (Docker)** free | no | one process manager (honcho/supervisord) runs all three (`Procfile`/`supervisord.conf`) |
| Redis (Celery broker + cache) | **Upstash** free | no | serverless; use `rediss://` TLS URL. If Celery misbehaves on Upstash, swap broker to **CloudAMQP** free RabbitMQ (also no card) |
| Postgres + pgvector | **Supabase** free | no | enable extension: `create extension vector;` |
| Keep-alive | **cron-job.org** free | no | hit `/health` every 5 min so the Space + Supabase never idle-sleep |

**Single-container backend:** HF Spaces runs one Docker image. The container's start command runs a process manager that launches `uvicorn` (binds the Space port), `celery worker`, and `celery beat` together. Redis and Postgres are external (Upstash/Supabase), so no data lives in the ephemeral Space.

**Local dev is unchanged:** `docker-compose.yml` still runs `pgvector/pgvector:pg16` + Redis + backend + worker locally. The hosted stack only swaps the DB/Redis URLs.

- **Migrations:** run Alembic on container start before the app boots.
- **Health:** `/health` (liveness) + `/health/ready` (DB+Redis check); the keep-alive cron targets `/health`.
- **Caveats (honest):** HF free CPU (2 vCPU/16GB) suits demo load, not heavy traffic; Supabase free pauses after ~7 days idle and HF after ~48h — the keep-alive cron prevents both. Verify each provider's current free limits before the event.

---

## 7b. Guardrails (safety) — in scope

Untrusted text enters the LLM from two places: **job descriptions** (scraped) and **uploaded writing samples**. Both must be guarded.

1. **Prompt-injection defense (`guardrails/injection.py`):** job/sample text is never concatenated raw into a prompt. It is wrapped in clearly delimited, labeled blocks with an explicit system instruction that content inside is data, not instructions. A lightweight detector flags known injection patterns ("ignore previous instructions", role-switch attempts) and strips/escapes them; drafting uses the freelancer's voice + job facts only, never obeys embedded commands.
2. **Input sanitization (`guardrails/sanitize.py`):** strip control chars, cap length, normalize whitespace, remove HTML/script from job text before storage and before prompting.
3. **PII scrub on samples (`guardrails/pii.py`):** uploaded samples may contain the user's (or clients') emails/phones. Redact obvious PII before embedding/storage; never send raw PII to the embedding provider beyond what's needed.
4. **Output validation:** all AI outputs validated against Pydantic schemas (scores in range, draft non-empty, no system-prompt leakage) before returning; on failure, retry or fail safe (no credit charge).
5. **Render safety (frontend):** job text and AI output are untrusted — never `dangerouslySetInnerHTML`; escape on render; external links `rel="noopener noreferrer"`.

## 10. MCP Server — in scope

GigPilot ships an **MCP (Model Context Protocol) server** (`mcp/server.py`) so any MCP client (Claude Desktop, Cursor) can use GigPilot as tools. It is a thin wrapper over existing services — no business logic is duplicated.

**Exposed tools (reuse `services/`):**
| MCP tool | Wraps | Does |
|---|---|---|
| `search_jobs(filters)` | jobs service | return aggregated/filtered jobs |
| `score_job(job_id)` | `services/scoring.py` | return the 4-dimension score |
| `draft_proposal(job_id)` | `services/drafting.py` | return a voice-matched draft (consumes a credit) |
| `list_proposals(status?)` | proposals service | list the user's proposals |
| `set_outcome(proposal_id, outcome)` | proposals service | mark won/lost/no-response |

- **Auth:** the MCP client presents a bearer token (`MCP_AUTH_TOKEN` → resolves to a user); all tool calls run under that user's tenant scope + credits + caps (same guardrails/limits as the REST API). The MCP server never bypasses RLS, credits, or guardrails.
- **Transport:** stdio for local clients; optional HTTP/SSE if hosted. For the demo, stdio + a short "connect GigPilot in Claude Desktop" clip is enough.
- **Human-in-the-loop still holds:** `draft_proposal` returns text; it never submits anything.

## 11-evals. Evaluation Harness — in scope

Offline harness (`evals/run_evals.py`) run on demand (not in the request path):
1. **Draft quality (LLM-as-judge):** for a fixture set of jobs, generate a voice-matched draft and a generic baseline; an LLM judge scores each on voice-match, relevance, specificity. Report win-rate of voice vs baseline.
2. **Scoring accuracy:** on a labeled set (jobs with known good/bad fit), measure correlation between predicted score and the label; report MAE / ranking quality.
3. **Guardrail tests:** feed injection-laced job fixtures; assert the drafter ignores embedded instructions (no leakage, stays on task).
4. **Output:** a small markdown/JSON report committed under `evals/` — usable as evidence in the submission's Evaluation section.
