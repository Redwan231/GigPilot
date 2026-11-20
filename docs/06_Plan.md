# 06 — Implementation Plan (Atomic, Dependency-Ordered)

**Product:** GigPilot
**Version:** 1.0 (MVP)
**Last updated:** 2026-11-20

> The coding agent works top-to-bottom. Each task is atomic and verifiable.
> **After completing a task, the agent MUST check its box here and commit.** Do not batch.
> Do not start a task whose dependencies are unchecked. If a task reveals a spec gap,
> STOP and flag it against the relevant doc — do not improvise scope.

Legend: `[ ]` todo · `[x]` done · each task notes the doc it derives from and its acceptance check.

---

## Phase 0 — Repo & Tooling Foundation
- [x] **P0-1** Init monorepo structure per `04_TRD.md §3` (backend/, frontend/, docs/, root files). _Check: tree matches._
- [x] **P0-2** Add `docker-compose.yml` with services: `db` (pgvector/pgvector:pg16), `redis` (7.4), `backend`, `worker`, `beat`. _Check: `docker compose config` valid._
- [x] **P0-3** Add `.env.example` (all keys from `04_TRD.md §8`) and git-ignored `.env`. _Check: no secrets committed._
- [x] **P0-4** Backend `pyproject.toml` with pinned deps (`04_TRD.md §1`); ruff+black config. _Check: `pip install` resolves, lint runs._
- [x] **P0-5** Frontend `create-next-app` (TS, App Router, Tailwind); add deps (`04_TRD.md §1`). _Check: dev server boots._
- [x] **P0-6** CI-less local verify scripts: `make backend-test`, `make fe-test`. _Check: both run (empty pass)._

## Phase 1 — Database & Auth (foundation of everything)
- [x] **P1-1** Alembic init + async engine/session in `db/session.py`, incl. RLS GUC setter hook. _Derives: `05_Schema.md §5`._
- [x] **P1-2** Migration: extensions + enum types (`05_Schema.md §1–2`). _Check: migration up/down clean._
- [x] **P1-3** Migration: `users`, `profiles`, `subscriptions`, `refresh_tokens` + indexes + `updated_at` triggers. _Check: tables exist._
- [x] **P1-4** Migration: `writing_samples`, `sample_chunks` (vector(768) + HNSW), `jobs`, `scores`, `proposals`, `ai_usage`, `source_health`. _Check: HNSW index present, dim=768._
- [x] **P1-5** Migration: enable RLS + `tenant_isolation` policies on all user-owned tables (`05_Schema.md §5.2`). _Check: unset GUC → zero rows._
- [x] **P1-6** SQLAlchemy models mirroring every table (field names == columns). _Check: `Base.metadata` matches migration._
- [x] **P1-7** `core/security.py`: bcrypt hashing, JWT sign/verify (HS256), opaque refresh token gen + SHA-256. _Check: unit tests._
- [x] **P1-8** Auth endpoints: `signup`, `login`, `refresh` (rotation + reuse-detection), `logout` (`05_Schema.md §6`). _Check: integration tests cover happy + 401 + rotation._
- [x] **P1-9** `api/deps.py`: `get_current_user` (verify JWT, set RLS GUC), rate-limit deps. _Check: protected route rejects no/invalid token._
- [x] **P1-10** RLS isolation test: user A cannot read user B's rows even with forged `user_id` in body. _Check: test passes (critical security gate)._

## Phase 2 — Core API & Services (no UI yet)
- [x] **P2-1** `me` endpoints: `GET /me`, `PATCH /me/profile` (bumps `profile_version`), onboarding completion. _Derives: US-A3, `02_AppFlow §4.4`._
- [x] **P2-2** Writing samples: `POST/GET/DELETE /me/samples` (size/count limits). _Derives: US-A4._
- [x] **P2-3** `ai/embeddings.py` (Gemini `gemini-embedding-001` via google-genai) + chunking; embed samples on create, delete chunks on sample delete. _Check: chunks+vectors written, dim=768._
- [x] **P2-4** Adapters: `base.py` + 4 source adapters with unified `Job` normalize (`04_TRD §4.1`). _Check: each returns normalized Jobs from a fixture._
- [ ] **P2-5** Celery app + beat; `aggregate_jobs` task: per-source isolation, upsert on `(platform, external_id)`, update `source_health`. _Derives: US-B1, `04_TRD §6`._
- [ ] **P2-6** Jobs API: `GET /jobs` (filters: platform/category/skill/budget/min-score, sort newest|score), `GET /jobs/{id}`. _Derives: US-B1–B3, `02_AppFlow §4.5–4.6`._
- [ ] **P2-7** `ai/llm.py`: GLM 5.3 Flash client (OpenAI-compatible), JSON mode, timeouts/retries, writes `ai_usage`. _Check: mock + one live smoke._
- [ ] **P2-7b** `guardrails/`: `sanitize.py`, `injection.py` (delimit + detect prompt injection in job/sample text), `pii.py` (redact PII before embedding). All LLM-bound untrusted text passes through these. _Derives: `04_TRD §7b`. Check: injection-laced fixture does not alter model behavior._
- [ ] **P2-8** `services/scoring.py`: cheap skill-overlap pre-filter → AI score using the 4 data-honest dimensions `{skills, seniority, rate, freshness}` (terse JSON), cache in `scores` by `(user,job,profile_version)`, daily Redis cap. Endpoint `POST /jobs/{id}/score`. _Derives: US-C1/C3, `04_TRD §5, §5b`._
- [ ] **P2-9** Score reasoning on demand: `GET /jobs/{id}/score/why` (lazy-generate + cache `reasoning`). _Derives: US-C2._
- [ ] **P2-10** `agents/`: `GigPilotState`, LangGraph `graph.py` (nodes: retrieve_voice → draft; conditional entry from score), node impls. _Derives: `04_TRD §2`._
- [ ] **P2-11** `services/drafting.py`: Voice RAG (per-user ANN top-k) OR cold-start template; invoked via LangGraph. Endpoint `POST /jobs/{id}/draft`. _Derives: US-D1, PRD §6._
- [ ] **P2-12** `services/credits.py`: atomic quota check+increment on draft success only; monthly reset logic. _Derives: US-D4/F1–F3, `05_Schema §3.8`._
- [ ] **P2-13** Proposals API: create (on draft "mark as used"), `GET/PATCH/DELETE /proposals`, set outcome. _Derives: US-D3/E1, `02_AppFlow §4.7–4.8`._
- [ ] **P2-14** `services/stats.py` + `GET /me/stats` (win-rate, counts, won/lost avg score). _Derives: US-E2._
- [ ] **P2-15** Feedback loop (bounded, no training): inject one line of the user's recent won/lost/no-response stats + top winning skills into the scoring prompt. _Derives: US-E3, `04_TRD §5c`. Do NOT build training/weights._
- [ ] **P2-16** `GET /health`, `GET /health/ready`. _Check: ready fails when DB/Redis down._
- [ ] **P2-17** `mcp/server.py`: MCP server exposing `search_jobs`, `score_job`, `draft_proposal`, `list_proposals`, `set_outcome` — thin wrappers over existing `services/`, auth via `MCP_AUTH_TOKEN`→user, enforcing the same tenant scope/credits/caps/guardrails. _Derives: `04_TRD §10`. Check: a tool call runs under the user and consumes a credit on draft; never bypasses RLS._

## Phase 3 — UI Integration
- [ ] **P3-1** Tailwind config + `globals.css` CSS variables from `03_UI_Spec.md §2–4`; fonts (Space Grotesk/Inter/JetBrains Mono). _Check: tokens resolve in both themes._
- [ ] **P3-2** `components/ui/` primitives: Button, Input, Select, Textarea, Card, Badge/ScoreChip, Modal, Toast, Skeleton, EmptyState — all states from `03_UI_Spec §5`. _Check: storybook-less demo page renders states._
- [ ] **P3-3** API client + auth context (in-memory access token, silent refresh, 401 handling) + TanStack Query setup. _Derives: `02_AppFlow §2–3`._
- [ ] **P3-4** Route middleware for protected/public redirects. _Check: unauth → /login; auth on /login → /app._
- [ ] **P3-5** `/signup`, `/login` screens with RHF+Zod, inline errors. _Derives: `02_AppFlow §4.2–4.3`._
- [ ] **P3-6** `/onboarding` 3-step wizard (profile, samples, cold-start questionnaire). _Derives: `02_AppFlow §4.4`._
- [ ] **P3-7** App shell (sidebar/topbar, credits pill, user menu, theme). _Derives: `03_UI_Spec §5.9`._
- [ ] **P3-8** `/app` feed: filters, job cards, score chip + inline "Score", sort, all empty/loading/error states. _Derives: `02_AppFlow §4.5`._
- [ ] **P3-9** `/app/jobs/[id]`: score panel (+Why), draft panel (generate/edit/copy/export/regenerate/mark-used), credit + error states. _Derives: `02_AppFlow §4.6`._
- [ ] **P3-10** `/app/proposals` + `[id]`: list, inline outcome, edit/delete. _Derives: `02_AppFlow §4.7–4.8`._
- [ ] **P3-11** `/app/dashboard`: Recharts widgets + empty state. _Derives: `02_AppFlow §4.9`._
- [ ] **P3-12** `/app/settings`: profile, samples, plan/credits (upgrade stub), account (password, logout, delete). _Derives: `02_AppFlow §4.10`._
- [ ] **P3-13** 404 + global error boundary + offline toast. _Derives: `02_AppFlow §2`._

## Phase 4 — Edge Cases, Hardening & Tests
- [ ] **P4-1** Credit edge tests: 0 credits blocks draft; AI failure does NOT deduct; monthly reset. _Derives: `02_AppFlow §6`._
- [ ] **P4-2** Scoring cap test: daily cap blocks with reset messaging. _Derives: `02_AppFlow §6`._
- [ ] **P4-3** Cold-start path test: no samples → template draft, banner shown, `voice_matched=false`. _Derives: PRD §6._
- [ ] **P4-4** Dedup test: same job from two sources stored once. _Derives: `04_TRD §6`._
- [ ] **P4-5** Adapter-down test: one source errors, aggregation still succeeds, `source_health` updated. _Derives: `04_TRD §6`._
- [ ] **P4-6** Auth hardening: brute-force rate limit, refresh reuse → full revoke, expired → `/login?expired=1`. _Derives: `04_TRD §7`._
- [ ] **P4-7** RLS penetration test (re-assert P1-10 at API level). _Derives: `05_Schema §5`._
- [ ] **P4-8** Cost guard test: unchanged (user,job,profile_version) is NOT re-scored; `ai_usage` rows written with cost. _Derives: `04_TRD §5`._
- [ ] **P4-9** Input abuse: oversized sample/upload rejected; XSS in job/AI text not executed on render. _Derives: `04_TRD §7`._
- [ ] **P4-10** e2e smoke (Playwright): signup → onboarding → score → draft → mark used → set outcome → dashboard. _Derives: `02_AppFlow §5`._
- [ ] **P4-11** Seed/demo script: create a demo Pro user + fetch jobs, so judges see a populated app. _Derives: PRD §5._
- [ ] **P4-12** Evals harness `evals/run_evals.py`: (a) LLM-as-judge voice-draft vs generic baseline, (b) scoring accuracy vs labeled fixtures, (c) injection-resistance tests. Commit a report under `evals/`. _Derives: `04_TRD §11-evals`. Check: report generated; injection tests pass._
- [ ] **P4-13** MCP smoke: connect the server from a local MCP client (Claude Desktop/Cursor), run `search_jobs`→`score_job`→`draft_proposal`; verify auth + credit enforcement. _Derives: `04_TRD §10`._

## Phase 5 — Deploy (demo): no-card, free, always-on (`04_TRD §9`)
- [ ] **P5-1** Provision free managed services (no card): **Supabase** Postgres (`create extension vector;`), **Upstash** Redis. Put URLs in secrets. _Check: backend connects to both._
- [ ] **P5-2** Backend `Dockerfile` + process manager (`Procfile`/honcho or `supervisord.conf`) running `uvicorn` + `celery worker` + `celery beat`; deploy to **Hugging Face Spaces (Docker)**; Alembic auto-migrates on start. _Check: all three processes run in the Space; `/health/ready` green._
- [ ] **P5-3** Frontend on **Vercel**, env → HF Space URL, CORS allow-list set to the Vercel origin. _Derives: `04_TRD §7.6`._
- [ ] **P5-4** Keep-alive: **cron-job.org** hits `/health` every 5 min so Space + Supabase never idle-sleep. _Check: app reachable after >1h idle._
- [ ] **P5-5** Smoke the live core loop end to end; confirm always-on. _Check: judges can open it cold at any time._

---

## Progress Log (agent appends one line per completed task)
<!-- format: YYYY-MM-DD | task-id | commit-sha | note -->
2026-11-20 | P0-1 | 3177cb7 | Monorepo skeleton: backend/app/* packages, frontend/*, migrations/, .cursorrules (mirror), .gitignore; tree matches 04_TRD §3
2026-11-20 | P0-2 | 4ef82d6 | docker-compose.yml: db(pgvector:pg16)+redis(7.4)+backend+worker+beat; `docker compose config` valid
2026-11-20 | P0-3 | ba8a7aa | .env.example with all 04_TRD §8 keys (dummy values); .env git-ignored; done before P0-2 per user request
2026-11-20 | P0-4 | 549c2b7 | backend/pyproject.toml (deps per 04_TRD §1, ruff+black); installed into 3.13 venv, requirements.lock frozen, ruff/black clean. Flagged 4 forced version bumps (pydantic 2.10, pydantic-settings 2.6, httpx 0.28, asyncpg 0.30) reflected in 04_TRD §1
2026-11-20 | P0-5 | 497ded4 | Next.js 14.2.35 scaffold (TS/App Router/Tailwind) hand-rolled + deps per 04_TRD §1 (react 18.3.1, TS 5.4.5, tailwind 3.4.19, TanStack/RHF/Zod/Recharts/lucide + vitest/playwright/eslint); npm install ok, package-lock committed; `next dev` boots (GET / -> 200)
2026-11-20 | P0-6 | 018178f | Makefile with backend-test/fe-test/test/lint targets; backend pytest green (1 smoke test), frontend vitest --passWithNoTests exit 0. make not installed on this Windows box; verified underlying commands directly
2026-11-20 | P1-1 | 9661107 | Alembic (async env.py) + config.py (pydantic-settings, asyncpg URL normalize) + db/base.py + db/session.py with tenant_session (SET LOCAL ROLE gigpilot_app + set_config GUC) & system_session. alembic current clean vs local pgvector; ruff/black clean
2026-11-20 | P1-2 | 15542f8 | Migration 85563be81646: extensions (pgcrypto/vector/citext) + 7 enum types; up/down/up clean on local pgvector, objects verified
2026-11-20 | P1-3 | 832feeb | Migration 3d5c9c9161f9: users/profiles/subscriptions/refresh_tokens + GIN(skills)/idx(user_id) + set_updated_at() trigger on 3 tables; up/down/up clean, objects verified
2026-11-20 | P1-4 | 9ef6302 | Migration 95ab058184fe: writing_samples/sample_chunks(vector(768)+HNSW cosine)/jobs/scores/proposals/ai_usage/source_health + indexes + proposals updated_at trigger + source_health seed(4). HNSW+dim=768 verified; up/down/up clean
2026-11-20 | P1-5 | 8dcbe32 | Migration a59ea7d2435e: ENABLE+FORCE RLS + tenant_isolation policy on 7 user-owned tables; created non-BYPASSRLS role gigpilot_app + grants (DML user-owned, SELECT jobs/source_health). Probe: unset GUC->0 rows, GUC=A->only A. up/down/up clean
2026-11-20 | P1-6 | 2f3ad15 | ORM models for all 11 tables (app/db/models/*, one file per aggregate) + db/types.py (Vector custom type, no pgvector dep; pg_enum create_type=False). Verified: all 11 tables' columns == DB columns built by migrations (PASS); ruff clean
2026-11-20 | P1-7 | 9f538d4 | core/security.py: bcrypt(cost12) hash/verify, HS256 access JWT create/decode(type+exp check), opaque refresh token + sha256. 6 unit tests pass. Pinned bcrypt<5 (passlib 1.7.4 breaks with bcrypt 5 on py3.13) -> lock refrozen, 04_TRD §1 note ⁵
2026-11-20 | P1-8 | edb714f | Auth endpoints (schemas/auth, main app factory, api/routes/auth, conftest w/ NullPool + truncate). signup/login/refresh(rotation+reuse-detect+10s grace)/logout on system_session. Migration 099ba0111c1e adds refresh_tokens.revoked_at (reconciles §3.10 w/ §6). 10 integration + 6 unit tests pass (happy/401/rotation/reuse/logout-final)
2026-11-20 | P1-9 | 2b5b293 | api/deps.py: get_current_user_id (verify Bearer JWT), get_tenant_db (tenant_session RLS GUC), get_current_user (privileged user load); core/rate_limit.py (slowapi Limiter wired into app); protected GET /me (api/routes/me.py). 3 deps tests: no token->401, bad token->401, valid->200
2026-11-20 | P1-10 | b7d0b96 | RLS isolation gate (test_rls.py, 4 tests) GENUINELY PASS vs real Postgres under non-BYPASSRLS role: A sees only A; forged-id read of B -> nothing; forged INSERT user_id=B -> WITH CHECK reject (DBAPIError); forged UPDATE/DELETE -> 0 rows; API token maps to own user only. Full suite 24 passed
2026-11-20 | P2-1 | b26ea2b | GET /me (full user+profile), PATCH /me/profile (upsert+version bump+onboarding completion); schemas/me.py + 6 tests pass
2026-11-20 | P2-2 | 2a26703 | Writing samples POST/GET/DELETE /me/samples; size/count limits (20k chars, 5 max); RLS-scoped; 7 tests pass
2026-11-20 | P2-3 | 92a9e67 | Gemini embeddings+chunking; embed on create; Vector bind/result processors; 6 tests (chunks+vectors dim=768 verified)
2026-11-20 | P2-4 | 509201e | Adapters: base ABC + remoteok/remotive/himalayas/wwr; unified RawJob normalize; 8 fixture tests pass
